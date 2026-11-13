"""Estagio de validacao: contrato -> relatorio -> (quarentena + bloqueio) ou liberacao.

Lote reprovado NAO chega ao modelo: vai inteiro para ``data/quarantine/<batch_id>/``,
gera log ``status=blocked`` com alerta critico e levanta ``ContractViolationError`` (o
script traduz em exit code != 0). O lote inteiro e bloqueado, nao so as linhas invalidas:
filtrar em silencio esconderia a falha de origem e distorceria a deteccao de drift.
"""

import time
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import PRODUCTION_DIR, QUARANTINE_DIR, REFERENCE_DIR, REPORTS_DIR, load_config
from src.contracts.corruption import corrupt_batch
from src.contracts.result import ContractResult, ContractViolationError
from src.contracts.validate import validate_batch
from src.monitoring.log import get_logger, log_pipeline_event
from src.pipeline.io import read_prepared, read_split_metadata, report_name, write_json

logger = get_logger(__name__)

VALIDATION_REPORT_DIR = REPORTS_DIR / "validation"
QUARANTINE_BATCH_FILE = "batch.parquet"
QUARANTINE_REPORT_FILE = "failures.json"


class DemoBatch(StrEnum):
    """Lotes da demonstracao do contrato."""

    VALID = "valid"
    CORRUPTED = "corrupted"


def validate_stage(
    batch: pd.DataFrame,
    batch_id: str,
    source: str,
    expected_rows: int | None = None,
    reference: pd.DataFrame | None = None,
    quarantine_dir: Path | None = QUARANTINE_DIR,
    report_dir: Path = VALIDATION_REPORT_DIR,
) -> ContractResult:
    """Valida um lote, grava o relatorio e bloqueia se houver violacao critica.

    Args:
        batch: Lote a validar.
        batch_id: Identificador do lote (nome do relatorio e da pasta de quarentena).
        source: ``real`` ou ``synthetic`` (relatorio do sintetico nao e versionado).
        expected_rows: Volume esperado (aviso W2).
        reference: Referencia para o aviso W3.
        quarantine_dir: Raiz da quarentena; ``None`` nao copia o lote (usado na referencia,
            que nao e um lote de producao).
        report_dir: Destino do relatorio JSON.

    Returns:
        Resultado da validacao, se o lote passou.

    Raises:
        ContractViolationError: Se alguma regra critica foi violada.
    """
    started = time.perf_counter()
    result = validate_batch(batch, load_config()["contract"], expected_rows, reference)
    write_json(report_dir / report_name(f"{batch_id}.json", source), _report(batch_id, result))
    for warning in result.warnings:
        logger.warning("contract_warning", batch_id=batch_id, **asdict(warning))
    if not result.passed and quarantine_dir is not None:
        _quarantine(batch, result, quarantine_dir / batch_id)
    _log(batch_id, result, time.perf_counter() - started)
    if not result.passed:
        raise ContractViolationError(batch_id, result)
    return result


def validate_demo_batch(
    kind: DemoBatch,
    reference_dir: Path = REFERENCE_DIR,
    production_dir: Path = PRODUCTION_DIR,
    quarantine_dir: Path = QUARANTINE_DIR,
    report_dir: Path = VALIDATION_REPORT_DIR,
) -> ContractResult:
    """Demonstracao do contrato: um lote valido passa; o corrompido e bloqueado.

    Ambos partem de uma amostra do pool de producao com a seed global.

    Raises:
        FileNotFoundError: Se os dados nao tiverem sido preparados.
        ContractViolationError: No lote corrompido (comportamento esperado).
    """
    config = load_config()
    pool = read_prepared(production_dir / "pool.parquet")
    reference = read_prepared(reference_dir / "train.parquet")
    source = read_split_metadata(reference_dir)["source"]
    batches = config["batches"]
    rows = batches["rows"] if kind is DemoBatch.VALID else batches["corrupted"]["rows"]
    batch = pool.sample(n=rows, random_state=config["seed"])
    if kind is DemoBatch.CORRUPTED:
        batch = corrupt_batch(batch, batches["corrupted"])
    return validate_stage(
        batch, f"demo_{kind}", source, rows, reference, quarantine_dir, report_dir
    )


def _report(batch_id: str, result: ContractResult) -> dict[str, Any]:
    return {"batch_id": batch_id, **result.to_dict()}


def _quarantine(batch: pd.DataFrame, result: ContractResult, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    batch.to_parquet(target / QUARANTINE_BATCH_FILE, index=False)
    write_json(target / QUARANTINE_REPORT_FILE, result.to_dict())


def _log(batch_id: str, result: ContractResult, duration: float) -> None:
    fields = {
        "stage": "validation",
        "batch_id": batch_id,
        "rows_in": result.rows,
        "duration_s": round(duration, 3),
    }
    if result.passed:
        logger.info("stage_validation", status="success", rows_out=result.rows, **fields)
        log_pipeline_event("stage_validation", status="success", rows_out=result.rows, **fields)
        return
    logger.error(
        "stage_validation",
        status="blocked",
        rows_out=0,
        rules_violated=result.rules_violated,
        **fields,
    )
    logger.critical("alert", severity="critical", reason="contract_violation", **fields)
    log_pipeline_event(
        "stage_validation",
        status="blocked",
        rows_out=0,
        rules_violated=result.rules_violated,
        **fields,
    )
