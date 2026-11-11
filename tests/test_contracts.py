"""Contrato de dados: lote valido passa; cada regra critica bloqueia; avisos nao bloqueiam."""

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.contracts.corruption import corrupt_batch
from src.contracts.result import ContractViolationError
from src.contracts.validate import validate_batch
from src.data import loader
from src.data.cleaning import clean_reference
from src.data.schema import TARGET_COLUMN, rename_raw_columns
from src.data.synthetic import generate_synthetic
from src.pipeline import prepare
from src.pipeline import validate as stage
from src.pipeline.io import report_name

SEED = 42
CORRUPTED_RULES = ["C1", "C2", "C3", "C4", "C6", "C8"]


@pytest.fixture(scope="module")
def contract_config() -> dict:
    return load_config()["contract"]


@pytest.fixture(scope="module")
def valid_batch() -> pd.DataFrame:
    raw = rename_raw_columns(generate_synthetic(1_000, seed=SEED))
    cleaned, _ = clean_reference(raw, load_config()["cleaning"])
    return cleaned


def _set(column: str, value: object, rows: int = 2) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def mutate(frame: pd.DataFrame) -> pd.DataFrame:
        frame.loc[frame.index[:rows], column] = value
        return frame

    return mutate


def _with_null(column: str) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def mutate(frame: pd.DataFrame) -> pd.DataFrame:
        frame[column] = frame[column].astype(float)
        frame.loc[frame.index[0], column] = np.nan
        return frame

    return mutate


INVALID_CASES = {
    "extra_column": ("C1", lambda f: f.assign(CPF="000.000.000-00")),
    "missing_column": ("C1", lambda f: f.drop(columns="PAY_AMT3")),
    "wrong_dtype": ("C1", lambda f: f.assign(AGE=f["AGE"].astype(str))),
    "target_out_of_domain": ("C1", _set(TARGET_COLUMN, 2)),
    "null_value": ("C2", _with_null("BILL_AMT2")),
    "duplicated_id": ("C3", lambda f: f.assign(ID=f["ID"].where(f.index != 1, f["ID"].iloc[0]))),
    "underage": ("C4", _set("AGE", 15)),
    "too_old": ("C4", _set("AGE", 130)),
    "zero_limit": ("C5", _set("LIMIT_BAL", 0)),
    "limit_scale_error": ("C5", _set("LIMIT_BAL", 50_000_000)),
    "unknown_education": ("C6", _set("EDUCATION", 0)),
    "unknown_sex": ("C6", _set("SEX", 3)),
    "unknown_marriage": ("C6", _set("MARRIAGE", 0)),
    "pay_status_above": ("C7", _set("PAY_4", 10)),
    "pay_status_below": ("C7", _set("PAY_0", -3)),
    "negative_payment": ("C8", _set("PAY_AMT6", -1)),
}


def test_valid_batch_passes(valid_batch: pd.DataFrame, contract_config: dict) -> None:
    result = validate_batch(valid_batch, contract_config)
    assert result.passed
    assert result.violations == []


def test_batch_without_label_passes(valid_batch: pd.DataFrame, contract_config: dict) -> None:
    """Em producao o rotulo chega com atraso: o lote sem ``default`` e valido."""
    assert validate_batch(valid_batch.drop(columns=TARGET_COLUMN), contract_config).passed


@pytest.mark.parametrize("case", INVALID_CASES, ids=list(INVALID_CASES))
def test_each_critical_rule_blocks(
    case: str, valid_batch: pd.DataFrame, contract_config: dict
) -> None:
    rule, mutate = INVALID_CASES[case]
    result = validate_batch(mutate(valid_batch.copy()), contract_config)
    assert not result.passed
    assert rule in result.rules_violated


def test_every_critical_rule_has_an_invalid_case() -> None:
    assert {rule for rule, _ in INVALID_CASES.values()} == {f"C{i}" for i in range(1, 9)}


