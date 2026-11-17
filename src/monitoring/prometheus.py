"""Camada opcional: envia as metricas de cada lote a um Prometheus Pushgateway.

O pipeline e batch: termina antes de qualquer scrape. O lote entao empurra suas metricas
para o Pushgateway, de onde o Prometheus as coleta e o Grafana as exibe (ambiente da
Fase 3). So e ativada com ``TC04_PUSHGATEWAY_URL``; sem a variavel, nada muda -- MLflow e
o dashboard HTML continuam sendo o caminho obrigatorio.

Cada lote e um grupo no Pushgateway (``batch_id`` + ``source``) e um novo envio substitui
o grupo inteiro: o Grafana mostra sempre a execucao mais recente de cada lote. A
cardinalidade e limitada: lotes (M01..M06 + demonstracao), estagios, regras e features.
"""

import os
import time
from collections.abc import Mapping, Sequence

from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

from src.monitoring.alerts import Alert
from src.monitoring.log import get_logger
from src.monitoring.stages import STATUS_VALUES

logger = get_logger(__name__)

PUSHGATEWAY_ENV = "TC04_PUSHGATEWAY_URL"
JOB = "tc04_batch"
PREFIX = "tc04_batch_"
PUSH_TIMEOUT_S = 10

# Metricas do lote com sufixo variavel viram uma serie com label (nome, descricao, label).
LABELED_FAMILIES = {
    "stage_status_": ("tc04_stage_status", "1 sucesso, 0 falha, -1 bloqueado", "stage"),
    "stage_duration_s_": ("tc04_stage_duration_seconds", "Latencia do estagio", "stage"),
    "contract_violations_": ("tc04_contract_violations", "Violacoes criticas por regra", "rule"),
    "contract_warnings_": ("tc04_contract_warnings", "Avisos do contrato por regra", "rule"),
    "ks_d_": ("tc04_feature_ks_d", "Estatistica D do KS por feature", "feature"),
    "psi_": ("tc04_feature_psi", "PSI por feature", "feature"),
}
SCALAR_EXCEPTIONS = {"psi_score"}  # comeca com psi_, mas e o PSI do score, nao de feature


def build_registry(
    *,
    scenario: str,
    status: str,
    metrics: Mapping[str, float],
    alerts: Sequence[Alert] = (),
) -> CollectorRegistry:
    """Converte as metricas de um lote em series Prometheus.

    Args:
        scenario: Cenario do lote, exposto como label de ``tc04_batch_info``.
        status: ``success``, ``failed`` ou ``blocked``.
        metrics: Metricas do lote, com os mesmos nomes registrados no MLflow.
        alerts: Alertas disparados; cada um vira uma serie ``tc04_batch_alert``.

    Returns:
        Registro pronto para envio.
    """
    registry = CollectorRegistry()
    families: dict[str, Gauge] = {}
    for key, value in metrics.items():
        prefix = next(
            (p for p in LABELED_FAMILIES if key.startswith(p) and key not in SCALAR_EXCEPTIONS),
            None,
        )
        if prefix is None:
            Gauge(f"{PREFIX}{key}", f"Metrica {key} do lote", registry=registry).set(value)
            continue
        name, description, label = LABELED_FAMILIES[prefix]
        if name not in families:
            families[name] = Gauge(name, description, [label], registry=registry)
        families[name].labels(key.removeprefix(prefix)).set(value)
    Gauge(f"{PREFIX}status", "1 sucesso, 0 falha, -1 bloqueado", registry=registry).set(
        STATUS_VALUES[status]
    )
    Gauge(f"{PREFIX}info", "Metadados do lote", ["scenario"], registry=registry).labels(
        scenario
    ).set(1)
    Gauge(f"{PREFIX}last_run_timestamp_seconds", "Fim da execucao", registry=registry).set(
        time.time()
    )
    alert_gauge = Gauge(
        f"{PREFIX}alert", "Alerta disparado", ["alert", "severity", "action"], registry=registry
    )
    for alert in alerts:
        alert_gauge.labels(alert["name"], alert["severity"], alert["action"]).set(1)
    return registry


def push_batch_metrics(
    batch_id: str,
    *,
    scenario: str,
    status: str,
    source: str,
    metrics: Mapping[str, float],
    alerts: Sequence[Alert] = (),
    gateway: str | None = None,
) -> bool:
    """Envia as metricas do lote ao Pushgateway, se houver um configurado.

    Camada opcional: Pushgateway ausente ou fora do ar nunca derruba o lote.

    Args:
        batch_id: Identificador do lote (chave do grupo no Pushgateway).
        scenario: Cenario do lote.
        status: ``success``, ``failed`` ou ``blocked``.
        source: ``real``, ``synthetic`` ou ``unknown`` (chave do grupo).
        metrics: Metricas do lote.
        alerts: Alertas disparados.
        gateway: URL do Pushgateway; se omitida, usa ``TC04_PUSHGATEWAY_URL``.

    Returns:
        ``True`` se as metricas foram enviadas; ``False`` se desligado ou inacessivel.
    """
    gateway = gateway or os.environ.get(PUSHGATEWAY_ENV)
    if not gateway:
        return False
    registry = build_registry(scenario=scenario, status=status, metrics=metrics, alerts=alerts)
    try:
        push_to_gateway(
            gateway,
            job=JOB,
            grouping_key={"batch_id": batch_id, "source": source},
            registry=registry,
            timeout=PUSH_TIMEOUT_S,
        )
    except OSError as error:
        logger.warning("pushgateway_unreachable", gateway=gateway, error_type=type(error).__name__)
        return False
    logger.info("pushgateway_pushed", gateway=gateway, batch_id=batch_id)
    return True
