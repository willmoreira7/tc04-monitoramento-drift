"""Verifica se o ambiente esta pronto para rodar o projeto e diz o que falta.

Uso:
    uv run python scripts/verify_setup.py

Termina com codigo 0 se nao houver falhas (avisos sao permitidos) e 1 caso contrario.
"""

import importlib
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (  # noqa: E402
    PROJECT_ROOT,
    load_config,
    raw_dataset_path,
    synthetic_dataset_path,
)
from src.data.download import is_valid  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402

logger = get_logger("verify_setup")

REQUIRED_PACKAGES = [
    "pandas",
    "numpy",
    "sklearn",
    "xgboost",
    "pandera",
    "evidently",
    "mlflow",
    "structlog",
    "yaml",
]
EXPECTED_PYTHON = (3, 12)
REQUIRED_DIRS = ["configs", "src", "scripts", "tests", "docs", "reports"]

OK, WARN, FAIL = "ok", "warn", "fail"


def check_python() -> tuple[str, str]:
    current = sys.version_info[:2]
    if current == EXPECTED_PYTHON:
        return OK, f"Python {sys.version.split()[0]}"
    return FAIL, f"Python {current[0]}.{current[1]}; esperado 3.12 (rode via `uv run`)"


def check_virtualenv() -> tuple[str, str]:
    if Path(sys.prefix).resolve() == (PROJECT_ROOT / ".venv").resolve():
        return OK, "ambiente do projeto (.venv)"
    return FAIL, "fora do .venv do projeto: rode `uv sync --group dev` e use `uv run`"


def check_packages() -> tuple[str, str]:
    missing = [name for name in REQUIRED_PACKAGES if not _importable(name)]
    if missing:
        return FAIL, f"pacotes ausentes: {', '.join(missing)} (rode `uv sync --group dev`)"
    pandas_major = int(importlib.import_module("pandas").__version__.split(".")[0])
    if pandas_major >= 3:
        return FAIL, "pandas >= 3 e incompativel com o Evidently 0.7 (rode `uv sync`)"
    return OK, "dependencias importaveis"


def check_dirs() -> tuple[str, str]:
    missing = [name for name in REQUIRED_DIRS if not (PROJECT_ROOT / name).is_dir()]
    if missing:
        return FAIL, f"diretorios ausentes: {', '.join(missing)}"
    return OK, "estrutura de diretorios"


def check_dataset() -> tuple[str, str]:
    if is_valid(raw_dataset_path(), load_config()["dataset"]["sha256"]):
        return OK, "dataset real presente e integro (SHA256 confere)"
    if raw_dataset_path().exists():
        return FAIL, "dataset real com SHA256 divergente: apague-o e baixe de novo"
    if synthetic_dataset_path().exists():
        return WARN, "so o sintetico presente: metricas nao reproduzem as documentadas"
    return WARN, "dataset ausente: `uv run python scripts/download_data.py`"


def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
    except ImportError:
        return False
    return True


CHECKS: list[tuple[str, Callable[[], tuple[str, str]]]] = [
    ("python", check_python),
    ("virtualenv", check_virtualenv),
    ("packages", check_packages),
    ("directories", check_dirs),
    ("dataset", check_dataset),
]


def main() -> int:
    configure_logging()
    failures = 0
    for name, check in CHECKS:
        status, detail = check()
        log = logger.error if status == FAIL else logger.warning if status == WARN else logger.info
        log("check", name=name, status=status, detail=detail)
        failures += status == FAIL
    logger.info("verify_setup_finished", failures=failures, ready=failures == 0)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
