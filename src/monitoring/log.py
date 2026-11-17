"""Configuracao unica do structlog para todo o projeto.

Formato ``console`` para quem le no terminal; ``json`` para o pipeline. Independente do
formato do terminal, todo evento tambem e gravado como uma linha JSON em
``logs/pipeline.jsonl`` -- o log centralizado da Etapa 3, anexado a cada execucao do MLflow.
O formato vem do argumento ou da variavel ``TC04_LOG_FORMAT``.
"""

import json
import logging
import os
import sys
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import structlog

from src.config import LOGS_DIR

LOG_FORMAT_ENV = "TC04_LOG_FORMAT"
PIPELINE_LOG = LOGS_DIR / "pipeline.jsonl"


def configure_logging(
    fmt: str | None = None,
    level: int = logging.INFO,
    log_file: Path | None = PIPELINE_LOG,
) -> None:
    """Configura o structlog.

    Args:
        fmt: ``"console"`` ou ``"json"``. Se omitido, usa ``TC04_LOG_FORMAT`` ou ``console``.
        level: Nivel minimo de log.
        log_file: Arquivo JSONL que centraliza os eventos; ``None`` desliga a gravacao.
    """
    fmt = fmt or os.environ.get(LOG_FORMAT_ENV, "console")
    renderer = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if log_file is not None:
        processors.append(_JsonlSink(log_file))
    structlog.configure(
        processors=[*processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Retorna um logger nomeado."""
    return structlog.get_logger(name)


def read_run_events(pipeline_run_id: str, log_file: Path = PIPELINE_LOG) -> list[dict[str, Any]]:
    """Eventos do log centralizado que pertencem a uma execucao do pipeline.

    Args:
        pipeline_run_id: Identificador vinculado aos logs durante a execucao do lote.
        log_file: Arquivo JSONL centralizado.

    Returns:
        Eventos da execucao, na ordem em que foram gravados (vazio se o arquivo nao existe).
    """
    if not log_file.is_file():
        return []
    events = []
    with log_file.open(encoding="utf-8") as handle:
        for line in handle:
            if pipeline_run_id not in line:
                continue
            event = json.loads(line)
            if event.get("pipeline_run_id") == pipeline_run_id:
                events.append(event)
    return events


class _JsonlSink:
    """Processor do structlog que anexa cada evento ao log centralizado.

    Grava so os campos do evento (agregados): nenhum estagio loga linhas do lote.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def __call__(
        self, logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event_dict, ensure_ascii=False, default=str) + "\n")
        return event_dict
