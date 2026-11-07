"""Esquema do dataset UCI 350: nomes originais (X1..X23, Y) e nomes do dicionario.

O ``data.csv`` oficial usa nomes genericos. Este modulo e a unica fonte do mapeamento.
Referencia: docs/DATASET.md#-esquema
"""

import pandas as pd

ID_COLUMN = "ID"
TARGET_COLUMN = "default"
RAW_TARGET_COLUMN = "Y"

PAY_STATUS_COLUMNS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL_COLUMNS = [f"BILL_AMT{i}" for i in range(1, 7)]
PAY_AMOUNT_COLUMNS = [f"PAY_AMT{i}" for i in range(1, 7)]

FEATURE_NAMES = [
    "LIMIT_BAL",
    "SEX",
    "EDUCATION",
    "MARRIAGE",
    "AGE",
    *PAY_STATUS_COLUMNS,
    *BILL_COLUMNS,
    *PAY_AMOUNT_COLUMNS,
]

RAW_FEATURE_NAMES = [f"X{i}" for i in range(1, len(FEATURE_NAMES) + 1)]
RAW_COLUMNS = [ID_COLUMN, *RAW_FEATURE_NAMES, RAW_TARGET_COLUMN]

RAW_TO_NAMED = {
    **dict(zip(RAW_FEATURE_NAMES, FEATURE_NAMES, strict=True)),
    RAW_TARGET_COLUMN: TARGET_COLUMN,
}

# Atributos usados apenas na auditoria de vies, nunca como feature (ADR 08).
AUDIT_ONLY_COLUMNS = ["SEX", "MARRIAGE"]


def rename_raw_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Renomeia ``X1..X23, Y`` para os nomes do dicionario da UCI.

    Args:
        frame: DataFrame no formato do ``data.csv`` oficial.

    Returns:
        Copia do DataFrame com as colunas renomeadas.

    Raises:
        ValueError: Se as colunas nao forem exatamente as do arquivo oficial.
    """
    if list(frame.columns) != RAW_COLUMNS:
        raise ValueError(f"Colunas inesperadas no arquivo bruto: {list(frame.columns)}")
    return frame.rename(columns=RAW_TO_NAMED)
