"""Registro dos estagios de um lote: status, latencia, volume e uso de memoria.

Cada lote passa por ``STAGES`` em ordem. O ``BatchRecorder`` mede cada estagio e produz
as metricas de pipeline e de infraestrutura descritas em docs/MONITORING.md. Um estagio
que nao chegou a rodar (lote bloqueado antes) simplesmente nao aparece nas metricas.
"""

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import psutil

from src.contracts.result import ContractViolationError
from src.monitoring.log import get_logger

logger = get_logger(__name__)

STAGES = ("ingestion", "validation", "prediction", "drift", "performance")

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"
STATUS_VALUES = {STATUS_SUCCESS: 1.0, STATUS_FAILED: 0.0, STATUS_BLOCKED: -1.0}

BYTES_PER_MB = 1024 * 1024


@dataclass
class StageRecord:
    """Resultado de um estagio.

    Attributes:
        stage: Nome do estagio (um de ``STAGES``).
        rows_in: Linhas recebidas; ``None`` se o estagio nao chegou a conhece-las.
        rows_out: Linhas entregues ao proximo estagio (0 se bloqueado ou com falha).
        status: ``success``, ``failed`` ou ``blocked``.
        duration_s: Latencia do estagio.
    """

    stage: str
    rows_in: int | None = None
    rows_out: int | None = None
    status: str = STATUS_SUCCESS
    duration_s: float = 0.0


@dataclass
class BatchRecorder:
    """Acumula os estagios de um lote e deriva as metricas de saude."""

    batch_id: str
    records: list[StageRecord] = field(default_factory=list)
    _started: float = field(default_factory=time.perf_counter)

    @contextmanager
    def stage(self, name: str, rows_in: int | None = None) -> Iterator[StageRecord]:
        """Mede um estagio. Excecoes sao registradas e propagadas, nunca engolidas.

        Violacao de contrato vira ``blocked`` (falha esperada, ja logada pelo estagio);
        qualquer outra excecao vira ``failed`` e e logada aqui.

        Args:
            name: Nome do estagio (um de ``STAGES``).
            rows_in: Linhas recebidas, quando ja conhecidas.

        Yields:
            Registro do estagio, para o chamador preencher ``rows_in``/``rows_out``.
        """
        if name not in STAGES:
            raise ValueError(f"Estagio desconhecido: {name}")
        record = StageRecord(name, rows_in)
        self.records.append(record)
        started = time.perf_counter()
        try:
            yield record
        except ContractViolationError as error:
            record.status = STATUS_BLOCKED
            record.rows_in = error.result.rows
            record.rows_out = 0
            raise
        except Exception as error:
            record.status = STATUS_FAILED
            record.rows_out = 0
            logger.error(
                f"stage_{name}",
                stage=name,
                status=STATUS_FAILED,
                batch_id=self.batch_id,
                rows_in=record.rows_in,
                rows_out=0,
                duration_s=round(time.perf_counter() - started, 3),
                error_type=type(error).__name__,
            )
            raise
        finally:
            record.duration_s = time.perf_counter() - started

    @property
    def status(self) -> str:
        """Status do lote: o do primeiro estagio que nao teve sucesso."""
        return next(
            (record.status for record in self.records if record.status != STATUS_SUCCESS),
            STATUS_SUCCESS,
        )

    def metrics(self) -> dict[str, float]:
        """Metricas de pipeline e infraestrutura do lote (docs/MONITORING.md)."""
        duration = time.perf_counter() - self._started
        rows_in = next((r.rows_in for r in self.records if r.rows_in is not None), 0)
        rows_out = self.records[-1].rows_out if self.records else 0
        metrics = {
            "rows_in": float(rows_in),
            "rows_out": float(rows_out or 0),
            "pipeline_duration_s": duration,
            "throughput_rows_s": rows_in / duration if duration > 0 else 0.0,
            "peak_memory_mb": peak_memory_mb(),
        }
        for record in self.records:
            metrics[f"stage_status_{record.stage}"] = STATUS_VALUES[record.status]
            metrics[f"stage_duration_s_{record.stage}"] = record.duration_s
        return metrics


def peak_memory_mb() -> float:
    """Pico de memoria residente do processo, em MB (Windows, Linux e macOS)."""
    memory = psutil.Process().memory_info()
    peak_bytes = getattr(memory, "peak_wset", None)  # so existe no Windows
    if peak_bytes is None:
        import resource  # modulo exclusivo de Unix

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = peak if sys.platform == "darwin" else peak * 1024  # macOS: bytes; Linux: KB
    return peak_bytes / BYTES_PER_MB
