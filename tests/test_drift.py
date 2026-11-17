"""Simulacao e deteccao de drift (Etapa 2, docs/DRIFT.md)."""

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import pytest
import structlog

from src.config import get_seed, load_config, load_scenarios
from src.contracts.corruption import corrupt_batch
from src.data import loader
from src.data.schema import FEATURE_NAMES, RAW_TO_NAMED, TARGET_COLUMN
from src.data.synthetic import generate_synthetic
from src.drift.detect import detect_drift
from src.drift.scenarios import relabel, sampling_weights, scale, simulate_batch
from src.monitoring.log import configure_logging
from src.monitoring.prometheus import PUSHGATEWAY_ENV
from src.pipeline import drift as drift_stage
from src.pipeline import prepare
from src.pipeline import train as train_stage
from src.pipeline.io import json_text
from src.pipeline.monitor import run_monitored_batch
from src.pipeline.validate import IngestedBatch

SEED = get_seed()
BILLS = [f"BILL_AMT{i}" for i in range(1, 7)]
EVIDENCE = drift_stage.DRIFT_REPORT_DIR / drift_stage.SUMMARY_FILE


@pytest.fixture
def pool() -> pd.DataFrame:
    """Pool pequeno no formato ja renomeado (sintetico, sem rede)."""
    frame = generate_synthetic(4_000, seed=SEED).rename(columns=RAW_TO_NAMED)
    frame["EDUCATION"] = frame["EDUCATION"].clip(1, 4)
    frame["MARRIAGE"] = frame["MARRIAGE"].clip(1, 3)
    return frame


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """MLflow, log e Pushgateway isolados do ambiente de quem roda os testes."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    monkeypatch.delenv(PUSHGATEWAY_ENV, raising=False)
    configure_logging("json", log_file=tmp_path / "pipeline.jsonl")
    yield tmp_path
    structlog.reset_defaults()


# --- Cenarios ---------------------------------------------------------------------------


def test_uniform_sampling_has_no_weights(pool: pd.DataFrame) -> None:
    assert sampling_weights(pool, []) is None


def test_resample_favors_the_declared_profile(pool: pd.DataFrame) -> None:
    rules = [{"column": "AGE", "below": 30, "weight": 4.0}]
    batch = simulate_batch(pool, {"resample": rules}, rows=1_000, seed=SEED)
    assert (batch["AGE"] < 30).mean() > (pool["AGE"] < 30).mean() + 0.10


def test_same_seed_gives_same_batch(pool: pd.DataFrame) -> None:
    scenario = {"scale": [{"columns": BILLS, "factor": 1.25}]}
    first = simulate_batch(pool, scenario, rows=500, seed=SEED)
    pd.testing.assert_frame_equal(first, simulate_batch(pool, scenario, rows=500, seed=SEED))


def test_scale_changes_only_declared_columns_and_keeps_types(pool: pd.DataFrame) -> None:
    scaled = scale(pool, ["LIMIT_BAL"], 0.85)
    assert (scaled.dtypes == pool.dtypes).all()
    assert np.allclose(scaled["LIMIT_BAL"], (pool["LIMIT_BAL"] * 0.85).round())
    untouched = [c for c in pool.columns if c != "LIMIT_BAL"]
    pd.testing.assert_frame_equal(scaled[untouched], pool[untouched])


def test_relabel_only_turns_eligible_good_payers_into_defaults(pool: pd.DataFrame) -> None:
    rule = {"min_utilization": 0.5, "max_pay_status": 0, "probability": 1.0}
    relabeled = relabel(pool, rule, SEED)

    changed = relabeled[TARGET_COLUMN] != pool[TARGET_COLUMN]
    utilization = pool["BILL_AMT1"].clip(lower=0) / pool["LIMIT_BAL"]
    assert changed.sum() > 0
    assert (pool.loc[changed, TARGET_COLUMN] == 0).all()
    assert (relabeled.loc[changed, TARGET_COLUMN] == 1).all()
    assert (pool.loc[changed, "PAY_0"] <= 0).all() and (utilization[changed] >= 0.5).all()
    pd.testing.assert_frame_equal(relabeled[FEATURE_NAMES], pool[FEATURE_NAMES])


# --- Configuracao dos cenarios ----------------------------------------------------------


def test_control_batch_has_no_perturbation() -> None:
    control = load_scenarios()["M01"]
    assert not {"resample", "relabel", "scale"} & set(control)
    assert control["expected"] == {"drifted": [], "performance_alert": False}


def test_scenarios_drift_at_least_two_model_features() -> None:
    """Exigencia do enunciado: drift intencional em >= 2 variaveis importantes."""
    excluded = set(load_config()["model"]["excluded_columns"])
    expected = {c for s in load_scenarios().values() for c in s["expected"]["drifted"]}
    assert len(expected - excluded) >= 2


def test_versioned_evidence_meets_every_declared_expectation() -> None:
    """Expectativas valem no dataset real: confere a evidencia versionada lote a lote.

    O CI (job do dataset real) regenera ``drift_summary.json`` e exige que ele saia igual
    ao versionado; este teste exige que, nele, cada lote faca o que o cenario declara.
    """
    summary = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert summary["source"] == "real"
    assert list(summary["batches"]) == list(load_scenarios())
    for batch_id, batch in summary["batches"].items():
        expected = load_scenarios()[batch_id]["expected"]
        assert batch["expected"] == expected, f"{batch_id}: resumo desatualizado em relacao ao YAML"
        assert sorted(batch["drifted"]) == sorted(expected["drifted"]), batch_id
        assert batch["performance_alert"] == expected["performance_alert"], batch_id
        assert batch["expectation_met"], batch_id


def test_scenarios_only_touch_known_columns() -> None:
    known = set(FEATURE_NAMES)
    for scenario in load_scenarios().values():
        for rule in scenario.get("resample", []):
            assert rule["column"] in known
        for step in scenario.get("scale", []):
            assert set(step["columns"]) <= known


# --- Deteccao ---------------------------------------------------------------------------


def test_detection_separates_stable_from_shifted_columns() -> None:
    rng = np.random.default_rng(SEED)
    reference = pd.DataFrame(
        {"stable": rng.normal(0, 1, 3_000), "shifted": rng.normal(0, 1, 3_000)}
    )
    current = pd.DataFrame({"stable": rng.normal(0, 1, 2_000), "shifted": rng.normal(1, 1, 2_000)})

    results, _ = detect_drift(reference, current, ["stable", "shifted"])

    assert results["stable"].psi < 0.10 < 0.25 < results["shifted"].psi
    assert results["shifted"].ks_d > results["stable"].ks_d
    assert results["shifted"].ks_pvalue < 0.05


# --- Relatorios HTML (30 MB: so substituidos quando o resumo muda) ----------------------


def test_summary_change_is_detected_byte_for_byte(tmp_path: Path) -> None:
    summary_file = tmp_path / "drift_summary.json"
    assert drift_stage.summary_changed(summary_file, {"a": 1})  # ainda nao existe
    summary_file.write_text(json_text({"a": 1}), encoding="utf-8", newline="\n")
    assert not drift_stage.summary_changed(summary_file, {"a": 1})
    assert drift_stage.summary_changed(summary_file, {"a": 2})


def test_html_reports_are_kept_when_numbers_did_not_change(tmp_path: Path) -> None:
    staging, reports = tmp_path / "staging", tmp_path / "reports"
    staging.mkdir()
    reports.mkdir()
    (staging / "M01.html").write_text("novo", encoding="utf-8")
    (staging / "M02.html").write_text("novo", encoding="utf-8")
    (reports / "M01.html").write_text("versionado", encoding="utf-8")

    copied = drift_stage.publish_html_reports(staging, reports, refresh=False)

    assert copied == [reports / "M02.html"]  # so o que faltava
    assert (reports / "M01.html").read_text(encoding="utf-8") == "versionado"
    drift_stage.publish_html_reports(staging, reports, refresh=True)
    assert (reports / "M01.html").read_text(encoding="utf-8") == "novo"


# --- Pipeline ---------------------------------------------------------------------------


@pytest.mark.parametrize("defect", ["demo", "BILL_AMT1", "PAY_0"])
def test_blocked_batch_never_reaches_the_model(
    isolated: Path, pool: pd.DataFrame, defect: str
) -> None:
    corrupted = corrupt_batch(pool.head(500), load_config()["batches"]["corrupted"])
    if defect != "demo":
        corrupted = pool.head(500).copy()
        corrupted[defect] = corrupted[defect].astype(object)
        corrupted.loc[corrupted.index[0], defect] = "INVALID"
    calls = []

    def ingest() -> IngestedBatch:
        return IngestedBatch("bad", corrupted, "synthetic", 500, pool)

    outcome = run_monitored_batch(
        "bad",
        "test",
        ingest,
        lambda *args: calls.append(args) or ({}, {}),
        isolated / "q",
        isolated / "r",
        isolated / "pipeline.jsonl",
    )

    assert outcome.status == "blocked"
    assert calls == []
    assert "stage_status_prediction" not in outcome.metrics
    assert (isolated / "q" / "bad" / "failures.json").is_file()
    saved = json.loads((isolated / "r" / "bad.synthetic.json").read_text())
    assert saved["status"] == "blocked"


def test_drift_simulation_end_to_end(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_file = isolated / "synthetic.csv"
    generate_synthetic(12_000, seed=SEED).to_csv(raw_file, index=False)
    monkeypatch.setattr(loader, "synthetic_dataset_path", lambda: raw_file)
    ref, prod, model, report = (isolated / name for name in ("ref", "prod", "model", "drift"))
    prepare.prepare_data(prepare.DataSource.SYNTHETIC, ref, prod, isolated / "val")
    train_stage.train_model(ref, model, isolated / "model_report")

    summary = drift_stage.run_drift_simulation(
        ref, prod, model, report, isolated / "val", isolated / "q", isolated / "pipeline.jsonl"
    )

    # As expectativas foram calibradas no dataset real (no sintetico ate o M01 erra):
    # aqui so se confere que cada lote as registra; quem exige que sejam atendidas e
    # test_versioned_evidence_meets_every_declared_expectation, sobre a evidencia real.
    batches = summary["batches"]
    assert list(batches) == list(load_scenarios())
    assert {batch["status"] for batch in batches.values()} == {"success"}
    for batch_id, batch in batches.items():
        assert batch["expected"] == load_scenarios()[batch_id]["expected"]
        assert isinstance(batch["expectation_met"], bool)
    assert batches["M01"]["drifted"] == []
    assert batches["M05"]["drifted"] == []
    assert batches["M05"]["performance"]["auc"] < batches["M01"]["performance"]["auc"]
    assert (
        batches["M04"]["columns"]["LIMIT_BAL"]["psi"]
        > batches["M01"]["columns"]["LIMIT_BAL"]["psi"]
    )
    assert all((report / f"{batch_id}.synthetic.html").is_file() for batch_id in batches)
    saved = json.loads((report / "drift_summary.synthetic.json").read_text(encoding="utf-8"))
    assert saved["source"] == "synthetic"
    assert not (report / "drift_summary.json").exists()  # sintetico nunca vira evidencia

    runs = mlflow.tracking.MlflowClient().search_runs(
        [mlflow.get_experiment_by_name("tc04-credit-scoring-monitoring").experiment_id]
    )
    assert len(runs) == len(batches)
    expected_hash = hashlib.sha256((model / "model.joblib").read_bytes()).hexdigest()
    for run in runs:
        assert run.data.params["model_sha256"] == expected_hash
        artifact = Path(
            mlflow.artifacts.download_artifacts(
                run_id=run.info.run_id, artifact_path="lineage/lineage.json"
            )
        )
        assert (
            hashlib.sha256(artifact.read_bytes()).hexdigest() == run.data.params["lineage_sha256"]
        )
        lineage = json.loads(artifact.read_text())
        assert lineage["model_sha256"] == expected_hash
        assert lineage["model_metadata"]["threshold"] == float(run.data.params["threshold"])
        assert lineage["model_metadata"]["features"] == summary["monitored"]["features"]
        assert lineage["pipeline_config"] == load_config()

    events = [json.loads(line) for line in (isolated / "pipeline.jsonl").read_text().splitlines()]
    completed = [e for e in events if e["event"] == "stage_finished" and e["batch_id"] == "M01"]
    assert [e["stage"] for e in completed] == [
        "ingestion",
        "validation",
        "prediction",
        "drift",
        "performance",
    ]
    assert all(e["status"] == "success" and e["pipeline_run_id"] for e in completed)

    metadata_path = model / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["source_sha256"] = "stale"
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="origens diferentes"):
        drift_stage.load_context(ref, model, report)