def test_validation_collects_all_violations_at_once(
    valid_batch: pd.DataFrame, contract_config: dict
) -> None:
    batch = corrupt_batch(valid_batch, load_config()["batches"]["corrupted"])
    result = validate_batch(batch, contract_config)
    assert result.rules_violated == CORRUPTED_RULES


def test_corruption_does_not_mutate_the_sample(valid_batch: pd.DataFrame) -> None:
    before = valid_batch.copy()
    corrupt_batch(valid_batch, load_config()["batches"]["corrupted"])
    pd.testing.assert_frame_equal(valid_batch, before)


def test_warnings_do_not_block(valid_batch: pd.DataFrame, contract_config: dict) -> None:
    batch = valid_batch.copy()
    batch.loc[batch.index[0], "BILL_AMT3"] = -500_000  # W1
    batch["PAY_0"] = np.where(np.arange(len(batch)) % 2 == 0, 3, batch["PAY_0"])  # W3
    batch = pd.concat([batch, batch.iloc[[1]].assign(ID=batch["ID"].max() + 1)])  # W4

    result = validate_batch(batch, contract_config, expected_rows=10_000, reference=valid_batch)

    assert result.passed
    assert [warning.rule for warning in result.warnings] == ["W1", "W2", "W3", "W4"]


def test_clean_batch_has_no_warnings(valid_batch: pd.DataFrame, contract_config: dict) -> None:
    result = validate_batch(
        valid_batch, contract_config, expected_rows=len(valid_batch), reference=valid_batch
    )
    assert result.warnings == []


def test_blocked_batch_goes_to_quarantine(valid_batch: pd.DataFrame, tmp_path: Path) -> None:
    batch = corrupt_batch(valid_batch, load_config()["batches"]["corrupted"])

    with pytest.raises(ContractViolationError) as blocked:
        stage.validate_stage(
            batch, "bad", "synthetic", quarantine_dir=tmp_path / "q", report_dir=tmp_path / "r"
        )

    assert blocked.value.result.rules_violated == CORRUPTED_RULES
    quarantined = pd.read_parquet(tmp_path / "q" / "bad" / stage.QUARANTINE_BATCH_FILE)
    assert len(quarantined) == len(batch)
    report = json.loads((tmp_path / "r" / "bad.synthetic.json").read_text())
    assert report["status"] == "blocked"
    assert report["rules_violated"] == CORRUPTED_RULES


def test_approved_batch_is_not_quarantined(valid_batch: pd.DataFrame, tmp_path: Path) -> None:
    result = stage.validate_stage(
        valid_batch, "ok", "real", quarantine_dir=tmp_path / "q", report_dir=tmp_path / "r"
    )
    assert result.passed
    assert not (tmp_path / "q").exists()
    assert json.loads((tmp_path / "r" / "ok.json").read_text())["status"] == "passed"


def test_demo_batches_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_file = tmp_path / "synthetic.csv"
    generate_synthetic(8_000, seed=SEED).to_csv(raw_file, index=False)
    monkeypatch.setattr(loader, "synthetic_dataset_path", lambda: raw_file)
    dirs = {
        "reference_dir": tmp_path / "ref",
        "production_dir": tmp_path / "prod",
    }
    prepare.prepare_data(prepare.DataSource.SYNTHETIC, validation_report_dir=tmp_path / "r", **dirs)
    stage_dirs = {**dirs, "quarantine_dir": tmp_path / "q", "report_dir": tmp_path / "r"}

    assert stage.validate_demo_batch(stage.DemoBatch.VALID, **stage_dirs).passed
    with pytest.raises(ContractViolationError):
        stage.validate_demo_batch(stage.DemoBatch.CORRUPTED, **stage_dirs)
    assert (tmp_path / "q" / "demo_corrupted" / stage.QUARANTINE_BATCH_FILE).is_file()
    assert not (tmp_path / "q" / "demo_valid").exists()


@pytest.mark.parametrize(
    ("source", "expected"),
    [("real", "batch.json"), ("synthetic", "batch.synthetic.json")],
)
def test_report_name_never_overwrites_real_evidence(source: str, expected: str) -> None:
    assert report_name("batch.json", source) == expected
