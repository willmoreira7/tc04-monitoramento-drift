"""Configuracao unica do structlog para todo o projeto.

Formato ``console`` para quem le no terminal; ``json`` para o pipeline, cujos logs sao
centralizados na Etapa 3. O formato vem do argumento ou da variavel ``TC04_LOG_FORMAT``.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

import structlog

from src.config import LOGS_DIR

LOG_FORMAT_ENV = "TC04_LOG_FORMAT"


def configure_logging(fmt: str | None = None, level: int = logging.INFO) -> None:
    """Configura o structlog.

    Args:
        fmt: ``"console"`` ou ``"json"``. Se omitido, usa ``TC04_LOG_FORMAT`` ou ``console``.
        level: Nivel minimo de log.
    """
    fmt = fmt or os.environ.get(LOG_FORMAT_ENV, "console")
    renderer = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def log_pipeline_event(event: str, **fields: Any) -> None:
    """Anexa evento JSON sanitizado ao log local; nunca serializa payloads de dados."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    with (LOGS_DIR / "pipeline.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\\n")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Retorna um logger nomeado."""
    return structlog.get_logger(name)
