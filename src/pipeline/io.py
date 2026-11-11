"""Leitura e escrita de artefatos compartilhados pelos estagios do pipeline."""

import json
from pathlib import Path
from typing import Any

import pandas as pd

METADATA_FILE = "split_metadata.json"
SYNTHETIC_SUFFIX = ".synthetic"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Grava JSON indentado, UTF-8 e com fim de linha LF (inclusive no Windows).

    Sem ``newline="\n"``, o Windows grava CRLF e um relatorio versionado aparece como
    modificado em toda execucao, mesmo com o conteudo identico.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_prepared(path: Path) -> pd.DataFrame:
    """Le um Parquet gerado por ``prepare_data.py``.

    Raises:
        FileNotFoundError: Se o arquivo nao existir, com o comando que o gera.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} nao encontrado. Rode `uv run python scripts/prepare_data.py`."
        )
    return pd.read_parquet(path)


def read_split_metadata(reference_dir: Path) -> dict[str, Any]:
    """Metadados do split (origem real/sintetica, hash, contagens)."""
    return json.loads((reference_dir / METADATA_FILE).read_text(encoding="utf-8"))


def report_name(filename: str, source: str) -> str:
    """Nome de um relatorio versionado conforme a origem dos dados.

    So o relatorio do dataset real e evidencia; o do sintetico ganha ``.synthetic`` antes
    da extensao, e ignorado pelo Git e nunca sobrescreve o real.
    """
    if source == "real":
        return filename
    stem, _, extension = filename.rpartition(".")
    return f"{stem}{SYNTHETIC_SUFFIX}.{extension}"
