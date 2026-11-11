"""Auditoria de vies e ablacao (ADR 13)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.data import loader
from src.data.schema import TARGET_COLUMN
from src.data.synthetic import generate_synthetic
from src.models.ablation import _variant_config, decide, variant_name
from src.models.fairness import audit, group_labels, group_metrics
from src.pipeline import audit as audit_stage
from src.pipeline import prepare
from src.pipeline import train as train_stage

SEED = 42
FAIRNESS = {
    "attributes": ["SEX"],
    "age_bins": [18, 30, 40, 50, 101],
    "impact_ratio_min": 0.8,
    "min_group_size": 4,
}


def _frame() -> pd.DataFrame:
    # Homens: 4 bons pagadores, 2 aprovados. Mulheres: 4 bons pagadores, 4 aprovados.
    return pd.DataFrame(
        {
            "SEX": [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
            "AGE": [25, 35, 45, 55, 29, 30, 39, 40, 50, 100],
            TARGET_COLUMN: [0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        }
    )


APPROVED = np.array([True, True, False, False, False, True, True, True, True, False])


def test_group_metrics_by_hand() -> None:
    rows = {row["group"]: row for row in group_metrics(_frame(), APPROVED, "SEX", FAIRNESS)}

    assert rows["masculino"]["approval_rate"] == 0.4
    assert rows["feminino"]["approval_rate"] == 0.8
    assert rows["masculino"]["impact_ratio"] == 0.5
    assert rows["masculino"]["good_payer_approval"] == 0.5
    assert rows["feminino"]["good_payer_ratio"] == 1.0
    assert rows["masculino"]["recall_default"] == 1.0


def test_audit_flags_four_fifths_violation() -> None:
    scores = np.where(APPROVED, 0.1, 0.9)
    summary = audit(_frame(), scores, threshold=0.5, config=FAIRNESS)["SEX"]
    assert summary["min_impact_ratio"] == 0.5
    assert summary["below_four_fifths"]


def test_small_groups_do_not_set_the_reference() -> None:
    frame = pd.concat([_frame(), pd.DataFrame({"SEX": [3], "AGE": [30], TARGET_COLUMN: [0]})])
    approved = np.append(APPROVED, True)
    rows = {row["group"]: row for row in group_metrics(frame, approved, "SEX", FAIRNESS)}

    assert not rows["desconhecido"]["conclusive"]
    assert rows["feminino"]["impact_ratio"] == 1.0


def test_age_bands_follow_configured_bins() -> None:
    labels = group_labels(_frame(), "AGE", FAIRNESS)
    assert list(labels.cat.categories) == ["18-29", "30-39", "40-49", "50+"]
    assert labels.iloc[4] == "18-29"
    assert labels.iloc[5] == "30-39"
    assert labels.iloc[9] == "50+"


@pytest.mark.parametrize(
    ("losses", "expected"),
    [
        ({"without_A_B": 0.005, "without_A": 0.02, "without_B": 0.0}, ["A", "B"]),
        ({"without_A_B": 0.03, "without_A": 0.02, "without_B": 0.0}, ["B"]),
        ({"without_A_B": 0.03, "without_A": 0.02, "without_B": 0.015}, []),
    ],
)
def test_ablation_decision_follows_declared_criterion(
    losses: dict[str, float], expected: list[str]
) -> None:
    variants = {name: {"auc_loss": loss} for name, loss in losses.items()}
    assert decide(variants, ["A", "B"], max_loss=0.01) == expected


def test_variant_config_restores_candidates_before_dropping() -> None:
    model_config = {"excluded_columns": ["ID", "SEX", "AGE", "EDUCATION"]}
    config = _variant_config(model_config, ["AGE", "EDUCATION"], ("AGE",))
    assert config["excluded_columns"] == ["ID", "SEX", "AGE"]
    assert variant_name(()) == "all"
    assert variant_name(("AGE", "EDUCATION")) == "without_AGE_EDUCATION"


def test_audit_stage_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_file = tmp_path / "synthetic.csv"
    generate_synthetic(6_000, seed=SEED).to_csv(raw_file, index=False)
    monkeypatch.setattr(loader, "synthetic_dataset_path", lambda: raw_file)
    ref, model, report = tmp_path / "ref", tmp_path / "model", tmp_path / "report"
    prepare.prepare_data(prepare.DataSource.SYNTHETIC, ref, tmp_path / "prod", tmp_path / "val")
    train_stage.train_model(ref, model, report)

    result = audit_stage.audit_model(ref, model, report)

    candidates = load_config()["ablation"]["candidates"]
    assert len(result["ablation"]["variants"]) == 2 ** len(candidates)
    assert set(result["ablation"]["remove"]) <= set(candidates)
    assert set(result["fairness"]["attributes"]) == set(load_config()["fairness"]["attributes"])
    saved = json.loads((report / "fairness_audit.synthetic.json").read_text())
    assert saved["evaluated_on"] == "test"
    assert (report / "ablation.synthetic.json").is_file()


def test_audit_requires_trained_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_file = tmp_path / "synthetic.csv"
    generate_synthetic(3_000, seed=SEED).to_csv(raw_file, index=False)
    monkeypatch.setattr(loader, "synthetic_dataset_path", lambda: raw_file)
    ref = tmp_path / "ref"
    prepare.prepare_data(prepare.DataSource.SYNTHETIC, ref, tmp_path / "prod", tmp_path / "val")

    with pytest.raises(FileNotFoundError, match="train_model"):
        audit_stage.audit_model(ref, tmp_path / "missing", tmp_path / "report")
