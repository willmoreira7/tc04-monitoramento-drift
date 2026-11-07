import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.data.cleaning import clean_reference
from src.data.schema import TARGET_COLUMN, rename_raw_columns
from src.data.split import split_dataset
from src.data.synthetic import generate_synthetic
from src.models.metrics import classification_metrics, ks_statistic, max_ks_threshold
from src.models.train import (
    CandidateResult,
    NoEligibleModelError,
    feature_columns,
    select_model,
    train_candidates,
)
from src.pipeline import prepare
from src.pipeline import train as train_stage

SEED = 42
CONFIG = load_config()["model"]


@pytest.fixture(scope="module")
def split():
    raw = rename_raw_columns(generate_synthetic(4_000, seed=SEED))
    cleaned, _ = clean_reference(raw, load_config()["cleaning"])
    return split_dataset(cleaned, load_config()["split"], SEED)


def _result(name: str, auc: float) -> CandidateResult:
    return CandidateResult(name=name, model=None, threshold=0.5, validation={"auc": auc})


def test_ks_is_one_for_perfect_separation_and_zero_for_constant_score() -> None:
    y = np.array([0, 0, 1, 1])
    assert ks_statistic(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert ks_statistic(y, np.full(4, 0.5)) == pytest.approx(0.0)


def test_max_ks_threshold_separates_classes() -> None:
    y = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    threshold = max_ks_threshold(y, scores)
    metrics = classification_metrics(y, scores, threshold)
    assert metrics["recall_default"] == 1.0
    assert metrics["precision_default"] == 1.0
    assert metrics["approval_rate"] == 0.5


def test_sensitive_and_key_columns_never_become_features(split) -> None:
    features = feature_columns(split.train, CONFIG)
    assert not {"ID", "SEX", "MARRIAGE", TARGET_COLUMN} & set(features)
    assert len(features) == 21


def test_trained_candidates_beat_dummy_on_synthetic(split) -> None:
    results = {r.name: r for r in train_candidates(split.train, split.validation, CONFIG, SEED)}
    assert set(results) == set(CONFIG["candidates"])
    assert results["logistic_regression"].validation["auc"] > results["dummy"].validation["auc"]
    assert results["xgboost"].validation["auc"] > results["dummy"].validation["auc"]


def test_select_prefers_interpretable_model_on_technical_tie() -> None:
    results = [
        _result("dummy", 0.50),
        _result("logistic_regression", 0.755),
        _result("xgboost", 0.760),
    ]
    assert select_model(results, CONFIG).name == "logistic_regression"


def test_select_takes_best_model_when_gap_exceeds_tolerance() -> None:
    results = [
        _result("dummy", 0.50),
        _result("logistic_regression", 0.71),
        _result("xgboost", 0.76),
    ]
    assert select_model(results, CONFIG).name == "xgboost"


def test_select_fails_when_no_candidate_reaches_minimum_auc() -> None:
    results = [
        _result("dummy", 0.50),
        _result("logistic_regression", 0.60),
        _result("xgboost", 0.65),
    ]
    with pytest.raises(NoEligibleModelError):
        select_model(results, CONFIG)


def test_train_stage_writes_model_metadata_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_file = tmp_path / "synthetic.csv"
    generate_synthetic(4_000, seed=SEED).to_csv(raw_file, index=False)
    monkeypatch.setattr(prepare, "source_path", lambda source: raw_file)
    monkeypatch.setattr("src.data.loader.synthetic_dataset_path", lambda: raw_file)
    prepare.prepare_data(prepare.DataSource.SYNTHETIC, tmp_path / "ref", tmp_path / "prod")

    summary = train_stage.train_model(tmp_path / "ref", tmp_path / "model", tmp_path / "report")

    model = joblib.load(tmp_path / "model" / train_stage.MODEL_FILE)
    test = pd.read_parquet(tmp_path / "ref" / "test.parquet")
    scores = model.predict_proba(test[summary["features"]])[:, 1]
    assert ((scores >= 0) & (scores <= 1)).all()
    report_file = tmp_path / "report" / train_stage.comparison_file("synthetic")
    assert report_file.name == "model_comparison.synthetic.json"
    assert not (tmp_path / "report" / train_stage.COMPARISON_FILE).exists()
    report = json.loads(report_file.read_text())
    assert report["promoted"] == summary["promoted"]
    assert {c["name"] for c in report["candidates"]} == set(CONFIG["candidates"])
    metadata = json.loads((tmp_path / "model" / train_stage.MODEL_METADATA_FILE).read_text())
    assert 0 < metadata["threshold"] <= 1
