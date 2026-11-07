"""Configuracao unica do structlog para todo o projeto.

Formato ``console`` para quem le no terminal; ``json`` para o pipeline, cujos logs sao
centralizados na Etapa 3. O formato vem do argumento ou da variavel ``TC04_LOG_FORMAT``.
"""

import logging
import os
import sys

import structlog

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


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Retorna um logger nomeado."""
    return structlog.get_logger(name)
