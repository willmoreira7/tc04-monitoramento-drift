"""Separacao unica entre referencia (treino/validacao/teste) e pool de producao.

O split e estratificado pelo target, feito UMA vez, com seed fixa. O pool de producao
nunca toca o treino: e a fonte dos lotes com drift simulado (docs/DATASET.md).
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

from src.data.schema import ID_COLUMN, TARGET_COLUMN


class LeakageError(RuntimeError):
    """Uma mesma linha apareceu em dois conjuntos que deveriam ser disjuntos."""


@dataclass(frozen=True)
class DataSplit:
    """Conjuntos resultantes do split."""

    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    production_pool: pd.DataFrame

    def as_dict(self) -> dict[str, pd.DataFrame]:
        return {
            "train": self.train,
            "validation": self.validation,
            "test": self.test,
            "production_pool": self.production_pool,
        }

    @property
    def reference(self) -> pd.DataFrame:
        return pd.concat([self.train, self.validation, self.test], ignore_index=True)


def split_dataset(frame: pd.DataFrame, config: dict[str, Any], seed: int) -> DataSplit:
    """Divide o dataset limpo em referencia (treino/val/teste) e pool de producao.

    Args:
        frame: Dataset limpo.
        config: Secao ``split`` da configuracao.
        seed: Seed global.

    Returns:
        Os quatro conjuntos, disjuntos.

    Raises:
        LeakageError: Se algum ``ID`` aparecer em mais de um conjunto.
    """
    reference, production = _stratified(frame, config["production_fraction"], seed)
    holdout_fraction = config["validation_fraction"] + config["test_fraction"]
    train, holdout = _stratified(reference, holdout_fraction, seed)
    test_share = config["test_fraction"] / holdout_fraction
    validation, test = _stratified(holdout, test_share, seed)
    split = DataSplit(train, validation, test, production)
    assert_disjoint(split)
    return split


def assert_disjoint(split: DataSplit) -> None:
    """Garante que nenhum ``ID`` aparece em dois conjuntos."""
    seen: set[int] = set()
    for name, subset in split.as_dict().items():
        ids = set(subset[ID_COLUMN])
        overlap = seen & ids
        if overlap:
            raise LeakageError(f"{len(overlap)} IDs de '{name}' ja estavam em outro conjunto")
        seen |= ids


def default_rate_gap_pp(split: DataSplit) -> float:
    """Diferenca, em pontos percentuais, da inadimplencia entre referencia e producao."""
    reference_rate = split.reference[TARGET_COLUMN].mean()
    production_rate = split.production_pool[TARGET_COLUMN].mean()
    return float(abs(reference_rate - production_rate) * 100)


def _stratified(
    frame: pd.DataFrame, second_fraction: float, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    first, second = train_test_split(
        frame, test_size=second_fraction, stratify=frame[TARGET_COLUMN], random_state=seed
    )
    return first.reset_index(drop=True), second.reset_index(drop=True)
