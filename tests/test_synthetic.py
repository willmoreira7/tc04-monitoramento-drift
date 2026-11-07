import pandas as pd
import pytest

from src.data.schema import RAW_COLUMNS, rename_raw_columns
from src.data.synthetic import generate_synthetic

ROWS = 5_000


@pytest.fixture(scope="module")
def synthetic() -> pd.DataFrame:
    return generate_synthetic(ROWS, seed=42)


def test_has_official_raw_schema(synthetic: pd.DataFrame) -> None:
    assert list(synthetic.columns) == RAW_COLUMNS
    assert len(synthetic) == ROWS


def test_is_deterministic_for_same_seed(synthetic: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(synthetic, generate_synthetic(ROWS, seed=42))


def test_values_stay_in_documented_domains(synthetic: pd.DataFrame) -> None:
    named = rename_raw_columns(synthetic)
    pay_status = named[["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]]

    assert named["ID"].is_unique
    assert named.notna().all().all()
    assert named["AGE"].between(21, 79).all()
    assert named["LIMIT_BAL"].between(10_000, 1_000_000).all()
    assert set(named["SEX"]) <= {1, 2}
    assert pay_status.isin(range(-2, 10)).all().all()
    assert (named[[f"PAY_AMT{i}" for i in range(1, 7)]] >= 0).all().all()


def test_default_rate_is_close_to_real_dataset(synthetic: pd.DataFrame) -> None:
    assert 0.15 <= synthetic["Y"].mean() <= 0.30


def test_reproduces_known_out_of_dictionary_codes(synthetic: pd.DataFrame) -> None:
    named = rename_raw_columns(synthetic)
    assert named["EDUCATION"].isin([0, 5, 6]).any()
