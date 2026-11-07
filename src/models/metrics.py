"""Metricas de um score de credito: AUC, KS e metricas no limiar escolhido."""

import numpy as np
from sklearn.metrics import precision_score, recall_score, roc_auc_score, roc_curve


def ks_statistic(y_true: np.ndarray, scores: np.ndarray) -> float:
    """KS de credito: maior distancia entre as distribuicoes de score de bons e maus.

    Equivale ao maximo de ``TPR - FPR`` na curva ROC.
    """
    fpr, tpr, _ = roc_curve(y_true, scores)
    return float(np.max(tpr - fpr))


def max_ks_threshold(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Limiar de score onde o KS e maximo (ponto de maior separacao)."""
    fpr, tpr, thresholds = roc_curve(y_true, scores)
    best = int(np.argmax(tpr - fpr))
    return float(min(thresholds[best], 1.0))


def classification_metrics(
    y_true: np.ndarray, scores: np.ndarray, threshold: float
) -> dict[str, float]:
    """Metricas do score e da decisao no limiar.

    Args:
        y_true: Rotulos (1 = inadimplente).
        scores: Probabilidade prevista de inadimplencia.
        threshold: Score a partir do qual o cliente e classificado como risco.

    Returns:
        AUC, KS, recall, precision e taxa de aprovacao (fracao abaixo do limiar).
    """
    predicted = (scores >= threshold).astype(int)
    return {
        "auc": float(roc_auc_score(y_true, scores)),
        "ks": ks_statistic(y_true, scores),
        "recall_default": float(recall_score(y_true, predicted, zero_division=0)),
        "precision_default": float(precision_score(y_true, predicted, zero_division=0)),
        "approval_rate": float(1 - predicted.mean()),
    }
