"""Adapta resultados de drift/performance da Etapa 2 ao contrato de métricas do tracking."""

import math
from collections.abc import Mapping
from typing import Any

from src.config import load_config


def build_model_metrics(
    feature_psi: Mapping[str, float],
    *,
    score_psi: float | None = None,
    feature_ks_d: Mapping[str, float] | None = None,
    baseline_auc: float | None = None,
    batch_auc: float | None = None,
    baseline_recall: float | None = None,
    batch_recall: float | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Converte estatísticas por lote em nomes/valores esperados pelo MLflow e alertas.

    Métricas de performance são omitidas se não há valores do lote (rótulos indisponíveis).
    Quedas são diferenças positivas ``baseline - batch``, limitadas inferiormente a zero.

    Args:
        feature_psi: PSI calculado para cada feature comparada.
        score_psi: PSI da distribuição dos scores, se calculado.
        feature_ks_d: Estatística D do KS por feature (não p-valor).
        baseline_auc: AUC medida no conjunto de referência de avaliação.
        batch_auc: AUC do lote atual, quando seus rótulos estão disponíveis.
        baseline_recall: Recall de inadimplentes no baseline.
        batch_recall: Recall de inadimplentes no lote atual, se rotulado.
        config: Configuração do projeto; por padrão, ``configs/pipeline.yaml``.

    Returns:
        Métricas escalares seguras para ``log_batch_run`` e ``evaluate_alerts``.

    Raises:
        ValueError: Para PSI/KS fora do domínio ou performance fora de [0, 1].
    """
    settings = (config or load_config())["monitoring"]["thresholds"]
    metrics: dict[str, float] = {}
    for feature, value in feature_psi.items():
        _require_range(f"PSI {feature}", value, 0.0, None)
        metrics[f"psi_{feature}"] = float(value)
    for feature, value in (feature_ks_d or {}).items():
        _require_range(f"KS D {feature}", value, 0.0, 1.0)
        metrics[f"ks_d_{feature}"] = float(value)
    if score_psi is not None:
        _require_range("PSI score", score_psi, 0.0, None)
        metrics["psi_score"] = float(score_psi)

    drifted = sum(value >= settings["psi_warning"] for value in feature_psi.values())
    metrics["n_features_drifted"] = float(drifted)
    metrics["share_features_drifted"] = drifted / len(feature_psi) if feature_psi else 0.0

    if batch_auc is not None:
        _require_range("AUC", batch_auc, 0.0, 1.0)
        metrics["auc_roc"] = float(batch_auc)
        if baseline_auc is not None:
            _require_range("AUC baseline", baseline_auc, 0.0, 1.0)
            metrics["auc_drop"] = round(max(0.0, float(baseline_auc - batch_auc)), 8)
    if batch_recall is not None:
        _require_range("Recall", batch_recall, 0.0, 1.0)
        metrics["recall_default"] = float(batch_recall)
        if baseline_recall is not None:
            _require_range("Recall baseline", baseline_recall, 0.0, 1.0)
            metrics["recall_drop"] = round(max(0.0, float(baseline_recall - batch_recall)), 8)
    return metrics


def _require_range(name: str, value: float, minimum: float, maximum: float | None) -> None:
    """Valida valores escalares, rejeitando NaN/inf por não pertencerem ao intervalo."""
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        upper = "infinito" if maximum is None else str(maximum)
        raise ValueError(f"{name} deve estar entre {minimum} e {upper}: {value}")
