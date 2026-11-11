"""Ablacao de AGE/EDUCATION (ADR 13) e auditoria de vies do modelo promovido.

Uso:
    uv run python scripts/audit_model.py

Pre-requisito: ``uv run python scripts/train_model.py``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.pipeline.audit import audit_model  # noqa: E402

logger = get_logger("audit_model")


def main() -> int:
    configure_logging()
    try:
        result = audit_model()
    except FileNotFoundError as error:
        logger.error("audit_failed", reason=str(error))
        return 1
    for name, variant in result["ablation"]["variants"].items():
        logger.info(
            "ablation_variant",
            variant=name,
            promoted=variant["promoted"],
            validation_auc=variant["validation_auc"],
            auc_loss=variant["auc_loss"],
        )
    logger.info("ablation_decision", remove=result["ablation"]["remove"])
    if not result["ablation"]["decision_applied"]:
        logger.warning("ablation_decision_not_applied", hint="ajuste model.excluded_columns")
    for attribute, summary in result["fairness"]["attributes"].items():
        logger.info(
            "fairness",
            attribute=attribute,
            min_impact_ratio=summary["min_impact_ratio"],
            min_good_payer_ratio=summary["min_good_payer_ratio"],
            below_four_fifths=summary["below_four_fifths"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
