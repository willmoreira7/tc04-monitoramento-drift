"""Simulacao dos lotes M01..M06 a partir do pool de producao (docs/DRIFT.md, ADR 14).

Os cenarios sao declarados em ``configs/drift_scenarios.yaml``; este modulo so os
interpreta. Tres mecanismos, sempre nesta ordem:

1. ``resample``: pesos de amostragem favorecem um perfil (covariate shift).
2. ``relabel``: bons pagadores de um perfil passam a inadimplir, features intactas
   (concept drift). Vem antes do ``scale`` para julgar o cliente como ele era.
3. ``scale``: valores nominais multiplicados, risco real igual (drift nominal).
"""

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from src.data.schema import TARGET_COLUMN

UTILIZATION_BILL = "BILL_AMT1"
UTILIZATION_LIMIT = "LIMIT_BAL"
LAST_PAY_STATUS = "PAY_0"


def simulate_batch(
    pool: pd.DataFrame, scenario: Mapping[str, Any], rows: int, seed: int
) -> pd.DataFrame:
    """Gera um lote: amostra do pool sem reposicao, depois as perturbacoes do cenario.

    Args:
        pool: Pool de producao (nunca usado no treino).
        scenario: Um lote de ``configs/drift_scenarios.yaml``.
        rows: Tamanho do lote.
        seed: Seed do lote (amostragem e reetiquetagem).

    Returns:
        Lote com as mesmas colunas e tipos do pool.
    """
    weights = sampling_weights(pool, scenario.get("resample", []))
    batch = pool.sample(n=rows, weights=weights, random_state=seed).reset_index(drop=True)
    if "relabel" in scenario:
        batch = relabel(batch, scenario["relabel"], seed)
    for step in scenario.get("scale", []):
        batch = scale(batch, step["columns"], step["factor"])
    return batch


def sampling_weights(pool: pd.DataFrame, rules: Sequence[Mapping[str, Any]]) -> pd.Series | None:
    """Pesos de amostragem: cada regra multiplica o peso das linhas do perfil.

    Uma regra tem ``column``, ``weight`` e um limite: ``below`` (valor < limite) ou
    ``at_least`` (valor >= limite). Sem regras, a amostragem e uniforme (``None``).
    """
    if not rules:
        return None
    weights = pd.Series(1.0, index=pool.index)
    for rule in rules:
        values = pool[rule["column"]]
        selected = values < rule["below"] if "below" in rule else values >= rule["at_least"]
        weights.loc[selected] *= rule["weight"]
    return weights


def relabel(batch: pd.DataFrame, rule: Mapping[str, Any], seed: int) -> pd.DataFrame:
    """Concept drift: bons pagadores em dia e endividados viram inadimplentes.

    Elegivel: ``default == 0``, ``PAY_0 <= max_pay_status`` e utilizacao
    (``BILL_AMT1 / LIMIT_BAL``) ``>= min_utilization``. Cada elegivel vira inadimplente
    com ``probability``. As features nao mudam: so a relacao entre elas e o rotulo.
    """
    utilization = batch[UTILIZATION_BILL].clip(lower=0) / batch[UTILIZATION_LIMIT]
    eligible = (
        (batch[TARGET_COLUMN] == 0)
        & (batch[LAST_PAY_STATUS] <= rule["max_pay_status"])
        & (utilization >= rule["min_utilization"])
    )
    draws = np.random.default_rng(seed).random(len(batch))
    relabeled = batch.copy()
    relabeled.loc[eligible & (draws < rule["probability"]), TARGET_COLUMN] = 1
    return relabeled


def scale(batch: pd.DataFrame, columns: Sequence[str], factor: float) -> pd.DataFrame:
    """Drift nominal: multiplica as colunas e arredonda, mantendo o tipo (contrato C1)."""
    scaled = batch.copy()
    columns = list(columns)
    scaled[columns] = (scaled[columns] * factor).round().astype(batch[columns].dtypes)
    return scaled
