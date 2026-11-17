"""Execucao monitorada de um lote: estagios medidos, alertas avaliados, run no MLflow.

E o ponto em que o pipeline encontra a observabilidade. Hoje cobre ingestao e validacao
do lote de demonstracao; predicao, drift e performance entram como novos blocos
``recorder.stage(...)`` quando a Etapa 2 existir, sem mudar o restante.
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from src.config import PRODUCTION_DIR, QUARANTINE_DIR, REFERENCE_DIR
from src.contracts.result import ContractResult, ContractViolationError
from src.monitoring.alerts import SEVERITY_CRITICAL, Alert, evaluate_alerts
from src.monitoring.log import PIPELINE_LOG, get_logger, read_run_events
from src.monitoring.prometheus import push_batch_metrics
from src.monitoring.stages import STATUS_FAILED, BatchRecorder
from src.monitoring.tracking import SOURCE_UNKNOWN, log_batch_run
from src.pipeline.io import report_name
from src.pipeline.validate import (
    VALIDATION_REPORT_DIR,
    DemoBatch,
    ingest_demo_batch,
    validate_stage,
)

logger = get_logger(__name__)


@dataclass
class BatchOutcome:
    """Resultado de uma execucao monitorada.

    Attributes:
        batch_id: Identificador do lote.
        status: ``success``, ``failed`` ou ``blocked``.
        source: ``real``, ``synthetic`` ou ``unknown`` (ingestao falhou antes de saber).
        alerts: Alertas disparados.
        mlflow_run_id: Execucao registrada no MLflow.
    """

    batch_id: str
    status: str
    source: str = SOURCE_UNKNOWN
    alerts: list[Alert] = field(default_factory=list)
    mlflow_run_id: str = ""


def run_monitored_demo(
    kind: DemoBatch,
    scenario: str,
    reference_dir: Path = REFERENCE_DIR,
    production_dir: Path = PRODUCTION_DIR,
    quarantine_dir: Path = QUARANTINE_DIR,
    report_dir: Path = VALIDATION_REPORT_DIR,
    log_file: Path = PIPELINE_LOG,
) -> BatchOutcome:
    """Roda o lote de demonstracao pelos estagios e registra a execucao no MLflow.

    Nenhuma excecao escapa: lote bloqueado e falha inesperada viram ``status`` no
    resultado, com a execucao registrada -- e o que faz o lote corrompido e a falha de
    ingestao aparecerem no dashboard em vez de sumirem.

    Args:
        kind: Lote valido ou corrompido.
        scenario: Rotulo do cenario, gravado como tag da execucao.
        reference_dir: Diretorio da referencia.
        production_dir: Diretorio do pool de producao.
        quarantine_dir: Raiz da quarentena.
        report_dir: Destino do relatorio de validacao.
        log_file: Log centralizado de onde os eventos da execucao sao lidos.

    Returns:
        Status, alertas e id da execucao no MLflow.
    """
    batch_id = f"demo_{kind}"
    pipeline_run_id = uuid.uuid4().hex
    outcome = BatchOutcome(batch_id, STATUS_FAILED)
    recorder = BatchRecorder(batch_id)
    extra_metrics: dict[str, float] = {}
    error_type = None
    with structlog.contextvars.bound_contextvars(
        batch_id=batch_id, pipeline_run_id=pipeline_run_id
    ):
        try:
            with recorder.stage("ingestion") as stage:
                ingested = ingest_demo_batch(kind, reference_dir, production_dir)
                stage.rows_in = stage.rows_out = len(ingested.batch)
            outcome.source = ingested.source
            extra_metrics["rows_expected"] = float(ingested.expected_rows)
            with recorder.stage("validation", rows_in=len(ingested.batch)) as stage:
                result = validate_stage(
                    ingested.batch,
                    batch_id,
                    ingested.source,
                    ingested.expected_rows,
                    ingested.reference,
                    quarantine_dir,
                    report_dir,
                )
                stage.rows_out = result.rows
            extra_metrics |= _contract_metrics(result)
        except ContractViolationError as error:
            error_type = type(error).__name__
            extra_metrics |= _contract_metrics(error.result)
        except Exception as error:  # noqa: BLE001 - falha vira run "failed", nao some
            error_type = type(error).__name__
            logger.exception("pipeline_failed", error_type=error_type)
        outcome.status = recorder.status
        metrics = recorder.metrics() | extra_metrics
        outcome.alerts = evaluate_alerts(metrics, outcome.status)
        for alert in outcome.alerts:
            log = logger.critical if alert["severity"] == SEVERITY_CRITICAL else logger.warning
            log("alert", **alert)
        logger.info(
            "pipeline_finished",
            status=outcome.status,
            duration_s=round(metrics["pipeline_duration_s"], 3),
            alerts=len(outcome.alerts),
        )
    outcome.mlflow_run_id = log_batch_run(
        batch_id,
        scenario=scenario,
        status=outcome.status,
        source=outcome.source,
        metrics=metrics,
        alerts=outcome.alerts,
        artifacts={
            "validation": report_dir / report_name(f"{batch_id}.json", outcome.source),
        },
        events=read_run_events(pipeline_run_id, log_file),
        error_type=error_type,
    )
    push_batch_metrics(
        batch_id,
        scenario=scenario,
        status=outcome.status,
        source=outcome.source,
        metrics=metrics,
        alerts=outcome.alerts,
    )
    return outcome


def _contract_metrics(result: ContractResult) -> dict[str, float]:
    """Violacoes e avisos do contrato, no total e por regra."""
    metrics = {
        "contract_violations": float(sum(v.cases for v in result.violations)),
        "contract_warnings": float(sum(w.cases for w in result.warnings)),
    }
    for prefix, items in (("violations", result.violations), ("warnings", result.warnings)):
        for item in items:
            key = f"contract_{prefix}_{item.rule}"
            metrics[key] = metrics.get(key, 0.0) + item.cases
    return metrics
