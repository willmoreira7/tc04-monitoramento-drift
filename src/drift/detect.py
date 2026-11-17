"""Deteccao de drift com o Evidently: PSI e KS configurados explicitamente, coluna a coluna.

O Evidently escolhe Wasserstein/Jensen-Shannon por padrao em amostras > 1000 linhas; aqui
cada coluna recebe ``ValueDrift(method="psi")`` e ``ValueDrift(method="ks")``. O PSI vem
so do Evidently (uma unica implementacao no projeto). O KS do Evidently devolve o
p-valor; a estatistica D, que mede o tamanho da diferenca, e calculada com o scipy.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.core.report import Snapshot
from evidently.metrics import ValueDrift
from scipy.stats import ks_2samp

PSI = "psi"
KS = "ks"


@dataclass(frozen=True)
class ColumnDrift:
    """Resultado dos testes de uma coluna.

    Attributes:
        column: Coluna comparada.
        psi: Population Stability Index (decisao do alerta).
        ks_d: Estatistica D do Kolmogorov-Smirnov (tamanho do efeito).
        ks_pvalue: p-valor do KS (com n grande, acusa diferencas irrelevantes).
    """

    column: str
    psi: float
    ks_d: float
    ks_pvalue: float


def detect_drift(
    reference: pd.DataFrame, current: pd.DataFrame, columns: list[str]
) -> tuple[dict[str, ColumnDrift], Snapshot]:
    """Compara o lote com a referencia em cada coluna.

    Args:
        reference: Janela de referencia.
        current: Lote atual.
        columns: Colunas numericas a comparar (features, populacao e score).

    Returns:
        Resultado por coluna e o snapshot do Evidently (para o relatorio HTML).
    """
    definition = DataDefinition(numerical_columns=columns)
    report = Report([ValueDrift(column=c, method=m) for c in columns for m in (PSI, KS)])
    snapshot = report.run(
        reference_data=Dataset.from_pandas(reference[columns], data_definition=definition),
        current_data=Dataset.from_pandas(current[columns], data_definition=definition),
    )
    values = _metric_values(snapshot)
    results = {
        column: ColumnDrift(
            column=column,
            psi=values[column, PSI],
            ks_d=float(ks_2samp(reference[column], current[column]).statistic),
            ks_pvalue=values[column, KS],
        )
        for column in columns
    }
    return results, snapshot


def _metric_values(snapshot: Snapshot) -> dict[tuple[str, str], float]:
    """Valor de cada ``ValueDrift`` do snapshot, por (coluna, metodo)."""
    metrics: list[dict[str, Any]] = snapshot.dict()["metrics"]
    return {
        (metric["config"]["column"], metric["config"]["method"]): float(metric["value"])
        for metric in metrics
    }
