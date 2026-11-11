"""Resultado da validacao de um lote contra o contrato de dados."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Violation:
    """Uma regra violada, agregada por coluna e verificacao.

    Attributes:
        rule: Identificador da regra em docs/DATA_CONTRACTS.md (``C1``..``C8``, ``W1``..``W4``).
        column: Coluna afetada; ``None`` para regras de lote inteiro.
        check: Verificacao que falhou, como descrita pelo Pandera ou pelo aviso.
        cases: Numero de ocorrencias.
        examples: Ate tres valores distintos que falharam (nunca linhas inteiras).
    """

    rule: str
    column: str | None
    check: str
    cases: int
    examples: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class ContractResult:
    """Violacoes criticas (bloqueiam) e avisos (so registram) de um lote."""

    rows: int
    violations: list[Violation]
    warnings: list[Violation]

    @property
    def passed(self) -> bool:
        """``True`` se nenhuma regra critica foi violada."""
        return not self.violations

    @property
    def rules_violated(self) -> list[str]:
        """Regras criticas violadas, sem repeticao e em ordem."""
        return sorted({violation.rule for violation in self.violations})

    def to_dict(self) -> dict[str, Any]:
        """Versao serializavel, usada no relatorio e na quarentena."""
        return {
            "status": "passed" if self.passed else "blocked",
            "rows": self.rows,
            "rules_violated": self.rules_violated,
            "critical": [asdict(violation) for violation in self.violations],
            "warnings": [asdict(warning) for warning in self.warnings],
        }


class ContractViolationError(RuntimeError):
    """Um lote violou regras criticas do contrato e foi bloqueado."""

    def __init__(self, batch_id: str, result: ContractResult) -> None:
        super().__init__(f"Lote '{batch_id}' bloqueado: regras {', '.join(result.rules_violated)}")
        self.batch_id = batch_id
        self.result = result
