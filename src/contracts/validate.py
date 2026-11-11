"""Validacao de um lote: regras criticas (Pandera, lazy) + avisos.

Nao move arquivos nem decide o que fazer com o lote: isso e do estagio de pipeline
(``src/pipeline/validate.py``). Aqui so se responde "o lote cumpre o contrato?".
"""

from typing import Any

import pandas as pd
import pandera.pandas as pa

from src.contracts.result import ContractResult, Violation
from src.contracts.schema import Contract, build_contract
from src.contracts.soft_checks import soft_checks

MAX_EXAMPLES = 3


def validate_batch(
    frame: pd.DataFrame,
    config: dict[str, Any],
    expected_rows: int | None = None,
    reference: pd.DataFrame | None = None,
) -> ContractResult:
    """Valida um lote contra o contrato.

    ``lazy=True`` coleta todas as violacoes, nao so a primeira: o relatorio mostra tudo o
    que esta errado no lote de uma vez.

    Args:
        frame: Lote a validar.
        config: Secao ``contract`` da configuracao.
        expected_rows: Volume esperado (aviso W2).
        reference: Referencia para comparar a fracao de atrasos (aviso W3).

    Returns:
        Violacoes criticas e avisos.
    """
    contract = build_contract(config)
    try:
        contract.schema.validate(frame, lazy=True)
        violations: list[Violation] = []
    except pa.errors.SchemaErrors as error:
        violations = _summarize(error.failure_cases, contract)
    warnings = soft_checks(frame, config["warnings"], expected_rows, reference)
    return ContractResult(rows=len(frame), violations=violations, warnings=warnings)


def _summarize(failures: pd.DataFrame, contract: Contract) -> list[Violation]:
    violations = []
    for (column, check), group in failures.groupby(["column", "check"], dropna=False, sort=False):
        name = None if pd.isna(column) else str(column)
        violations.append(
            Violation(
                rule=contract.rule_of(name, str(check)),
                column=name,
                check=str(check),
                cases=len(group),
                examples=_examples(group["failure_case"]),
            )
        )
    return sorted(violations, key=lambda v: (v.rule, v.column or "", v.check))


def _examples(values: pd.Series) -> list[Any]:
    distinct = values.drop_duplicates().head(MAX_EXAMPLES)
    return [None if pd.isna(value) else _plain(value) for value in distinct]


def _plain(value: Any) -> Any:
    """Converte escalares numpy para tipos nativos (serializaveis em JSON)."""
    return value.item() if hasattr(value, "item") else value
