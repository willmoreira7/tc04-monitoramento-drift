"""Limpeza da referencia: aplicada uma vez, antes do split, com cada alteracao contada.

Em producao NADA disto e aplicado: o contrato de dados rejeita os mesmos problemas
(docs/DATA_CONTRACTS.md). Corrigir em silencio esconderia falhas de origem.
"""

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from src.data.schema import ID_COLUMN


@dataclass(frozen=True)
class CleaningReport:
    """Quantas linhas cada regra de limpeza alterou ou removeu."""

    rows_in: int
    education_recoded: int
    marriage_recoded: int
    duplicate_profiles_dropped: int
    rows_out: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def clean_reference(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, CleaningReport]:
    """Aplica a limpeza declarada em ``configs/pipeline.yaml`` (secao ``cleaning``).

    Args:
        frame: Dataset bruto com nomes do dicionario.
        config: Secao ``cleaning`` da configuracao.

    Returns:
        DataFrame limpo e o relatorio de alteracoes.
    """
    cleaned = frame.copy()
    education_mask = cleaned["EDUCATION"].isin(config["education_other_codes"])
    cleaned.loc[education_mask, "EDUCATION"] = config["education_other_value"]
    marriage_mask = cleaned["MARRIAGE"].isin(config["marriage_other_codes"])
    cleaned.loc[marriage_mask, "MARRIAGE"] = config["marriage_other_value"]

    duplicates = 0
    if config["drop_duplicate_profiles"]:
        profile = [column for column in cleaned.columns if column != ID_COLUMN]
        duplicated = cleaned.duplicated(subset=profile, keep="first")
        duplicates = int(duplicated.sum())
        cleaned = cleaned.loc[~duplicated].reset_index(drop=True)

    report = CleaningReport(
        rows_in=len(frame),
        education_recoded=int(education_mask.sum()),
        marriage_recoded=int(marriage_mask.sum()),
        duplicate_profiles_dropped=duplicates,
        rows_out=len(cleaned),
    )
    return cleaned, report
