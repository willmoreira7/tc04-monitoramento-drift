"""Ablação causal: mede mecanismos isolados e a interação documentada em M06."""

from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    MODELS_DIR,
    PRODUCTION_DIR,
    REFERENCE_DIR,
    REPORTS_DIR,
    get_seed,
    load_causal_interventions,
    load_config,
    load_scenarios,
)
from src.data.schema import TARGET_COLUMN
from src.drift.detect import detect_drift
from src.drift.scenarios import simulate_batch
from src.models.metrics import classification_metrics
from src.models.train import predict_scores
from src.pipeline.drift import SCORE_COLUMN, DriftContext, load_context
from src.pipeline.io import read_prepared, report_name, write_json

CAUSAL_REPORT = "causal_ablation.json"
DIGITS = 4


def run_causal_ablation(
    reference_dir: Path = REFERENCE_DIR,
    production_dir: Path = PRODUCTION_DIR,
    model_dir: Path = MODELS_DIR / "baseline",
    report_dir: Path = REPORTS_DIR / "drift",
) -> dict[str, Any]:
    """Mede o efeito de cada mecanismo isolado sobre o mesmo pool e limiar de decisão.

    A reamostragem altera necessariamente a composição das linhas selecionadas; os outros
    mecanismos reutilizam a mesma seed e tamanho de lote. Métricas são comparadas com M01
    (controle sem perturbação), e M04/M06 mostram o efeito da combinação observada.
    """
    context = load_context(reference_dir, model_dir, report_dir)
    pool = read_prepared(production_dir / "pool.parquet")
    rows = load_config()["batches"]["rows"]
    seed = get_seed()
    control = _measure(pool, {}, rows, seed, context)
    interventions = {
        name: _measure(pool, scenario, rows, seed, context)
        for name, scenario in load_causal_interventions().items()
    }
    scenarios = load_scenarios()
    contrasts = {
        batch_id: _measure(pool, scenarios[batch_id], rows, seed, context)
        for batch_id in ("M04", "M06")
    }
    result = {
        "source": context.source,
        "seed": seed,
        "rows_per_batch": rows,
        "reference_window": load_config()["drift"]["reference_window"],
        "method": "one mechanism at a time; changes measured against unperturbed M01 control",
        "control": control,
        "interventions": {
            name: _with_deltas(metrics, control) for name, metrics in interventions.items()
        },
        "combined_contrasts": {
            name: _with_deltas(metrics, control) for name, metrics in contrasts.items()
        },
        "interaction_m06_vs_m04": {
            metric: round(contrasts["M06"][metric] - contrasts["M04"][metric], DIGITS)
            for metric in ("auc", "recall_default", "approval_rate")
        },
    }
    write_json(report_dir / report_name(CAUSAL_REPORT, context.source), result)
    return result


def _measure(
    pool: pd.DataFrame,
    scenario: dict[str, Any],
    rows: int,
    seed: int,
    context: DriftContext,
) -> dict[str, Any]:
    batch = simulate_batch(pool, scenario, rows, seed)
    scores = predict_scores(context.model, batch[context.features])
    performance = classification_metrics(batch[TARGET_COLUMN].to_numpy(), scores, context.threshold)
    batch_with_score = batch.assign(**{SCORE_COLUMN: scores})
    drift, _ = detect_drift(context.reference, batch_with_score, context.monitored)
    threshold = load_config()["monitoring"]["thresholds"]["psi_warning"]
    return {
        **{key: round(value, DIGITS) for key, value in performance.items()},
        "default_rate": round(float(batch[TARGET_COLUMN].mean()), DIGITS),
        "drifted": sorted(
            name
            for name in [*context.features, *context.population]
            if drift[name].psi >= threshold
        ),
        "psi": {name: round(drift[name].psi, DIGITS) for name in context.monitored},
        "ks_d": {name: round(drift[name].ks_d, DIGITS) for name in context.monitored},
    }


def _with_deltas(metrics: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    """Inclui diferenças para controle sem alterar os valores medidos."""
    deltas = {
        key: round(metrics[key] - control[key], DIGITS)
        for key in ("auc", "recall_default", "approval_rate", "default_rate")
    }
    return {**metrics, "delta_vs_m01": deltas}
