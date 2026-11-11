"""Auditoria de vies: resultado do modelo por grupo de um atributo sensivel.

Nao treina nada: recebe os scores e o limiar. Duas razoes de impacto por grupo, porque
os grupos tem inadimplencia real diferente:

- ``impact_ratio``: taxa de aprovacao do grupo / maior taxa de aprovacao entre os grupos
  (regra dos 4/5). Mistura risco real e tratamento diferente.
- ``good_payer_ratio``: o mesmo, mas so entre quem **nao** ficou inadimplente. Mede se um
  bom pagador tem a mesma chance de aprovacao em qualquer grupo (igualdade de
  oportunidade) e e a leitura principal.
"""

from typing import Any

import numpy as np
import pandas as pd

from src.data.schema import CATEGORY_LABELS, TARGET_COLUMN

AGE_COLUMN = "AGE"
UNKNOWN_GROUP = "desconhecido"


def audit(
    frame: pd.DataFrame, scores: np.ndarray, threshold: float, config: dict[str, Any]
) -> dict[str, Any]:
    """Audita o resultado por grupo de cada atributo configurado.

    Args:
        frame: Conjunto avaliado, com os atributos sensiveis e o rotulo.
        scores: Probabilidade prevista de inadimplencia para cada linha.
        threshold: Score a partir do qual o cliente e classificado como risco (recusado).
        config: Secao ``fairness`` da configuracao.

    Returns:
        Por atributo: metricas por grupo, menores razoes entre grupos conclusivos e se
        alguma ficou abaixo da regra dos 4/5.
    """
    approved = scores < threshold
    return {
        attribute: _attribute_summary(group_metrics(frame, approved, attribute, config), config)
        for attribute in config["attributes"]
    }


def group_metrics(
    frame: pd.DataFrame, approved: np.ndarray, attribute: str, config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Metricas de cada grupo de um atributo.

    Returns:
        Uma linha por grupo: tamanho, inadimplencia real, aprovacao geral, aprovacao de
        bons pagadores, recall de inadimplentes e as duas razoes de impacto.
    """
    groups = group_labels(frame, attribute, config)
    defaulted = frame[TARGET_COLUMN].to_numpy() == 1
    rows = [
        _group_row(str(label), (groups == label).to_numpy(), approved, defaulted, config)
        for label in groups.cat.categories
        if (groups == label).any()
    ]
    # A referencia da razao vem so de grupos conclusivos: um grupo minusculo com 100% de
    # aprovacao por acaso distorceria a razao de todos os outros.
    reference = [row for row in rows if row["conclusive"]] or rows
    best_approval = max(row["approval_rate"] for row in reference)
    best_good = max(row["good_payer_approval"] for row in reference)
    for row in rows:
        row["impact_ratio"] = round(row["approval_rate"] / best_approval, 4)
        row["good_payer_ratio"] = round(row["good_payer_approval"] / best_good, 4)
    return rows


def group_labels(frame: pd.DataFrame, attribute: str, config: dict[str, Any]) -> pd.Series:
    """Grupo de cada linha (faixa etaria ou categoria do dicionario), como categoria ordenada."""
    if attribute == AGE_COLUMN:
        bins = config["age_bins"]
        labels = [f"{low}-{high - 1}" for low, high in zip(bins[:-2], bins[1:-1], strict=True)]
        labels.append(f"{bins[-2]}+")
        return pd.cut(frame[attribute], bins=bins, labels=labels, right=False)
    names = CATEGORY_LABELS[attribute]
    mapped = frame[attribute].map(names).fillna(UNKNOWN_GROUP)
    return pd.Series(pd.Categorical(mapped, categories=[*names.values(), UNKNOWN_GROUP]))


def _group_row(
    label: str,
    mask: np.ndarray,
    approved: np.ndarray,
    defaulted: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    good = mask & ~defaulted
    bad = mask & defaulted
    return {
        "group": label,
        "n": int(mask.sum()),
        "conclusive": bool(mask.sum() >= config["min_group_size"]),
        "default_rate": _rate(defaulted, mask),
        "approval_rate": _rate(approved, mask),
        "good_payer_approval": _rate(approved, good),
        "recall_default": _rate(~approved, bad),
    }


def _rate(event: np.ndarray, population: np.ndarray) -> float:
    total = population.sum()
    return round(float((event & population).sum() / total), 4) if total else 0.0


def _attribute_summary(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    conclusive = [row for row in rows if row["conclusive"]] or rows
    min_impact = min(row["impact_ratio"] for row in conclusive)
    min_good = min(row["good_payer_ratio"] for row in conclusive)
    floor = config["impact_ratio_min"]
    return {
        "groups": rows,
        "min_impact_ratio": min_impact,
        "min_good_payer_ratio": min_good,
        "below_four_fifths": min_impact < floor or min_good < floor,
    }
