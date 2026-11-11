"""Schema Pandera do contrato de dados (regras criticas C1..C8 de docs/DATA_CONTRACTS.md).

As regras estruturais valem para todas as colunas: C1 (esquema exato e tipos), C2 (sem
nulos) e C3 (chave sem duplicata). As regras de dominio (C4..C8) sao declaradas por
coluna junto com o identificador da regra, para que cada falha do Pandera seja
atribuida a regra correta no relatorio. Os limites vem de ``configs/pipeline.yaml``.
"""

from dataclasses import dataclass
from typing import Any

import pandera.pandas as pa

from src.data.schema import (
    FEATURE_NAMES,
    ID_COLUMN,
    PAY_AMOUNT_COLUMNS,
    PAY_STATUS_COLUMNS,
    TARGET_COLUMN,
)

INTEGER = "int64"
SCHEMA_RULE = "C1"
# Verificacoes estruturais do Pandera -> regra do contrato.
STRUCTURAL_RULES = {
    "column_in_schema": "C1",
    "column_in_dataframe": "C1",
    "not_nullable": "C2",
    "field_uniqueness": "C3",
}


@dataclass(frozen=True)
class Contract:
    """Schema Pandera e a regra de dominio de cada coluna."""

    schema: pa.DataFrameSchema
    domain_rules: dict[str, str]

    def rule_of(self, column: str | None, check: str) -> str:
        """Regra do contrato violada por uma falha do Pandera.

        Args:
            column: Coluna reportada pelo Pandera (``None`` para falhas de esquema).
            check: Descricao da verificacao, como ``in_range(18, 100)`` ou ``not_nullable``.

        Returns:
            Identificador da regra, como ``C4``.
        """
        if check in STRUCTURAL_RULES:
            return STRUCTURAL_RULES[check]
        if check.startswith("dtype("):
            return SCHEMA_RULE
        return self.domain_rules.get(column or "", SCHEMA_RULE)


def build_contract(config: dict[str, Any]) -> Contract:
    """Monta o contrato a partir da secao ``contract`` da configuracao.

    Args:
        config: Secao ``contract`` de ``configs/pipeline.yaml``.

    Returns:
        Contrato com schema estrito (nenhuma coluna extra) e regras por coluna.
    """
    domain = _domain_checks(config)
    columns = {
        ID_COLUMN: pa.Column(INTEGER, unique=True),
        **{name: pa.Column(INTEGER, domain.get(name, (None, []))[1]) for name in FEATURE_NAMES},
        # O rotulo chega com atraso em producao: o lote pode vir sem ele.
        TARGET_COLUMN: pa.Column(INTEGER, domain[TARGET_COLUMN][1], required=False),
    }
    schema = pa.DataFrameSchema(columns, strict=True, ordered=False)
    return Contract(schema, {name: rule for name, (rule, _) in domain.items()})


def _domain_checks(config: dict[str, Any]) -> dict[str, tuple[str, list[pa.Check]]]:
    age_min, age_max = config["age_range"]
    pay_min, pay_max = config["pay_status_range"]
    return {
        "AGE": ("C4", [pa.Check.in_range(age_min, age_max)]),
        "LIMIT_BAL": ("C5", [pa.Check.gt(0), pa.Check.le(config["limit_bal_max"])]),
        "EDUCATION": ("C6", [pa.Check.isin(config["education_codes"])]),
        "SEX": ("C6", [pa.Check.isin(config["sex_codes"])]),
        "MARRIAGE": ("C6", [pa.Check.isin(config["marriage_codes"])]),
        **{name: ("C7", [pa.Check.in_range(pay_min, pay_max)]) for name in PAY_STATUS_COLUMNS},
        **{name: ("C8", [pa.Check.ge(0)]) for name in PAY_AMOUNT_COLUMNS},
        TARGET_COLUMN: (SCHEMA_RULE, [pa.Check.isin([0, 1])]),
    }
