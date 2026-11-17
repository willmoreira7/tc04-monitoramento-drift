"""Testes da ablação causal e do contrato de intervenções declaradas em YAML."""

import json
from pathlib import Path

from src.config import load_causal_interventions
from src.data import loader
from src.data.synthetic import generate_synthetic
from src.pipeline import causal, prepare
from src.pipeline import train as train_stage


def test_causal_interventions_isolate_one_mechanism_each() -> None:
    """Cada intervenção deve alterar um único mecanismo declarado."""
    interventions = load_causal_interventions()
    assert set(interventions) == {
        "inflation_only",
        "younger_profiles_only",
        "delayed_profiles_only",
        "lower_limits_only",
        "concept_drift_only",
    }
    expected = {
        "inflation_only": {"scale"},
        "younger_profiles_only": {"resample"},
        "delayed_profiles_only": {"resample"},
        "lower_limits_only": {"scale"},
        "concept_drift_only": {"relabel"},
    }
    for name, scenario in interventions.items():
        assert {key for key in ("resample", "relabel", "scale") if key in scenario} == expected[
            name
        ]


def test_causal_ablation_pipeline_writes_aggregated_report(tmp_path: Path, monkeypatch) -> None:
    """O relatório causal é reproduzível, agregado e tem os contrastes esperados."""
    raw_file = tmp_path / "synthetic.csv"
    generate_synthetic(12_000, seed=42).to_csv(raw_file, index=False)
    monkeypatch.setattr(loader, "synthetic_dataset_path", lambda: raw_file)
    reference, production, model = (
        tmp_path / name for name in ("reference", "production", "model")
    )
    prepare.prepare_data(
        prepare.DataSource.SYNTHETIC, reference, production, tmp_path / "validation"
    )
    train_stage.train_model(reference, model, tmp_path / "model-report")

    destination = tmp_path / "drift"
    result = causal.run_causal_ablation(reference, production, model, destination)

    assert set(result["interventions"]) == set(load_causal_interventions())
    assert set(result["combined_contrasts"]) == {"M04", "M06"}
    assert "delta_vs_m01" in result["interventions"]["concept_drift_only"]
    assert result["source"] == "synthetic"
    report = json.loads((destination / "causal_ablation.synthetic.json").read_text("utf-8"))
    assert report == result
    assert not (destination / "causal_ablation.json").exists()
