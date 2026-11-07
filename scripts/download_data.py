"""Obtem o dataset do projeto.

Uso:
    uv run python scripts/download_data.py               # dataset real da UCI (sem conta)
    uv run python scripts/download_data.py --synthetic   # fallback sintetico, mesmo esquema

O dataset real e conferido por SHA256 (configs/pipeline.yaml). O sintetico valida o
pipeline, mas nao reproduz as metricas documentadas.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from src.config import get_seed, load_config, raw_dataset_path, synthetic_dataset_path  # noqa: E402
from src.data.download import DatasetIntegrityError, download_dataset  # noqa: E402
from src.data.synthetic import generate_synthetic  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402

logger = get_logger("download_data")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Obtem o dataset UCI 350 ou o sintetico.")
    parser.add_argument("--synthetic", action="store_true", help="Gera o dataset sintetico.")
    parser.add_argument("--rows", type=int, default=None, help="Linhas do sintetico.")
    return parser.parse_args()


def fetch_real() -> int:
    dataset = load_config()["dataset"]
    try:
        path = download_dataset(dataset["url"], raw_dataset_path(), dataset["sha256"])
    except requests.RequestException as error:
        logger.error(
            "dataset_download_failed",
            reason=str(error),
            hint="UCI indisponivel? Use --synthetic para validar o pipeline sem o dado real.",
        )
        return 1
    except DatasetIntegrityError as error:
        logger.error("dataset_integrity_failed", reason=str(error))
        return 1
    logger.info("dataset_ready", path=str(path), license=dataset["license"])
    return 0


def build_synthetic(rows: int | None) -> int:
    rows = rows or load_config()["synthetic"]["default_rows"]
    path = synthetic_dataset_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    generate_synthetic(rows, get_seed()).to_csv(path, index=False)
    logger.info("synthetic_dataset_ready", path=str(path), rows=rows)
    return 0


def main() -> int:
    configure_logging()
    args = parse_args()
    return build_synthetic(args.rows) if args.synthetic else fetch_real()


if __name__ == "__main__":
    sys.exit(main())
