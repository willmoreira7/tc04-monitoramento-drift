"""Tracking de observabilidade batch no MLflow e regras de alerta."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import mlflow
from mlflow.entities import ViewType
from mlflow.tracking import MlflowClient

from src.config import LOGS_DIR, REPORTS_DIR, load_config

EXPERIMENT_NAME = "tc04-credit-scoring-monitoring"
TRACKING_URI = f"sqlite:///{(LOGS_DIR / 'mlflow.db').as_posix()}"


def configure_tracking() -> None:
    """Configura tracking local em SQLite e cria o experimento de monitoramento."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", TRACKING_URI))
    mlflow.set_experiment(EXPERIMENT_NAME)


def evaluate_alerts(
    metrics: Mapping[str, float], config: Mapping[str, Any] | None = None
) -> list[dict[str, str]]:
    """Avalia regras configuradas e retorna alertas sem efeitos colaterais."""
    rules = (config or load_config())["monitoring"]["thresholds"]
    alerts: list[dict[str, str]] = []
    for key, value in metrics.items():
        if key.startswith("psi_") and key != "psi_score":
            if value >= rules["psi_critical"]:
                alerts.append({"name": key, "severity": "critical", "action": "investigate_drift"})
            elif value >= rules["psi_warning"]:
                alerts.append({"name": key, "severity": "warning", "action": "monitor_trend"})
        if key == "psi_score" and value >= rules["score_psi_warning"]:
            alerts.append(
                {"name": key, "severity": "warning", "action": "review_score_distribution"}
            )
        if key == "auc_drop" and value >= rules["auc_drop_critical"]:
            alerts.append({"name": key, "severity": "critical", "action": "review_performance"})
    return alerts


def log_batch_run(
    batch_id: str,
    *,
    scenario: str = "unspecified",
    status: str,
    metrics: Mapping[str, float] | None = None,
    params: Mapping[str, str | int | float] | None = None,
    alerts: list[dict[str, str]] | None = None,
    artifacts: Mapping[str, str | Path] | None = None,
    error_type: str | None = None,
) -> str:
    """Registra uma execução por lote, inclusive lotes bloqueados ou com falha.

    Artefatos são anexados apenas quando são arquivos existentes. Não registrar linhas
    individuais, payloads ou valores de features.
    """
    if status not in {"success", "failed", "blocked"}:
        raise ValueError(f"Status inválido: {status}")
    configure_tracking()
    with mlflow.start_run(run_name=batch_id) as run:
        mlflow.set_tags({"batch_id": batch_id, "scenario": scenario, "status": status})
        if error_type:
            mlflow.set_tag("error_type", error_type)
        if params:
            mlflow.log_params({key: str(value) for key, value in params.items()})
        numeric = {key: float(value) for key, value in (metrics or {}).items()}
        if numeric:
            mlflow.log_metrics(numeric)
        alert_list = alerts or []
        mlflow.log_metrics(
            {
                "alerts_warning": float(
                    sum(alert["severity"] == "warning" for alert in alert_list)
                ),
                "alerts_critical": float(
                    sum(alert["severity"] == "critical" for alert in alert_list)
                ),
                "batch_blocked": float(status == "blocked"),
                "batch_failed": float(status == "failed"),
            }
        )
        mlflow.log_dict(alert_list, "monitoring/alerts.json")
        for name, artifact in (artifacts or {}).items():
            path = Path(artifact)
            if path.is_file():
                mlflow.log_artifact(str(path), artifact_path=name)
        return run.info.run_id


def build_dashboard(output: Path | None = None) -> Path:
    """Gera dashboard HTML estático a partir das runs do experimento local."""
    configure_tracking()
    client = MlflowClient()
    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    runs = (
        client.search_runs(
            [experiment.experiment_id],
            run_view_type=ViewType.ACTIVE_ONLY,
            max_results=1000,
            order_by=["attributes.start_time DESC"],
        )
        if experiment
        else []
    )
    records = []
    for run in runs:
        metrics = {key: round(value, 6) for key, value in run.data.metrics.items()}
        records.append(
            {
                "batch_id": run.data.tags.get("batch_id", run.info.run_name),
                "scenario": run.data.tags.get("scenario", "unspecified"),
                "status": run.data.tags.get("status", "unknown"),
                "started": run.info.start_time,
                "metrics": metrics,
            }
        )
    destination = output or REPORTS_DIR / "monitoring" / "dashboard.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{_escape(value)}</td>"
            for value in (
                record["batch_id"],
                record["scenario"],
                record["status"],
                json.dumps(record["metrics"], ensure_ascii=False, sort_keys=True),
            )
        )
        + "</tr>"
        for record in records
    )
    destination.write_text(
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width'><title>Monitoramento TC04</title>"
        "<style>body{font:15px system-ui;margin:2rem;color:#17202a}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ccd1d1;padding:.6rem;text-align:left}th{background:#eaf2f8}"
        ".success{color:#176b36}.blocked,.failed{color:#a93226}</style>"
        f"<h1>Monitoramento de pipelines e modelos</h1><p>Execuções: {len(records)}. "
        "Fonte: MLflow local. Métricas de performance dependem da disponibilidade de rótulos.</p>"
        "<table><thead><tr><th>Lote</th><th>Cenário</th><th>Status</th><th>Métricas agregadas</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></html>",
        encoding="utf-8",
    )
    return destination


def _escape(value: object) -> str:
    """Escapa conteúdo dinâmico para HTML."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
