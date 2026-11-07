"""Treina os candidatos (ADR 04), promove pelo criterio declarado e grava o modelo.

Uso:
    uv run python scripts/train_model.py

Pre-requisito: ``uv run python scripts/prepare_data.py``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.train import NoEligibleModelError  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.pipeline.train import train_model  # noqa: E402

logger = get_logger("train_model")


def main() -> int:
    configure_logging()
    try:
        summary = train_model()
    except (FileNotFoundError, NoEligibleModelError) as error:
        logger.error("train_failed", reason=str(error))
        return 1
    for candidate in summary["candidates"]:
        logger.info(
            "candidate",
            name=candidate["name"],
            validation_auc=candidate["validation"]["auc"],
            test_auc=candidate["test"]["auc"],
            test_ks=candidate["test"]["ks"],
            test_recall=candidate["test"]["recall_default"],
        )
    logger.info("promoted", name=summary["promoted"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
