"""Limpa o dataset e separa referencia (treino/validacao/teste) e pool de producao.

Uso:
    uv run python scripts/prepare_data.py               # dataset real
    uv run python scripts/prepare_data.py --synthetic   # dataset sintetico
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.loader import DataSource  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.pipeline.prepare import prepare_data  # noqa: E402

logger = get_logger("prepare_data")


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Prepara referencia e pool de producao.")
    parser.add_argument("--synthetic", action="store_true", help="Usa o dataset sintetico.")
    source = DataSource.SYNTHETIC if parser.parse_args().synthetic else DataSource.REAL
    try:
        metadata = prepare_data(source)
    except FileNotFoundError as error:
        logger.error("dataset_missing", reason=str(error))
        return 1
    for name, subset in metadata["subsets"].items():
        logger.info("subset_ready", subset=name, **subset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
