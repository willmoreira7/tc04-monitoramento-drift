"""Estagio de auditoria: ablacao dos atributos pessoais + vies do modelo promovido.

- ``reports/model/ablation.json``: cada variante (com/sem ``AGE`` e ``EDUCATION``), o
  criterio declarado e a decisao (ADR 13). Medido na validacao.
- ``reports/model/fairness_audit.json``: resultado por grupo do modelo promovido, no teste.

Pre-requisito: ``train_model.py`` (o vies e medido no modelo que de fato foi promovido).
"""

import json
import time
from pathlib import Path
from typing import Any

import joblib

from src.config import MODELS_DIR, REFERENCE_DIR, REPORTS_DIR, get_seed, load_config
from src.models.ablation import run_ablation
from src.models.fairness import audit
from src.models.train import predict_scores
from src.monitoring.log import get_logger
from src.pipeline.io import read_prepared, read_split_metadata, report_name, write_json
from src.pipeline.train import MODEL_FILE, MODEL_METADATA_FILE

logger = get_logger(__name__)

ABLATION_FILE = "ablation.json"
FAIRNESS_FILE = "fairness_audit.json"


def audit_model(
    reference_dir: Path = REFERENCE_DIR,
    model_dir: Path = MODELS_DIR / "baseline",
    report_dir: Path = REPORTS_DIR / "model",
) -> dict[str, Any]:
    """Executa a ablacao e a auditoria de vies e grava os dois relatorios.

    Returns:
        ``{"ablation": ..., "fairness": ...}``.

    Raises:
        FileNotFoundError: Se a referencia ou o modelo nao existirem.
    """
    started = time.perf_counter()
    config = load_config()
    train, validation, test = (
        read_prepared(reference_dir / f"{name}.parquet") for name in ("train", "validation", "test")
    )
    source = read_split_metadata(reference_dir)["source"]

    ablation = run_ablation(train, validation, config, get_seed())
    ablation["decision_applied"] = _decision_applied(ablation["remove"], config)
    fairness = _audit_promoted(test, model_dir, config)

    write_json(report_dir / report_name(ABLATION_FILE, source), ablation)
    write_json(report_dir / report_name(FAIRNESS_FILE, source), fairness)
    logger.info(
        "stage_audit",
        status="success",
        remove=ablation["remove"],
        decision_applied=ablation["decision_applied"],
        rows_in=len(test),
        duration_s=round(time.perf_counter() - started, 3),
    )
    return {"ablation": ablation, "fairness": fairness}


def _audit_promoted(test: Any, model_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    model_path = model_dir / MODEL_FILE
    if not model_path.is_file():
        raise FileNotFoundError(
            f"{model_path} nao encontrado. Rode `uv run python scripts/train_model.py`."
        )
    metadata = json.loads((model_dir / MODEL_METADATA_FILE).read_text(encoding="utf-8"))
    scores = predict_scores(joblib.load(model_path), test[metadata["features"]])
    return {
        "model": metadata["promoted"],
        "features": metadata["features"],
        "threshold": round(metadata["threshold"], 6),
        "evaluated_on": "test",
        "rows": len(test),
        "criterion": config["fairness"],
        "attributes": audit(test, scores, metadata["threshold"], config["fairness"]),
    }


def _decision_applied(remove: list[str], config: dict[str, Any]) -> bool:
    """A config de treino reflete a decisao da ablacao?"""
    excluded = set(config["model"]["excluded_columns"])
    candidates = set(config["ablation"]["candidates"])
    return excluded & candidates == set(remove)
