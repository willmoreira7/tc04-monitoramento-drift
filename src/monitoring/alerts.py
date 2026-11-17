"""Regras de alerta avaliadas a cada lote (docs/MONITORING.md).

Funcao pura: recebe as metricas e o status do lote, devolve os alertas. Limiares vem de
``configs/pipeline.yaml``; quem registra e notifica e o chamador.
"""

from collections.abc import Mapping
from typing import Any

from src.config import load_config

SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

Alert = dict[str, str]


def evaluate_alerts(
    metrics: Mapping[str, float],
    status: str = "success",
    config: Mapping[str, Any] | None = None,
) -> list[Alert]:
    """Avalia as regras de alerta de um lote, sem efeitos colaterais.

    Args:
        metrics: Metricas do lote. Regras cuja metrica nao esta presente nao disparam
            (ex.: ``auc_drop`` so existe quando os rotulos chegam).
        status: Status do lote (``success``, ``failed`` ou ``blocked``).
        config: Configuracao do pipeline; se omitida, usa ``configs/pipeline.yaml``.

    Returns:
        Alertas com ``name``, ``severity`` e ``action`` (a resposta do playbook).
    """
    config = config or load_config()
    rules = config["monitoring"]["thresholds"]
    alerts = _status_alerts(status)
    alerts += _volume_alerts(metrics, config["contract"]["warnings"]["volume_tolerance"])
    for key, value in metrics.items():
        if key == "psi_score":
            if value >= rules["score_psi_critical"]:
                alerts.append(_alert(key, SEVERITY_CRITICAL, "investigate_score_drift"))
            elif value >= rules["score_psi_warning"]:
                alerts.append(_alert(key, SEVERITY_WARNING, "review_approval_rate"))
        elif key.startswith("psi_"):
            if value >= rules["psi_critical"]:
                alerts.append(_alert(key, SEVERITY_CRITICAL, "open_causal_analysis"))
            elif value >= rules["psi_warning"]:
                alerts.append(_alert(key, SEVERITY_WARNING, "monitor_trend"))
        elif key == "auc_drop":
            if value >= rules["auc_drop_critical"]:
                alerts.append(_alert(key, SEVERITY_CRITICAL, "evaluate_retraining"))
            elif value >= rules["auc_drop_warning"]:
                alerts.append(_alert(key, SEVERITY_WARNING, "review_performance"))
        elif key == "recall_drop":
            if value >= rules["recall_drop_critical"]:
                alerts.append(_alert(key, SEVERITY_CRITICAL, "review_missed_defaults"))
            elif value >= rules["recall_drop_warning"]:
                alerts.append(_alert(key, SEVERITY_WARNING, "review_recall_trend"))
        elif key == "share_features_drifted":
            if value >= rules["drifted_share_critical"]:
                alerts.append(_alert(key, SEVERITY_CRITICAL, "open_causal_analysis"))
            elif value >= rules["drifted_share_warning"]:
                alerts.append(_alert(key, SEVERITY_WARNING, "monitor_feature_drift"))
    return alerts


def _status_alerts(status: str) -> list[Alert]:
    if status == "blocked":
        return [_alert("batch_blocked", SEVERITY_CRITICAL, "investigate_source_and_reprocess")]
    if status == "failed":
        return [_alert("stage_failure", SEVERITY_CRITICAL, "read_stage_log_and_rerun")]
    return []


def _volume_alerts(metrics: Mapping[str, float], tolerance: float) -> list[Alert]:
    expected = metrics.get("rows_expected")
    if not expected or "rows_in" not in metrics:
        return []
    if abs(metrics["rows_in"] - expected) / expected > tolerance:
        return [_alert("volume_anomaly", SEVERITY_WARNING, "check_extraction")]
    return []


def _alert(name: str, severity: str, action: str) -> Alert:
    return {"name": name, "severity": severity, "action": action}
