"""Gerador sintetico no mesmo formato do ``data.csv`` da UCI (ID, X1..X23, Y).

Serve ao CI e a quem nao conseguir baixar o dataset real. Todos os parametros estao
declarados neste modulo; nenhuma linha do dataset real e copiada. Os dados validam o
pipeline, mas NAO reproduzem as metricas documentadas.

As anomalias conhecidas do dataset real (codigos fora do dicionario em EDUCATION e
MARRIAGE) sao reproduzidas em baixa frequencia para que a limpeza seja exercitada.
"""

import numpy as np
import pandas as pd

from src.data.schema import (
    BILL_COLUMNS,
    FEATURE_NAMES,
    ID_COLUMN,
    PAY_AMOUNT_COLUMNS,
    PAY_STATUS_COLUMNS,
    RAW_TO_NAMED,
)

NAMED_TO_RAW = {named: raw for raw, named in RAW_TO_NAMED.items()}

SEX_P = {1: 0.40, 2: 0.60}
EDUCATION_P = {0: 0.001, 1: 0.35, 2: 0.47, 3: 0.16, 4: 0.004, 5: 0.01, 6: 0.005}
MARRIAGE_P = {0: 0.002, 1: 0.455, 2: 0.532, 3: 0.011}
PAY_STATUS_P = {-2: 0.09, -1: 0.19, 0: 0.49, 1: 0.12, 2: 0.09, 3: 0.012, 4: 0.008}
PAY_PERSISTENCE = 0.6
BASE_LOGIT = -1.9


def generate_synthetic(rows: int, seed: int) -> pd.DataFrame:
    """Gera um dataset sintetico no formato bruto da UCI.

    Args:
        rows: Numero de linhas.
        seed: Seed do gerador; mesma seed gera o mesmo arquivo.

    Returns:
        DataFrame com as colunas ``ID, X1..X23, Y``.
    """
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({ID_COLUMN: np.arange(1, rows + 1)})
    frame["LIMIT_BAL"] = _limit_balance(rng, rows)
    frame["SEX"] = _categorical(rng, SEX_P, rows)
    frame["EDUCATION"] = _categorical(rng, EDUCATION_P, rows)
    frame["MARRIAGE"] = _categorical(rng, MARRIAGE_P, rows)
    frame["AGE"] = np.clip(21 + rng.gamma(shape=3.0, scale=5.0, size=rows), 21, 79).astype(int)
    frame[PAY_STATUS_COLUMNS] = _pay_status(rng, rows)
    frame[BILL_COLUMNS] = _bills(rng, frame["LIMIT_BAL"].to_numpy())
    frame[PAY_AMOUNT_COLUMNS] = _payments(rng, frame[BILL_COLUMNS].to_numpy())
    frame["Y"] = _target(rng, frame)
    return frame[[ID_COLUMN, *FEATURE_NAMES, "Y"]].rename(columns=NAMED_TO_RAW)


def _categorical(rng: np.random.Generator, probs: dict[int, float], rows: int) -> np.ndarray:
    values = np.array(list(probs))
    weights = np.array(list(probs.values()))
    return rng.choice(values, size=rows, p=weights / weights.sum())


def _limit_balance(rng: np.random.Generator, rows: int) -> np.ndarray:
    raw = rng.lognormal(mean=11.8, sigma=0.75, size=rows)
    return (np.clip(raw, 10_000, 1_000_000) // 10_000 * 10_000).astype(int)


def _pay_status(rng: np.random.Generator, rows: int) -> np.ndarray:
    status = np.empty((rows, len(PAY_STATUS_COLUMNS)), dtype=int)
    status[:, 0] = _categorical(rng, PAY_STATUS_P, rows)
    for month in range(1, len(PAY_STATUS_COLUMNS)):
        keep = rng.random(rows) < PAY_PERSISTENCE
        fresh = _categorical(rng, PAY_STATUS_P, rows)
        status[:, month] = np.where(keep, status[:, month - 1], fresh)
    return status


def _bills(rng: np.random.Generator, limit: np.ndarray) -> np.ndarray:
    utilization = rng.beta(0.8, 1.6, size=limit.size)
    monthly_noise = rng.normal(1.0, 0.08, size=(limit.size, len(BILL_COLUMNS)))
    bills = limit[:, None] * utilization[:, None] * monthly_noise
    credit_balance = rng.random(limit.size) < 0.02
    bills[credit_balance, 0] = -rng.uniform(100, 5_000, size=credit_balance.sum())
    return bills.round().astype(int)


def _payments(rng: np.random.Generator, bills: np.ndarray) -> np.ndarray:
    share = rng.beta(0.6, 4.0, size=bills.shape)
    return np.clip(bills * share, 0, None).round().astype(int)


def _target(rng: np.random.Generator, frame: pd.DataFrame) -> np.ndarray:
    utilization = frame["BILL_AMT1"].clip(lower=0) / frame["LIMIT_BAL"]
    logit = (
        BASE_LOGIT
        + 0.75 * frame["PAY_0"].clip(lower=0)
        + 0.8 * utilization
        - 0.25 * np.log(frame["LIMIT_BAL"] / 100_000)
    )
    probability = 1 / (1 + np.exp(-logit))
    return (rng.random(len(frame)) < probability).astype(int)
