"""Estagio de treino: le a referencia, compara candidatos, promove e grava.

Grava o artefato em ``models/baseline/`` (nao versionado) e a comparacao em
``reports/model/model_comparison.json`` (versionado: so metricas agregadas).
"""

import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib

from src.config import MODELS_DIR, REFERENCE_DIR, REPORTS_DIR, get_seed, load_config
from src.models.train import (
    CandidateResult,
    evaluate_on_test,
    feature_columns,
    select_model,
    train_candidates,
)
from src.monitoring.log import get_logger
from src.pipeline.io import read_prepared, read_split_metadata, report_name, write_json

logger = get_logger(__name__)

MODEL_FILE = "model.joblib"
MODEL_METADATA_FILE = "metadata.json"
COMPARISON_FILE = "model_comparison.json"


def train_model(
    reference_dir: Path = REFERENCE_DIR,
    model_dir: Path = MODELS_DIR / "baseline",
    report_dir: Path = REPORTS_DIR / "model",
) -> dict[str, Any]:
    """Executa o estagio de treino e devolve o resumo da comparacao.

    Raises:
        FileNotFoundError: Se a referencia nao tiver sido preparada.
    """
    started = time.perf_counter()
    config = load_config()["model"]
    train, validation, test = (
        read_prepared(reference_dir / f"{name}.parquet") for name in ("train", "validation", "test")
    )
    results = train_candidates(train, validation, config, get_seed())
    evaluate_on_test(results, test, config)
    promoted = select_model(results, config)

    summary = _summary(results, promoted, feature_columns(train, config), reference_dir)
    _write(promoted, summary, model_dir, report_dir)
    logger.info(
        "stage_train",
        status="success",
        promoted=promoted.name,
        validation_auc=round(promoted.validation["auc"], 4),
        test_auc=round(promoted.test["auc"], 4),
        duration_s=round(time.perf_counter() - started, 3),
    )
    return summary


def _summary(
    results: list[CandidateResult], promoted: CandidateResult, features: list[str], ref: Path
) -> dict[str, Any]:
    split_metadata = read_split_metadata(ref)
    return {
        "promoted": promoted.name,
        "criterion": load_config()["model"]["promotion"],
        "features": features,
        "source": split_metadata["source"],
        "source_sha256": split_metadata["source_sha256"],
        "seed": get_seed(),
        "library_versions": {lib: version(lib) for lib in ("scikit-learn", "xgboost")},
        "candidates": [
            {
                "name": r.name,
                "threshold": round(r.threshold, 6),
                "validation": {k: round(v, 4) for k, v in r.validation.items()},
                "test": {k: round(v, 4) for k, v in r.test.items()},
            }
            for r in results
        ],
    }


def _write(
    promoted: CandidateResult, summary: dict[str, Any], model_dir: Path, report_dir: Path
) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(promoted.model, model_dir / MODEL_FILE)
    metadata = {**summary, "threshold": promoted.threshold}
    write_json(model_dir / MODEL_METADATA_FILE, metadata)
    report = report_dir / report_name(COMPARISON_FILE, summary["source"])
    write_json(report, summary)
