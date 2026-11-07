"""Escrita de artefatos JSON com saida identica em qualquer sistema operacional."""

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Grava JSON indentado, UTF-8 e com fim de linha LF (inclusive no Windows).

    Sem ``newline="\n"``, o Windows grava CRLF e um relatorio versionado aparece como
    modificado em toda execucao, mesmo com o conteudo identico.
    """
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
