"""Roda um lote de demonstracao monitorado: estagios medidos, alertas e run no MLflow.

Uso:
    uv run python scripts/run_monitoring_demo.py --demo valid       # exit 0
    uv run python scripts/run_monitoring_demo.py --demo corrupted   # exit 2 (bloqueado)

Exit codes: 0 = lote aprovado · 1 = falha (ex.: dados nao preparados) · 2 = lote bloqueado.
Toda execucao, inclusive a bloqueada e a com falha, fica registrada no MLflow e no dashboard.
Pre-requisito: ``uv run python scripts/prepare_data.py``.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitoring.dashboard import build_dashboard  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.monitoring.stages import STATUS_BLOCKED, STATUS_FAILED, STATUS_SUCCESS  # noqa: E402
from src.monitoring.tracking import SOURCE_UNKNOWN  # noqa: E402
from src.pipeline.monitor import run_monitored_demo  # noqa: E402
from src.pipeline.validate import DemoBatch  # noqa: E402

logger = get_logger("run_monitoring_demo")

EXIT_CODES = {STATUS_SUCCESS: 0, STATUS_FAILED: 1, STATUS_BLOCKED: 2}


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Roda um lote de demonstracao monitorado.")
    parser.add_argument(
        "--demo", choices=[kind.value for kind in DemoBatch], required=True, help="Lote."
    )
    parser.add_argument("--scenario", default="contract_demo", help="Tag de cenario da execucao.")
    args = parser.parse_args()
    outcome = run_monitored_demo(DemoBatch(args.demo), args.scenario)
    if outcome.source != SOURCE_UNKNOWN:
        dashboard = build_dashboard(outcome.source)
        logger.info("dashboard_generated", path=str(dashboard))
    return EXIT_CODES[outcome.status]


if __name__ == "__main__":
    sys.exit(main())
