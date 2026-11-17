"""Testes da camada de observabilidade: logs, estagios, alertas, MLflow e dashboard."""

import base64
import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import mlflow
import pytest
import structlog
from prometheus_client import CollectorRegistry

from src.config import get_seed
from src.contracts.result import ContractResult, ContractViolationError, Violation
from src.data import loader
from src.data.synthetic import generate_synthetic
from src.monitoring.alerts import evaluate_alerts
from src.monitoring.dashboard import build_dashboard, render_dashboard
from src.monitoring.log import configure_logging, get_logger, read_run_events
from src.monitoring.model_metrics import build_model_metrics
from src.monitoring.prometheus import (
    PUSHGATEWAY_ENV,
    PUSHGATEWAY_PASSWORD_ENV,
    PUSHGATEWAY_USERNAME_ENV,
    build_registry,
    push_batch_metrics,
)
from src.monitoring.stages import BatchRecorder
from src.monitoring.tracking import BatchRun, load_batch_runs, log_batch_run
from src.pipeline import monitor, prepare
from src.pipeline.validate import DemoBatch

SEED = get_seed()


@pytest.fixture
def log_file(tmp_path: Path) -> Iterator[Path]:
    """Log centralizado em diretorio temporario; restaura o structlog ao final."""
    path = tmp_path / "logs" / "pipeline.jsonl"
    configure_logging("json", log_file=path)
    yield path
    structlog.reset_defaults()


