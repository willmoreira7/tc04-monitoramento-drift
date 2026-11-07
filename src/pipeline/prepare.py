"""Estagio de preparacao: carga -> limpeza -> split -> gravacao.

Grava a referencia em ``data/reference/`` e o pool em ``data/production/``, mais um
``split_metadata.json`` com contagens, taxas e o hash do arquivo de origem.
"""

import time
from pathlib import Path
from typing import Any

from src.config import PRODUCTION_DIR, REFERENCE_DIR, get_seed, load_config
from src.data.cleaning import clean_reference
from src.data.download import sha256_of
from src.data.loader import DataSource, load_raw, source_path
from src.data.schema import TARGET_COLUMN
from src.data.split import DataSplit, default_rate_gap_pp, split_dataset
from src.monitoring.log import get_logger
from src.pipeline.io import write_json

logger = get_logger(__name__)

METADATA_FILE = "split_metadata.json"


class SplitBalanceError(RuntimeError):
    """Referencia e producao ficaram com inadimplencia diferente demais."""


def prepare_data(
    source: DataSource = DataSource.REAL,
    reference_dir: Path = REFERENCE_DIR,
    production_dir: Path = PRODUCTION_DIR,
) -> dict[str, Any]:
    """Executa o estagio de preparacao e grava os conjuntos em Parquet.

    Args:
        source: Dataset real ou sintetico.
        reference_dir: Destino de treino, validacao e teste.
        production_dir: Destino do pool de producao.

    Returns:
        Metadados do split (tambem gravados em JSON).

    Raises:
        SplitBalanceError: Se a diferenca de inadimplencia passar do limite configurado.
    """
    started = time.perf_counter()
    config = load_config()
    raw = load_raw(source)
    cleaned, cleaning_report = clean_reference(raw, config["cleaning"])
    logger.info("stage_cleaning", status="success", **cleaning_report.to_dict())

    split = split_dataset(cleaned, config["split"], get_seed())
    gap = default_rate_gap_pp(split)
    if gap > config["split"]["max_default_rate_gap_pp"]:
        raise SplitBalanceError(f"Inadimplencia difere {gap:.2f} p.p. entre ref. e producao")

    metadata = _metadata(source, cleaning_report.to_dict(), split, gap)
    _write(split, metadata, reference_dir, production_dir)
    logger.info(
        "stage_prepare",
        status="success",
        source=str(source),
        rows_in=len(raw),
        rows_out=len(cleaned),
        duration_s=round(time.perf_counter() - started, 3),
    )
    return metadata


def _metadata(
    source: DataSource, cleaning: dict[str, int], split: DataSplit, gap: float
) -> dict[str, Any]:
    subsets = {
        name: {"rows": len(frame), "default_rate": round(float(frame[TARGET_COLUMN].mean()), 4)}
        for name, frame in split.as_dict().items()
    }
    return {
        "source": str(source),
        "source_sha256": sha256_of(source_path(source)),
        "seed": get_seed(),
        "cleaning": cleaning,
        "subsets": subsets,
        "default_rate_gap_pp": round(gap, 4),
    }


def _write(
    split: DataSplit, metadata: dict[str, Any], reference_dir: Path, production_dir: Path
) -> None:
    reference_dir.mkdir(parents=True, exist_ok=True)
    production_dir.mkdir(parents=True, exist_ok=True)
    for name in ("train", "validation", "test"):
        getattr(split, name).to_parquet(reference_dir / f"{name}.parquet", index=False)
    split.production_pool.to_parquet(production_dir / "pool.parquet", index=False)
    metadata_path = reference_dir / METADATA_FILE
    write_json(metadata_path, metadata)
