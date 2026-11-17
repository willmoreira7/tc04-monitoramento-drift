"""Rastreamento no MLflow: uma execucao por lote, inclusive bloqueados e com falha.

O banco local fica em ``mlflow.db`` na raiz do projeto -- o mesmo que ``uv run mlflow ui``
abre por padrao -- e os artefatos em ``mlartifacts/``. Ambos sao ignorados pelo Git; a
evidencia versionada e o dashboard HTML (``src/monitoring/dashboard.py``).
"""

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlflow
from mlflow.entities import ViewType
from mlflow.tracking import MlflowClient

from src.config import PROJECT_ROOT
from src.monitoring.alerts import SEVERITY_CRITICAL, SEVERITY_WARNING, Alert
from src.monitoring.stages import STATUS_BLOCKED, STATUS_FAILED, STATUS_VALUES

EXPERIMENT_NAME = "tc04-credit-scoring-monitoring"
TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"
SQLITE_PREFIX = "sqlite:///"
TRACKING_URI = f"{SQLITE_PREFIX}{(PROJECT_ROOT / 'mlflow.db').as_posix()}"
ARTIFACTS_DIR = "mlartifacts"
SOURCE_UNKNOWN = "unknown"
MAX_RUNS = 1000


@dataclass(frozen=True)
class BatchRun:
    """Execucao de um lote lida do MLflow, ja pronta para o dashboard."""

    batch_id: str
    scenario: str
    status: str
    source: str
    started_ms: int
    metrics: dict[str, float]
    alerts: list[Alert]


def configure_tracking() -> str:
    """Aponta o MLflow para o banco local (ou ``MLFLOW_TRACKING_URI``) e cria o experimento.

    Com SQLite, os artefatos ficam ao lado do banco. O padrao do MLflow seria ``./mlruns``
    relativo ao diretorio corrente, que muda conforme de onde o script e chamado.

    Returns:
        Id do experimento de monitoramento.
    """
    uri = os.environ.get(TRACKING_URI_ENV, TRACKING_URI)
    mlflow.set_tracking_uri(uri)
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    if experiment is None:
        artifacts = None
        if uri.startswith(SQLITE_PREFIX):
            database = Path(uri.removeprefix(SQLITE_PREFIX))
            artifacts = (database.resolve().parent / ARTIFACTS_DIR).as_uri()
        experiment_id = mlflow.create_experiment(EXPERIMENT_NAME, artifact_location=artifacts)
    else:
        experiment_id = experiment.experiment_id
    mlflow.set_experiment(experiment_id=experiment_id)
    return experiment_id


def log_batch_run(
    batch_id: str,
    *,
    scenario: str = "unspecified",
    status: str,
    source: str = SOURCE_UNKNOWN,
    metrics: Mapping[str, float] | None = None,
    params: Mapping[str, str | int | float] | None = None,
    alerts: Sequence[Alert] = (),
    artifacts: Mapping[str, Path] | None = None,
    events: Sequence[Mapping[str, Any]] = (),
    error_type: str | None = None,
) -> str:
    """Registra uma execucao por lote.

    So agregados entram no MLflow: metricas, alertas, relatorios e eventos de log. Nunca
    linhas do lote nem valores de features.

    Args:
        batch_id: Identificador do lote (nome da execucao e tag).
        scenario: Cenario de drift do lote, ou o nome da demonstracao.
        status: ``success``, ``failed`` ou ``blocked``.
        source: ``real`` ou ``synthetic``; ``unknown`` se a ingestao falhou antes de saber.
        metrics: Metricas numericas do lote.
        params: Parametros da execucao.
        alerts: Alertas disparados (``evaluate_alerts``).
        artifacts: Arquivos a anexar, por subpasta; os inexistentes sao ignorados.
        events: Eventos do log centralizado desta execucao, anexados como JSONL.
        error_type: Classe da excecao, em lotes bloqueados ou com falha.

    Returns:
        Id da execucao no MLflow.

    Raises:
        ValueError: Se ``status`` nao for um dos tres valores aceitos.
    """
    if status not in STATUS_VALUES:
        raise ValueError(f"Status inválido: {status}")
    configure_tracking()
    alert_list = list(alerts)
    with mlflow.start_run(run_name=batch_id) as run:
        mlflow.set_tags(
            {
                "batch_id": batch_id,
                "scenario": scenario,
                "status": status,
                "source": source,
                "alerts": json.dumps(alert_list, ensure_ascii=False),
            }
        )
        if error_type:
            mlflow.set_tag("error_type", error_type)
        if params:
            mlflow.log_params({key: str(value) for key, value in params.items()})
        mlflow.log_metrics(
            {
                **{key: float(value) for key, value in (metrics or {}).items()},
                "alerts_warning": _count(alert_list, SEVERITY_WARNING),
                "alerts_critical": _count(alert_list, SEVERITY_CRITICAL),
                "batch_blocked": float(status == STATUS_BLOCKED),
                "batch_failed": float(status == STATUS_FAILED),
            }
        )
        mlflow.log_dict(alert_list, "monitoring/alerts.json")
        if events:
            lines = (json.dumps(event, ensure_ascii=False, default=str) for event in events)
            mlflow.log_text("\n".join(lines) + "\n", "logs/pipeline.jsonl")
        for name, artifact in (artifacts or {}).items():
            if artifact.is_file():
                mlflow.log_artifact(str(artifact), artifact_path=name)
        return run.info.run_id


def load_batch_runs() -> list[BatchRun]:
    """Todas as execucoes do experimento de monitoramento, da mais recente para a mais antiga."""
    experiment_id = configure_tracking()
    runs = MlflowClient().search_runs(
        [experiment_id],
        run_view_type=ViewType.ACTIVE_ONLY,
        max_results=MAX_RUNS,
        order_by=["attributes.start_time DESC"],
    )
    return [
        BatchRun(
            batch_id=run.data.tags.get("batch_id", run.info.run_name),
            scenario=run.data.tags.get("scenario", "unspecified"),
            status=run.data.tags.get("status", SOURCE_UNKNOWN),
            source=run.data.tags.get("source", SOURCE_UNKNOWN),
            started_ms=run.info.start_time,
            metrics=dict(run.data.metrics),
            alerts=json.loads(run.data.tags.get("alerts", "[]")),
        )
        for run in runs
    ]


def _count(alerts: Sequence[Alert], severity: str) -> float:
    return float(sum(alert["severity"] == severity for alert in alerts))
