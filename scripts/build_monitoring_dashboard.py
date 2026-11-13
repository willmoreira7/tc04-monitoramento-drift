"""Gera o dashboard HTML estático com base nas execuções MLflow locais."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.monitoring.tracking import build_dashboard  # noqa: E402

if __name__ == "__main__":
    configure_logging("json")
    get_logger(__name__).info("dashboard_generated", path=str(build_dashboard()))
