"""Gera o dashboard HTML estatico a partir das execucoes locais do MLflow.

Uso:
    uv run python scripts/build_monitoring_dashboard.py                      # dataset real
    uv run python scripts/build_monitoring_dashboard.py --source synthetic   # nao versionado
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitoring.dashboard import build_dashboard  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402

logger = get_logger("build_monitoring_dashboard")


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Gera o dashboard de monitoramento.")
    parser.add_argument("--source", choices=["real", "synthetic"], default="real", help="Origem.")
    logger.info("dashboard_generated", path=str(build_dashboard(parser.parse_args().source)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