@pytest.fixture
def tracking(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """MLflow isolado: banco e artefatos dentro de ``tmp_path``."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    return tmp_path


def _names(alerts: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(alert["name"], alert["severity"]) for alert in alerts]


# --- logs -----------------------------------------------------------------------------


def test_every_event_is_one_json_line_in_the_central_log(log_file: Path) -> None:
    logger = get_logger("test")
    logger.info("stage_ingestion", stage="ingestion", status="success", rows_in=10)
    logger.error("stage_validation", stage="validation", status="blocked", rows_in=10)

    lines = log_file.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    assert [event["event"] for event in events] == ["stage_ingestion", "stage_validation"]
    assert events[1]["level"] == "error"
    assert "timestamp" in events[0]


def test_run_events_are_filtered_by_pipeline_run(log_file: Path) -> None:
    logger = get_logger("test")
    with structlog.contextvars.bound_contextvars(pipeline_run_id="run-a"):
        logger.info("mine")
    with structlog.contextvars.bound_contextvars(pipeline_run_id="run-b"):
        logger.info("other", note="mentions run-a but belongs to run-b")

    assert [event["event"] for event in read_run_events("run-a", log_file)] == ["mine"]
    assert read_run_events("run-a", log_file.with_name("missing.jsonl")) == []


# --- estagios -------------------------------------------------------------------------


def test_recorder_measures_successful_stages() -> None:
    recorder = BatchRecorder("batch")
    with recorder.stage("ingestion") as stage:
        stage.rows_in = stage.rows_out = 100
    with recorder.stage("validation", rows_in=100) as stage:
        stage.rows_out = 100

    metrics = recorder.metrics()
    assert recorder.status == "success"
    assert metrics["stage_status_ingestion"] == metrics["stage_status_validation"] == 1.0
    assert metrics["rows_in"] == metrics["rows_out"] == 100
    assert metrics["pipeline_duration_s"] >= metrics["stage_duration_s_validation"] >= 0
    assert metrics["peak_memory_mb"] > 0
    assert "stage_status_prediction" not in metrics  # estagio que nao rodou nao aparece


def test_recorder_marks_contract_violation_as_blocked() -> None:
    result = ContractResult(50, [Violation("C4", "AGE", "in_range", 2)], [])
    recorder = BatchRecorder("batch")
    with (
        pytest.raises(ContractViolationError),
        recorder.stage("validation", rows_in=50),
    ):
        raise ContractViolationError("batch", result)

    metrics = recorder.metrics()
    assert recorder.status == "blocked"
    assert metrics["stage_status_validation"] == -1.0
    assert metrics["rows_out"] == 0


def test_recorder_marks_unexpected_error_as_failed_and_reraises() -> None:
    recorder = BatchRecorder("batch")
    with pytest.raises(RuntimeError), recorder.stage("ingestion"):
        raise RuntimeError("disco cheio")

    assert recorder.status == "failed"
    assert recorder.metrics()["stage_status_ingestion"] == 0.0


def test_recorder_rejects_unknown_stage() -> None:
    with pytest.raises(ValueError, match="desconhecido"), BatchRecorder("batch").stage("deploy"):
        pass


# --- alertas --------------------------------------------------------------------------


def test_alert_rules_use_configured_psi_thresholds() -> None:
    alerts = evaluate_alerts({"psi_LIMIT_BAL": 0.12, "psi_PAY_0": 0.26, "psi_score": 0.11})
    assert _names(alerts) == [
        ("psi_LIMIT_BAL", "warning"),
        ("psi_PAY_0", "critical"),
        ("psi_score", "warning"),
    ]


def test_model_metrics_adapter_emits_tracking_contract() -> None:
    metrics = build_model_metrics(
        {"PAY_0": 0.30, "LIMIT_BAL": 0.05},
        feature_ks_d={"PAY_0": 0.12},
        score_psi=0.26,
        baseline_auc=0.80,
        batch_auc=0.74,
        baseline_recall=0.70,
        batch_recall=0.58,
    )
    assert metrics == {
        "psi_PAY_0": 0.30,
        "psi_LIMIT_BAL": 0.05,
        "ks_d_PAY_0": 0.12,
        "psi_score": 0.26,
        "n_features_drifted": 1.0,
        "share_features_drifted": 0.5,
        "auc_roc": 0.74,
        "auc_drop": 0.06,
        "recall_default": 0.58,
        "recall_drop": 0.12,
    }


def test_model_metrics_omit_delayed_performance_without_labels() -> None:
    metrics = build_model_metrics({"PAY_0": 0.12})
    assert "auc_roc" not in metrics
    assert "recall_default" not in metrics
    assert "auc_drop" not in metrics
    assert "recall_drop" not in metrics


def test_model_metrics_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="PSI"):
        build_model_metrics({"PAY_0": float("nan")})
    with pytest.raises(ValueError, match="KS D"):
        build_model_metrics({}, feature_ks_d={"PAY_0": 1.2})


def test_alert_thresholds_include_score_auc_recall_and_feature_share() -> None:
    alerts = evaluate_alerts(
        {
            "psi_score": 0.25,
            "auc_drop": 0.03,
            "recall_drop": 0.05,
            "share_features_drifted": 0.20,
        }
    )
    assert [(alert["name"], alert["severity"]) for alert in alerts] == [
        ("psi_score", "critical"),
        ("auc_drop", "warning"),
        ("recall_drop", "warning"),
        ("share_features_drifted", "warning"),
    ]


def test_alert_rules_ignore_healthy_metrics() -> None:
    healthy = {"psi_PAY_0": 0.04, "psi_score": 0.02, "auc_drop": 0.01, "rows_in": 2400}
    assert evaluate_alerts({**healthy, "rows_expected": 2400}) == []


def test_auc_drop_is_critical() -> None:
    assert _names(evaluate_alerts({"auc_drop": 0.05})) == [("auc_drop", "critical")]


@pytest.mark.parametrize(
    ("status", "expected"),
    [("blocked", "batch_blocked"), ("failed", "stage_failure")],
)
def test_blocked_and_failed_batches_raise_critical_alerts(status: str, expected: str) -> None:
    assert _names(evaluate_alerts({}, status)) == [(expected, "critical")]


@pytest.mark.parametrize(
    ("rows", "alerted"), [(2400, False), (1700, False), (1600, True), (3200, True)]
)
def test_volume_outside_tolerance_raises_warning(rows: int, alerted: bool) -> None:
    """Tolerancia de 30% sobre 2400 linhas: 1680 a 3120 passam."""
    alerts = evaluate_alerts({"rows_in": rows, "rows_expected": 2400})
    assert _names(alerts) == ([("volume_anomaly", "warning")] if alerted else [])


# --- MLflow e dashboard ---------------------------------------------------------------


def test_batch_run_is_tracked_with_metrics_alerts_and_logs(tracking: Path) -> None:
    alerts = evaluate_alerts({}, "blocked")
    run_id = log_batch_run(
        "M99",
        scenario="unit_test",
        status="blocked",
        source="real",
        metrics={"rows_in": 10, "rows_out": 0},
        alerts=alerts,
        events=[{"event": "stage_validation", "status": "blocked"}],
    )

    [run] = load_batch_runs()
    assert (run.batch_id, run.scenario, run.status, run.source) == (
        "M99",
        "unit_test",
        "blocked",
        "real",
    )
    assert run.alerts == alerts
    assert run.metrics["batch_blocked"] == 1.0
    assert run.metrics["alerts_critical"] == 1.0
    logged = Path(mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="logs"))
    line = (logged / "pipeline.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(line)["event"] == "stage_validation"
    assert (tracking / "mlartifacts").is_dir()  # artefatos ao lado do banco, nao no cwd


def test_batch_run_rejects_unknown_status(tracking: Path) -> None:
    with pytest.raises(ValueError, match="Status"):
        log_batch_run("M99", status="ok")


def test_dashboard_shows_latest_run_per_batch_and_separates_sources(tracking: Path) -> None:
    log_batch_run("M01", status="failed", source="real", metrics={"stage_status_ingestion": 0})
    log_batch_run(
        "M01",
        status="success",
        source="real",
        metrics={"stage_status_ingestion": 1, "stage_duration_s_ingestion": 0.5, "rows_in": 2400},
    )
    log_batch_run("S01", status="success", source="synthetic")

    real = build_dashboard("real", tracking / "real.html").read_text("utf-8")
    synthetic = build_dashboard("synthetic", tracking / "synthetic.html").read_text("utf-8")
    assert "sucesso · 0.50 s" in real
    assert "<td class='failed'>falha</td>" not in real  # a execucao antiga saiu da tabela
    assert "1 com falha inesperada" in real  # mas segue contada no historico
    assert "S01" not in real
    assert "S01" in synthetic
    assert "M01" not in synthetic


def test_dashboard_default_path_never_overwrites_real_evidence(
    tracking: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.monitoring.dashboard.DASHBOARD_DIR", tracking / "reports")
    assert build_dashboard("real").name == "dashboard.html"
    assert build_dashboard("synthetic").name == "dashboard.synthetic.html"


def test_dashboard_escapes_dynamic_values() -> None:
    run = BatchRun(
        batch_id="<script>alert('x')</script>",
        scenario="s",
        status="blocked",
        source="real",
        started_ms=0,
        metrics={"stage_status_validation": -1.0, "alerts_critical": 1.0},
        alerts=[{"name": "batch_blocked", "severity": "critical", "action": "<b>agir</b>"}],
    )
    html = render_dashboard([run], "real")
    assert "<script>" not in html
    assert "<b>agir</b>" not in html
    assert "&lt;script&gt;" in html
    assert "bloqueado · 0.00 s" in html


# --- execucao monitorada fim a fim ----------------------------------------------------


def test_monitored_demo_end_to_end(
    tracking: Path, log_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_file = tracking / "synthetic.csv"
    generate_synthetic(8_000, seed=SEED).to_csv(raw_file, index=False)
    monkeypatch.setattr(loader, "synthetic_dataset_path", lambda: raw_file)
    dirs = {"reference_dir": tracking / "ref", "production_dir": tracking / "prod"}
    prepare.prepare_data(prepare.DataSource.SYNTHETIC, validation_report_dir=tracking / "r", **dirs)
    run_dirs = {
        **dirs,
        "quarantine_dir": tracking / "q",
        "report_dir": tracking / "r",
        "log_file": log_file,
    }

    valid = monitor.run_monitored_demo(DemoBatch.VALID, "test", **run_dirs)
    blocked = monitor.run_monitored_demo(DemoBatch.CORRUPTED, "test", **run_dirs)
    failed = monitor.run_monitored_demo(
        DemoBatch.VALID, "test", **{**run_dirs, "production_dir": tracking / "missing"}
    )

    assert (valid.status, valid.source, valid.alerts) == ("success", "synthetic", [])
    assert blocked.status == "blocked"
    assert _names(blocked.alerts) == [("batch_blocked", "critical")]
    assert failed.status == "failed"
    assert _names(failed.alerts) == [("stage_failure", "critical")]

    runs = {run.status: run for run in load_batch_runs()}
    assert runs["success"].metrics["rows_out"] == runs["success"].metrics["rows_in"] > 0
    assert runs["blocked"].metrics["stage_status_ingestion"] == 1.0
    assert runs["blocked"].metrics["stage_status_validation"] == -1.0
    assert runs["blocked"].metrics["rows_out"] == 0
    assert runs["blocked"].metrics["contract_violations_C4"] > 0
    assert runs["failed"].metrics["stage_status_ingestion"] == 0.0
    assert "stage_status_validation" not in runs["failed"].metrics

    logs = Path(mlflow.artifacts.download_artifacts(run_id=blocked.mlflow_run_id)) / "logs"
    events = [json.loads(line) for line in (logs / "pipeline.jsonl").read_text().splitlines()]
    assert {event["batch_id"] for event in events} == {"demo_corrupted"}
    assert {"stage_ingestion", "stage_validation", "alert", "pipeline_finished"} <= {
        event["event"] for event in events
    }


# --- Prometheus Pushgateway (camada opcional) -----------------------------------------


def _samples(registry: CollectorRegistry) -> dict[tuple[str, tuple[tuple[str, str], ...]], float]:
    return {
        (sample.name, tuple(sorted(sample.labels.items()))): sample.value
        for family in registry.collect()
        for sample in family.samples
    }


def test_batch_metrics_become_bounded_prometheus_series() -> None:
    registry = build_registry(
        scenario="inflation",
        status="blocked",
        metrics={
            "rows_in": 500,
            "stage_status_validation": -1,
            "stage_duration_s_validation": 0.05,
            "contract_violations": 7,
            "contract_violations_C4": 5,
            "psi_PAY_0": 0.31,
            "psi_score": 0.12,
            "ks_d_PAY_0": 0.2,
        },
        alerts=evaluate_alerts({}, "blocked"),
    )

    samples = _samples(registry)
    assert samples[("tc04_batch_rows_in", ())] == 500
    assert samples[("tc04_batch_status", ())] == -1
    assert samples[("tc04_stage_status", (("stage", "validation"),))] == -1
    assert samples[("tc04_stage_duration_seconds", (("stage", "validation"),))] == 0.05
    assert samples[("tc04_batch_contract_violations", ())] == 7  # total, sem label
    assert samples[("tc04_contract_violations", (("rule", "C4"),))] == 5
    assert samples[("tc04_feature_psi", (("feature", "PAY_0"),))] == 0.31
    assert samples[("tc04_batch_psi_score", ())] == 0.12  # score nao e feature
    assert samples[("tc04_feature_ks_d", (("feature", "PAY_0"),))] == 0.2
    assert samples[("tc04_batch_info", (("scenario", "inflation"),))] == 1
    alert = (
        ("action", "investigate_source_and_reprocess"),
        ("alert", "batch_blocked"),
        ("severity", "critical"),
    )
    assert samples[("tc04_batch_alert", alert)] == 1


def test_push_is_disabled_without_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PUSHGATEWAY_ENV, raising=False)
    assert not push_batch_metrics("M01", scenario="s", status="success", source="real", metrics={})


def test_unreachable_gateway_never_breaks_the_batch() -> None:
    pushed = push_batch_metrics(
        "M01",
        scenario="s",
        status="success",
        source="real",
        metrics={"rows_in": 1},
        gateway="http://127.0.0.1:1",
    )
    assert pushed is False


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, str]]]:
    """Pushgateway falso que exige o login ``tc04:segredo`` e guarda o que recebeu."""
    received: list[dict[str, str]] = []
    expected = "Basic " + base64.b64encode(b"tc04:segredo").decode()

    class Gateway(BaseHTTPRequestHandler):
        def do_PUT(self) -> None:  # noqa: N802 - nome exigido pelo http.server
            body = self.rfile.read(int(self.headers["Content-Length"])).decode()
            authorized = self.headers.get("Authorization") == expected
            received.append(
                {"method": self.command, "path": self.path, "body": body, "ok": str(authorized)}
            )
            self.send_response(200 if authorized else 401)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Gateway)
    Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv(PUSHGATEWAY_ENV, f"http://127.0.0.1:{server.server_port}")
    monkeypatch.delenv(PUSHGATEWAY_USERNAME_ENV, raising=False)
    monkeypatch.delenv(PUSHGATEWAY_PASSWORD_ENV, raising=False)
    yield received
    server.shutdown()


def _push() -> bool:
    return push_batch_metrics(
        "M01", scenario="control", status="success", source="real", metrics={"rows_in": 2400}
    )


def test_push_sends_one_group_per_batch_and_source(
    gateway: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PUSHGATEWAY_USERNAME_ENV, "tc04")
    monkeypatch.setenv(PUSHGATEWAY_PASSWORD_ENV, "segredo")

    assert _push() is True
    [request] = gateway
    assert request["ok"] == "True"  # o login foi enviado como Basic Auth
    assert request["method"] == "PUT"  # substitui o grupo: series antigas nao sobrevivem
    assert request["path"] == "/metrics/job/tc04_batch/batch_id/M01/source/real"
    assert "tc04_batch_rows_in 2400.0" in request["body"]


def test_rejected_login_never_breaks_the_batch(gateway: list[dict[str, str]]) -> None:
    """Sem usuario e senha, o Pushgateway responde 401 e o lote segue."""
    assert _push() is False
    assert [request["ok"] for request in gateway] == ["False"]


def test_wrong_password_never_breaks_the_batch(
    gateway: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PUSHGATEWAY_USERNAME_ENV, "tc04")
    monkeypatch.setenv(PUSHGATEWAY_PASSWORD_ENV, "errada")
    assert _push() is False
