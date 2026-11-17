"""Simula os lotes M01..M06, detecta drift (PSI e KS) e mede a performance de cada um.

Uso:
    uv run python scripts/run_drift_simulation.py

Cada lote vira uma execucao no MLflow e um relatorio HTML do Evidently em
``reports/drift/``; o resumo de todos fica em ``reports/drift/drift_summary.json`` e o
dashboard de monitoramento e regenerado no fim.

Exit codes: 0 = todos os lotes processados · 1 = falha (ex.: modelo nao treinado) ·
2 = algum lote bloqueado pelo contrato.
Pre-requisitos: ``prepare_data.py`` e ``train_model.py``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitoring.dashboard import build_dashboard  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.monitoring.stages import STATUS_BLOCKED, STATUS_SUCCESS  # noqa: E402
from src.pipeline.drift import run_drift_simulation  # noqa: E402

logger = get_logger("run_drift_simulation")


def main() -> int:
    configure_logging()
    try:
        summary = run_drift_simulation()
    except (FileNotFoundError, ValueError) as error:
        logger.error("drift_simulation_failed", reason=str(error))
        return 1
    for batch_id, batch in summary["batches"].items():
        logger.info(
            "drift_batch",
            batch_id=batch_id,
            status=batch["status"],
            drifted=batch.get("drifted"),
            auc=batch.get("performance", {}).get("auc"),
            expectation_met=batch.get("expectation_met"),
        )
    logger.info("dashboard_generated", path=str(build_dashboard(summary["source"])))
    statuses = {batch["status"] for batch in summary["batches"].values()}
    if statuses == {STATUS_SUCCESS}:
        return 0
    return 2 if STATUS_BLOCKED in statuses else 1


if __name__ == "__main__":
    sys.exit(main())
