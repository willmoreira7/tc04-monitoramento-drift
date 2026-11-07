"""Carga do dataset bruto (real ou sintetico) ja com os nomes do dicionario."""

from enum import StrEnum
from pathlib import Path

import pandas as pd

from src.config import raw_dataset_path, synthetic_dataset_path
from src.data.schema import rename_raw_columns


class DataSource(StrEnum):
    """Origem do dataset bruto."""

    REAL = "real"
    SYNTHETIC = "synthetic"


def source_path(source: DataSource) -> Path:
    """Caminho do arquivo bruto de cada origem."""
    return raw_dataset_path() if source == DataSource.REAL else synthetic_dataset_path()


def load_raw(source: DataSource = DataSource.REAL) -> pd.DataFrame:
    """Le o arquivo bruto e renomeia as colunas para o dicionario da UCI.

    Args:
        source: Dataset real (UCI) ou sintetico.

    Returns:
        DataFrame com ``ID``, as 23 features nomeadas e ``default``.

    Raises:
        FileNotFoundError: Se o arquivo nao existir, com o comando que o gera.
    """
    path = source_path(source)
    if not path.is_file():
        flag = " --synthetic" if source == DataSource.SYNTHETIC else ""
        raise FileNotFoundError(
            f"{path} nao encontrado. Rode `uv run python scripts/download_data.py{flag}`."
        )
    return rename_raw_columns(pd.read_csv(path))
