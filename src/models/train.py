"""Treino, avaliacao e promocao dos candidatos (ADR 04: comparacao enxuta).

Os candidatos sao avaliados na validacao; o teste so reporta o resultado do promovido.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from src.data.schema import TARGET_COLUMN
from src.models.metrics import classification_metrics, max_ks_threshold


class NoEligibleModelError(RuntimeError):
    """Nenhum candidato atingiu o criterio de promocao."""


@dataclass
class CandidateResult:
    """Modelo treinado e suas metricas."""

    name: str
    model: Pipeline
    threshold: float
    validation: dict[str, float]
    test: dict[str, float] = field(default_factory=dict)


def feature_columns(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    """Colunas usadas como feature (tudo menos as excluidas na config)."""
    return [column for column in frame.columns if column not in config["excluded_columns"]]


def build_candidate(name: str, features: list[str], config: dict[str, Any], seed: int) -> Pipeline:
    """Monta o pipeline de pre-processamento + estimador de um candidato."""
    categorical = [c for c in config["categorical_columns"] if c in features]
    numeric = [c for c in features if c not in categorical]
    preprocess = ColumnTransformer(
        [
            ("numeric", StandardScaler(), numeric),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
        ]
    )
    estimators = {
        "dummy": DummyClassifier(strategy="stratified", random_state=seed),
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=seed),
        "xgboost": XGBClassifier(random_state=seed, n_jobs=1, eval_metric="logloss"),
    }
    return Pipeline([("preprocess", preprocess), ("model", estimators[name])])


def train_candidates(
    train: pd.DataFrame, validation: pd.DataFrame, config: dict[str, Any], seed: int
) -> list[CandidateResult]:
    """Treina cada candidato e o avalia na validacao, com limiar de maximo KS."""
    features = feature_columns(train, config)
    results = []
    for name in config["candidates"]:
        model = build_candidate(name, features, config, seed)
        model.fit(train[features], train[TARGET_COLUMN])
        scores = predict_scores(model, validation[features])
        y_val = validation[TARGET_COLUMN].to_numpy()
        threshold = max_ks_threshold(y_val, scores)
        metrics = classification_metrics(y_val, scores, threshold)
        results.append(CandidateResult(name, model, threshold, metrics))
    return results


def select_model(results: list[CandidateResult], config: dict[str, Any]) -> CandidateResult:
    """Aplica o criterio de promocao do ADR 04.

    Raises:
        NoEligibleModelError: Se nenhum candidato passar no piso de AUC e no Dummy.
    """
    promotion = config["promotion"]
    dummy_auc = next(r.validation["auc"] for r in results if r.name == "dummy")
    eligible = [
        r
        for r in results
        if r.name != "dummy"
        and r.validation["auc"] >= promotion["min_auc"]
        and r.validation["auc"] > dummy_auc
    ]
    if not eligible:
        raise NoEligibleModelError("Nenhum candidato atingiu o criterio de promocao")
    best = max(eligible, key=lambda r: r.validation["auc"])
    interpretable = next((r for r in eligible if r.name == config["interpretable"]), None)
    if (
        interpretable
        and best.validation["auc"] - interpretable.validation["auc"] < (promotion["tie_tolerance"])
    ):
        return interpretable
    return best


def evaluate_on_test(results: list[CandidateResult], test: pd.DataFrame, config: dict) -> None:
    """Preenche as metricas de teste de cada candidato, no limiar escolhido na validacao."""
    features = feature_columns(test, config)
    y_test = test[TARGET_COLUMN].to_numpy()
    for result in results:
        scores = predict_scores(result.model, test[features])
        result.test = classification_metrics(y_test, scores, result.threshold)


def predict_scores(model: Pipeline, features: pd.DataFrame) -> np.ndarray:
    """Probabilidade prevista de inadimplencia."""
    return model.predict_proba(features)[:, 1]
