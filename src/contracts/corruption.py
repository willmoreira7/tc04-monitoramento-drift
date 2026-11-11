"""Lote corrompido da demonstracao de bloqueio (docs/DATA_CONTRACTS.md#-demonstração).

Parte de uma amostra VALIDA e injeta um defeito por bloco de linhas, cada um declarado
em ``configs/pipeline.yaml`` (secao ``batches.corrupted``) e associado a uma regra:

| Bloco | Defeito                         | Regra |
|-------|---------------------------------|-------|
| 0     | ``LIMIT_BAL`` nulo              | C2    |
| 1     | ``ID`` repetido de outras linhas | C3    |
| 2     | ``AGE`` fora de [18, 100]       | C4    |
| 3     | ``EDUCATION`` fora do dicionario | C6    |
| 4     | ``PAY_AMT1`` negativo           | C8    |
| --    | Coluna extra (``CPF``)          | C1    |
"""

from typing import Any

import numpy as np
import pandas as pd

from src.data.schema import ID_COLUMN

DEFECT_BLOCKS = 5
# Valor ficticio e fixo: a coluna simula um vazamento de PII sem conter um CPF real.
FAKE_DOCUMENT = "000.000.000-00"


def corrupt_batch(sample: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Injeta os defeitos declarados numa amostra valida.

    Args:
        sample: Amostra valida do pool de producao.
        config: Secao ``batches.corrupted`` da configuracao.

    Returns:
        Copia da amostra com os defeitos injetados.

    Raises:
        ValueError: Se a amostra nao tiver linhas para todos os blocos e as copias de ID.
    """
    size = config["rows_per_defect"]
    if len(sample) < (DEFECT_BLOCKS + 1) * size:
        raise ValueError(f"Amostra pequena demais: precisa de {(DEFECT_BLOCKS + 1) * size} linhas")
    batch = sample.reset_index(drop=True).copy()
    block = [batch.index[i * size : (i + 1) * size] for i in range(DEFECT_BLOCKS)]

    batch["LIMIT_BAL"] = batch["LIMIT_BAL"].astype(float)
    batch.loc[block[0], "LIMIT_BAL"] = np.nan
    batch.loc[block[1], ID_COLUMN] = batch[ID_COLUMN].iloc[-size:].to_numpy()
    batch.loc[block[2], "AGE"] = np.resize(config["invalid_ages"], size)
    batch.loc[block[3], "EDUCATION"] = config["invalid_education"]
    batch.loc[block[4], "PAY_AMT1"] = -(batch.loc[block[4], "PAY_AMT1"] + 1)
    batch[config["extra_column"]] = FAKE_DOCUMENT
    return batch
