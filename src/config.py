"""Caminhos do projeto, seed e carregamento da configuracao YAML."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
REFERENCE_DIR = DATA_DIR / "reference"
PRODUCTION_DIR = DATA_DIR / "production"
QUARANTINE_DIR = DATA_DIR / "quarantine"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"

PIPELINE_CONFIG = CONFIGS_DIR / "pipeline.yaml"


@lru_cache(maxsize=1)
def load_config(path: Path = PIPELINE_CONFIG) -> dict[str, Any]:
    """Carrega o YAML de configuracao do pipeline.

    Args:
        path: Caminho do arquivo YAML.

    Returns:
        Dicionario com a configuracao.
    """
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_seed() -> int:
    """Retorna a seed global declarada em ``configs/pipeline.yaml``."""
    return int(load_config()["seed"])


def raw_dataset_path() -> Path:
    """Caminho do dataset real baixado da UCI."""
    return RAW_DIR / load_config()["dataset"]["raw_file"]


def synthetic_dataset_path() -> Path:
    """Caminho do dataset sintetico de fallback."""
    return RAW_DIR / load_config()["dataset"]["synthetic_file"]
