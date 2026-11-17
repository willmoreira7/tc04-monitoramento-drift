"""Executa ablação causal dos cenários de drift sobre o dataset preparado."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.pipeline.causal import run_causal_ablation  # noqa: E402

logger = get_logger(__name__)


def main() -> int:
    """Gera o relatório causal real ou sintético conforme a origem preparada."""
    configure_logging()
    try:
        report = run_causal_ablation()
    except (FileNotFoundError, ValueError) as error:
        logger.error("causal_ablation_failed", reason=str(error))
        return 1
    logger.info(
        "causal_ablation_completed",
        source=report["source"],
        output="reports/drift/causal_ablation.json",
        interventions=len(report["interventions"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
