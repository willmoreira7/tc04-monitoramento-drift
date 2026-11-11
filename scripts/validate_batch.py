"""Demonstra o contrato de dados: um lote valido passa, o corrompido e bloqueado.

Uso:
    uv run python scripts/validate_batch.py --demo valid       # exit 0
    uv run python scripts/validate_batch.py --demo corrupted   # exit 2 (bloqueado)

Exit codes: 0 = lote aprovado · 1 = dados nao preparados · 2 = lote bloqueado pelo contrato.
Pre-requisito: ``uv run python scripts/prepare_data.py``.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.contracts.result import ContractViolationError  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.pipeline.validate import DemoBatch, validate_demo_batch  # noqa: E402

logger = get_logger("validate_batch")

EXIT_MISSING_DATA = 1
EXIT_BLOCKED = 2


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Valida um lote de demonstracao.")
    parser.add_argument(
        "--demo", choices=[kind.value for kind in DemoBatch], required=True, help="Lote."
    )
    kind = DemoBatch(parser.parse_args().demo)
    try:
        validate_demo_batch(kind)
    except FileNotFoundError as error:
        logger.error("data_missing", reason=str(error))
        return EXIT_MISSING_DATA
    except ContractViolationError as error:
        for violation in error.result.violations:
            logger.error(
                "violation",
                rule=violation.rule,
                column=violation.column,
                check=violation.check,
                cases=violation.cases,
            )
        logger.error("batch_blocked", batch_id=error.batch_id, quarantine="data/quarantine/")
        return EXIT_BLOCKED
    return 0


if __name__ == "__main__":
    sys.exit(main())
