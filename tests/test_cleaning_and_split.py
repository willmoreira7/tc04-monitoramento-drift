import json
from pathlib import Path

import pandas as pd
import pytest

from src.config import load_config
from src.data import loader
from src.data.cleaning import clean_reference
from src.data.loader import DataSource, load_raw
from src.data.schema import TARGET_COLUMN, rename_raw_columns
from src.data.split import (
    DataSplit,
    LeakageError,
    assert_disjoint,
    default_rate_gap_pp,
    split_dataset,
)
from src.data.synthetic import generate_synthetic
from src.pipeline import prepare

SEED = 42


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return rename_raw_columns(generate_synthetic(6_000, seed=SEED))


@pytest.fixture(scope="module")
def cleaned(raw: pd.DataFrame) -> pd.DataFrame:
    frame, _ = clean_reference(raw, load_config()["cleaning"])
    return frame


@pytest.fixture(scope="module")
def split(cleaned: pd.DataFrame) -> DataSplit:
    return split_dataset(cleaned, load_config()["split"], SEED)


def test_cleaning_recodes_out_of_dictionary_codes(raw: pd.DataFrame) -> None:
    cleaned, report = clean_reference(raw, load_config()["cleaning"])

    assert set(cleaned["EDUCATION"]) <= {1, 2, 3, 4}
    assert set(cleaned["MARRIAGE"]) <= {1, 2, 3}
    assert report.education_recoded == raw["EDUCATION"].isin([0, 5, 6]).sum()
    assert report.marriage_recoded == (raw["MARRIAGE"] == 0).sum()


def test_cleaning_drops_only_extra_copies_of_identical_profiles(raw: pd.DataFrame) -> None:
    profile = raw.drop(columns="ID").iloc[[0]]
    duplicated = pd.concat([raw, profile.assign(ID=[raw["ID"].max() + 1])], ignore_index=True)

    cleaned, report = clean_reference(duplicated, load_config()["cleaning"])

    assert report.duplicate_profiles_dropped >= 1
    assert report.rows_out == len(cleaned) == len(duplicated) - report.duplicate_profiles_dropped
    assert raw["ID"].iloc[0] in set(cleaned["ID"])


def test_cleaning_does_not_mutate_input(raw: pd.DataFrame) -> None:
    before = raw.copy()
    clean_reference(raw, load_config()["cleaning"])
    pd.testing.assert_frame_equal(raw, before)


def test_split_is_disjoint_and_complete(cleaned: pd.DataFrame, split: DataSplit) -> None:
    all_ids = pd.concat([subset["ID"] for subset in split.as_dict().values()])
    assert all_ids.is_unique
    assert set(all_ids) == set(cleaned["ID"])


def test_production_pool_never_reaches_reference(split: DataSplit) -> None:
    assert not set(split.production_pool["ID"]) & set(split.reference["ID"])


def test_no_production_profile_reaches_training(split: DataSplit) -> None:
    """Alem do ID, o conteudo: nenhum perfil do pool aparece no treino com outro ID."""
    profile = [column for column in split.train.columns if column != "ID"]
    train_profiles = set(split.train[profile].itertuples(index=False, name=None))
    pool_profiles = set(split.production_pool[profile].itertuples(index=False, name=None))
    assert not train_profiles & pool_profiles


def test_split_preserves_default_rate(split: DataSplit) -> None:
    assert default_rate_gap_pp(split) < load_config()["split"]["max_default_rate_gap_pp"]
    rates = [subset[TARGET_COLUMN].mean() for subset in split.as_dict().values()]
    assert max(rates) - min(rates) < 0.02


def test_split_is_reproducible(cleaned: pd.DataFrame, split: DataSplit) -> None:
    again = split_dataset(cleaned, load_config()["split"], SEED)
    pd.testing.assert_frame_equal(split.train, again.train)
    pd.testing.assert_frame_equal(split.production_pool, again.production_pool)


def test_assert_disjoint_detects_leakage(split: DataSplit) -> None:
    leaked = DataSplit(
        split.train,
        split.validation,
        split.test,
        pd.concat([split.production_pool, split.train.head(1)]),
    )
    with pytest.raises(LeakageError):
        assert_disjoint(leaked)


def test_load_raw_explains_how_to_get_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(loader, "synthetic_dataset_path", lambda: tmp_path / "missing.csv")
    with pytest.raises(FileNotFoundError, match="--synthetic"):
        load_raw(DataSource.SYNTHETIC)


def test_prepare_writes_parquet_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_file = tmp_path / "synthetic.csv"
    generate_synthetic(3_000, seed=SEED).to_csv(raw_file, index=False)
    monkeypatch.setattr(loader, "synthetic_dataset_path", lambda: raw_file)

    metadata = prepare.prepare_data(
        DataSource.SYNTHETIC,
        tmp_path / "reference",
        tmp_path / "production",
        tmp_path / "validation",
    )

    for name in ("train", "validation", "test"):
        assert (tmp_path / "reference" / f"{name}.parquet").is_file()
    assert (tmp_path / "production" / "pool.parquet").is_file()
    for subset in ("reference", "production_pool"):
        report = json.loads((tmp_path / "validation" / f"{subset}.synthetic.json").read_text())
        assert report["status"] == "passed"
    saved = json.loads((tmp_path / "reference" / prepare.METADATA_FILE).read_text())
    assert saved == metadata
    assert (
        sum(subset["rows"] for subset in metadata["subsets"].values())
        == (metadata["cleaning"]["rows_out"])
    )
