"""Executa a demonstracao de contrato e registra runs batch no MLflow."""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import REPORTS_DIR  # noqa: E402
from src.contracts.result import ContractViolationError  # noqa: E402
from src.monitoring.log import configure_logging, get_logger  # noqa: E402
from src.monitoring.tracking import build_dashboard, log_batch_run  # noqa: E402
from src.pipeline.validate import DemoBatch, validate_demo_batch  # noqa: E402

logger = get_logger(__name__)


def main() -> int:
    """Roda lotes de demonstração e atualiza evidência HTML."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", choices=[item.value for item in DemoBatch], required=True)
    parser.add_argument("--scenario", default="contract_demo")
    args = parser.parse_args()
    configure_logging("json")
    kind = DemoBatch(args.demo)
    batch_id = f"demo_{kind.value}"
    report = REPORTS_DIR / "validation" / f"{batch_id}.json"
    started = time.perf_counter()
    try:
        result = validate_demo_batch(kind)
    except ContractViolationError as error:
        elapsed = time.perf_counter() - started
        alerts = [{"name": "contract_violation", "severity": "critical", "action": "quarantine"}]
        log_batch_run(
            batch_id,
            scenario=args.scenario,
            status="blocked",
            metrics={
                "validation_duration_s": elapsed,
                "rows_in": error.result.rows,
                "rows_out": 0,
                "contract_violations": len(error.result.violations),
            },
            alerts=alerts,
            artifacts={"validation": report},
            error_type=type(error).__name__,
        )
        build_dashboard()
        logger.error("monitoring_batch_blocked", batch_id=batch_id, status="blocked")
        return 2
    except Exception as error:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        log_batch_run(
            batch_id,
            scenario=args.scenario,
            status="failed",
            metrics={"validation_duration_s": elapsed},
            error_type=type(error).__name__,
        )
        build_dashboard()
        logger.exception("monitoring_batch_failed", batch_id=batch_id, status="failed")
        return 1

    elapsed = time.perf_counter() - started
    log_batch_run(
        batch_id,
        scenario=args.scenario,
        status="success",
        metrics={
            "validation_duration_s": elapsed,
            "rows_in": result.rows,
            "rows_out": result.rows,
            "contract_violations": 0,
            "contract_warnings": len(result.warnings),
        },
        artifacts={"validation": report},
    )
    build_dashboard()
    logger.info("monitoring_batch_completed", batch_id=batch_id, status="success")
    return 0


if __name__ == "__main__":
    sys.exit(main())
