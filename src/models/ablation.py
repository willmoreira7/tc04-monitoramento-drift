"""Ablacao dos atributos pessoais candidatos (ADR 13).

Para cada variante (todos os candidatos, sem cada um, sem todos) repete a comparacao do
ADR 04 no mesmo split e registra o modelo promovido, a AUC de validacao e o vies medido na
validacao. A decisao segue o criterio declarado em ``configs/pipeline.yaml`` (secao
``ablation``) antes da execucao.
"""

from itertools import combinations
from typing import Any

import pandas as pd

from src.models.fairness import audit
from src.models.train import feature_columns, predict_scores, select_model, train_candidates

FULL_VARIANT = "all"


def variant_name(dropped: tuple[str, ...]) -> str:
    """Nome da variante: ``all`` ou ``without_<A>_<B>``."""
    return FULL_VARIANT if not dropped else "without_" + "_".join(dropped)


def run_ablation(
    train: pd.DataFrame, validation: pd.DataFrame, config: dict[str, Any], seed: int
) -> dict[str, Any]:
    """Executa todas as variantes e aplica o criterio de decisao.

    Args:
        train: Treino da referencia.
        validation: Validacao da referencia (onde a decisao e tomada).
        config: Configuracao completa (secoes ``model``, ``ablation`` e ``fairness``).
        seed: Seed global.

    Returns:
        Resultado de cada variante e os atributos a remover.
    """
    candidates = config["ablation"]["candidates"]
    variants = {}
    for size in range(len(candidates) + 1):
        for dropped in combinations(candidates, size):
            variants[variant_name(dropped)] = _evaluate(train, validation, config, dropped, seed)
    full_auc = variants[FULL_VARIANT]["validation_auc"]
    for result in variants.values():
        result["auc_loss"] = round(full_auc - result["validation_auc"], 4)
    return {
        "criterion": config["ablation"],
        "variants": variants,
        "remove": decide(variants, candidates, config["ablation"]["max_auc_loss"]),
    }


def decide(variants: dict[str, Any], candidates: list[str], max_loss: float) -> list[str]:
    """Criterio do ADR 13.

    Remove o conjunto inteiro se a variante sem todos perder menos que ``max_loss``; senao,
    remove cada candidato cuja retirada isolada perca menos que ``max_loss``.
    """
    if variants[variant_name(tuple(candidates))]["auc_loss"] < max_loss:
        return list(candidates)
    return [c for c in candidates if variants[variant_name((c,))]["auc_loss"] < max_loss]


def _evaluate(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    config: dict[str, Any],
    dropped: tuple[str, ...],
    seed: int,
) -> dict[str, Any]:
    model_config = _variant_config(config["model"], config["ablation"]["candidates"], dropped)
    results = train_candidates(train, validation, model_config, seed)
    promoted = select_model(results, model_config)
    features = feature_columns(validation, model_config)
    scores = predict_scores(promoted.model, validation[features])
    bias = audit(validation, scores, promoted.threshold, config["fairness"])
    return {
        "dropped": list(dropped),
        "promoted": promoted.name,
        "validation_auc": round(promoted.validation["auc"], 4),
        "validation_ks": round(promoted.validation["ks"], 4),
        "candidates_auc": {r.name: round(r.validation["auc"], 4) for r in results},
        "min_good_payer_ratio": {a: s["min_good_payer_ratio"] for a, s in bias.items()},
        "min_impact_ratio": {a: s["min_impact_ratio"] for a, s in bias.items()},
    }


def _variant_config(
    model_config: dict[str, Any], candidates: list[str], dropped: tuple[str, ...]
) -> dict[str, Any]:
    """Config do modelo com todos os candidatos como feature, menos os retirados."""
    base = [c for c in model_config["excluded_columns"] if c not in candidates]
    return {**model_config, "excluded_columns": [*base, *dropped]}
