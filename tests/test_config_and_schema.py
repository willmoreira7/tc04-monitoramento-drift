import pandas as pd
import pytest

from src.config import PROJECT_ROOT, get_seed, load_config, raw_dataset_path
from src.data.schema import FEATURE_NAMES, RAW_COLUMNS, RAW_TO_NAMED, rename_raw_columns


def test_config_declares_seed_and_dataset_integrity() -> None:
    config = load_config()
    assert get_seed() == 42
    assert len(config["dataset"]["sha256"]) == 64
    assert config["dataset"]["license"] == "CC BY 4.0"


def test_paths_resolve_inside_project() -> None:
    assert raw_dataset_path().is_relative_to(PROJECT_ROOT / "data" / "raw")


def test_schema_maps_all_23_features_and_target() -> None:
    assert len(FEATURE_NAMES) == 23
    assert RAW_TO_NAMED["X1"] == "LIMIT_BAL"
    assert RAW_TO_NAMED["X6"] == "PAY_0"
    assert RAW_TO_NAMED["Y"] == "default"


def test_rename_rejects_unexpected_layout() -> None:
    frame = pd.DataFrame(columns=[*RAW_COLUMNS, "CPF"])
    with pytest.raises(ValueError, match="Colunas inesperadas"):
        rename_raw_columns(frame)
