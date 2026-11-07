"""Download do dataset UCI 350 com conferencia de integridade (SHA256).

O arquivo so e gravado no destino depois de conferido: um download interrompido ou
adulterado nunca fica em ``data/raw/`` com o nome do arquivo valido.
"""

import hashlib
from pathlib import Path

import requests

from src.monitoring.log import get_logger

logger = get_logger(__name__)

CHUNK_SIZE = 1 << 20
TIMEOUT_SECONDS = 60


class DatasetIntegrityError(RuntimeError):
    """O arquivo baixado nao corresponde ao SHA256 esperado."""


def sha256_of(path: Path) -> str:
    """Calcula o SHA256 de um arquivo.

    Args:
        path: Arquivo a ser lido.

    Returns:
        Hash hexadecimal.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid(path: Path, expected_sha256: str) -> bool:
    """Indica se o arquivo existe e tem o hash esperado."""
    return path.is_file() and sha256_of(path) == expected_sha256


def download_dataset(url: str, destination: Path, expected_sha256: str) -> Path:
    """Baixa o dataset e o grava em ``destination`` somente se o hash conferir.

    Se o arquivo ja existir com o hash correto, nada e baixado.

    Args:
        url: URL publica do arquivo.
        destination: Caminho final do arquivo.
        expected_sha256: Hash esperado.

    Returns:
        O caminho do arquivo valido.

    Raises:
        DatasetIntegrityError: Se o hash do arquivo baixado divergir.
        requests.RequestException: Se o download falhar.
    """
    if is_valid(destination, expected_sha256):
        logger.info("dataset_already_present", path=str(destination))
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    logger.info("dataset_download_started", url=url)
    _stream_to_file(url, partial)

    actual = sha256_of(partial)
    if actual != expected_sha256:
        partial.unlink()
        raise DatasetIntegrityError(
            f"SHA256 divergente: esperado {expected_sha256}, obtido {actual}"
        )

    partial.replace(destination)
    logger.info("dataset_download_finished", path=str(destination), sha256=actual)
    return destination


def _stream_to_file(url: str, target: Path) -> None:
    with requests.get(url, stream=True, timeout=TIMEOUT_SECONDS) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                handle.write(chunk)
