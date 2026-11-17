"""Estagio de drift: lotes M01..M06 pelo fluxo monitorado, relatorios e resumo (Etapa 2).

Cada lote passa por ingestao (simulacao do cenario) -> validacao (contrato) -> predicao ->
drift (PSI e KS por coluna, Evidently) -> performance (rotulos revelados no proprio lote,
ressalva declarada). Cada lote vira uma execucao no MLflow, como os da demonstracao.

Evidencias (dataset real; as do sintetico ganham ``.synthetic`` e nao sao versionadas):

- ``reports/drift/drift_summary.json``: numeros de todos os lotes, deterministico e
  conferido pelo CI.
- ``reports/drift/<lote>.html``: relatorio do Evidently (~5 MB). Muda a cada execucao (ids
  e data internos), entao fica fora da conferencia byte a byte do CI e so e substituido
  quando o resumo muda: rodar de novo sem mudar numero nenhum nao toca os HTML versionados
  (cada regeneracao commitada somaria 30 MB ao historico). O HTML de cada execucao e gerado
  numa pasta temporaria e e ele que vai anexado ao MLflow.
"""

import hashlib
import io
import json
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from functools import partial
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from src.config import (
    MODELS_DIR,
    PRODUCTION_DIR,
    QUARANTINE_DIR,
    REFERENCE_DIR,
    REPORTS_DIR,
    get_seed,
    load_config,
    load_scenarios,
)
from src.data.schema import TARGET_COLUMN
from src.drift.detect import ColumnDrift, detect_drift
from src.drift.scenarios import simulate_batch
from src.models.metrics import classification_metrics
from src.models.train import predict_scores
from src.monitoring.log import PIPELINE_LOG, get_logger
from src.monitoring.model_metrics import build_model_metrics
from src.monitoring.stages import BatchRecorder
from src.pipeline.io import json_text, read_prepared, read_split_metadata, report_name, write_json
from src.pipeline.monitor import BatchOutcome, run_monitored_batch
from src.pipeline.validate import VALIDATION_REPORT_DIR, IngestedBatch

logger = get_logger(__name__)

DRIFT_REPORT_DIR = REPORTS_DIR / "drift"
SUMMARY_FILE = "drift_summary.json"
SCENARIO_TAG = "drift_simulation"
SCORE_COLUMN = "score"
PERFORMANCE_ALERTS = {"auc_drop", "recall_drop"}
CONTRACT_WARNING_PREFIX = "contract_warnings_"  # avisos por regra, de pipeline.monitor
DIGITS = 4


@dataclass
class DriftContext:
    """O que e fixo entre os lotes: modelo, referencia e linha de base.

    Attributes:
        model: Modelo promovido.
        threshold: Limiar de decisao do modelo.
        features: Features do modelo.
        population: Colunas monitoradas que nao sao features (``drift.population_columns``).
        reference: Janela de referencia, ja com a coluna de score.
        baseline: Performance do modelo na janela de referencia.
        source: ``real`` ou ``synthetic``.
        train: Treino da referencia, usado pelo aviso W3 do contrato.
        staging_dir: Pasta temporaria onde cada execucao grava o HTML do Evidently.
        model_sha256: Hash dos mesmos bytes usados para carregar o modelo.
        model_metadata: Metadados do treinamento anexados aos runs de monitoramento.
        results: Resultado de cada lote, preenchido pelos estagios.
    """

    model: Pipeline
    threshold: float
    features: list[str]
    population: list[str]
    reference: pd.DataFrame
    baseline: dict[str, float]
    source: str
    train: pd.DataFrame
    staging_dir: Path
    model_sha256: str
    model_metadata: dict[str, Any]
    results: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def monitored(self) -> list[str]:
        """Colunas comparadas: features, populacao e score."""
        return [*self.features, *self.population, SCORE_COLUMN]


def run_drift_simulation(
    reference_dir: Path = REFERENCE_DIR,
    production_dir: Path = PRODUCTION_DIR,
    model_dir: Path = MODELS_DIR / "baseline",
    report_dir: Path = DRIFT_REPORT_DIR,
    validation_report_dir: Path = VALIDATION_REPORT_DIR,
    quarantine_dir: Path = QUARANTINE_DIR,
    log_file: Path = PIPELINE_LOG,
) -> dict[str, Any]:
    """Roda os lotes de ``configs/drift_scenarios.yaml`` e grava o resumo.

    Raises:
        FileNotFoundError: Se os dados nao tiverem sido preparados ou o modelo treinado.
    """
    with tempfile.TemporaryDirectory() as staging:
        context = load_context(reference_dir, model_dir, Path(staging))
        pool = read_prepared(production_dir / "pool.parquet")
        rows = load_config()["batches"]["rows"]
        lineage = context.staging_dir / "lineage.json"
        write_json(
            lineage,
            {
                "model_sha256": context.model_sha256,
                "model_metadata": context.model_metadata,
                "split_metadata": read_split_metadata(reference_dir),
                "pipeline_config": load_config(),
                "scenarios": load_scenarios(),
            },
        )
        params = {
            "model_sha256": context.model_sha256,
            "lineage_sha256": hashlib.sha256(lineage.read_bytes()).hexdigest(),
            "threshold": context.threshold,
            "source_sha256": context.model_metadata["source_sha256"],
        }
        outcomes = {}
        for batch_id, scenario in load_scenarios().items():
            # Mesma seed em todos os lotes (numeros aleatorios comuns, ADR 14): a diferenca
            # entre lotes vem so das perturbacoes declaradas, nao do sorteio.
            ingest = partial(
                ingest_scenario_batch, batch_id, pool, scenario, rows, get_seed(), context
            )
            outcomes[batch_id] = run_monitored_batch(
                batch_id,
                SCENARIO_TAG,
                ingest,
                partial(model_stages, context=context),
                quarantine_dir,
                validation_report_dir,
                log_file,
                tracking_params=params,
                tracking_artifacts={"lineage": lineage},
            )
        summary = build_summary(context, outcomes, reference_dir)
        summary_file = report_dir / report_name(SUMMARY_FILE, context.source)
        refresh = summary_changed(summary_file, summary)
        write_json(summary_file, summary)
        publish_html_reports(context.staging_dir, report_dir, refresh)
    return summary


def summary_changed(summary_file: Path, summary: dict[str, Any]) -> bool:
    """Se o resumo novo difere do gravado (ou se ainda nao ha resumo)."""
    if not summary_file.is_file():
        return True
    return summary_file.read_text(encoding="utf-8") != json_text(summary)


def publish_html_reports(staging_dir: Path, report_dir: Path, refresh: bool) -> list[Path]:
    """Copia os HTML do Evidently para ``report_dir``.

    Com ``refresh`` falso (nenhum numero mudou), so copia os que ainda nao existem: os
    versionados ficam intactos.

    Returns:
        Arquivos copiados.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for staged in sorted(staging_dir.glob("*.html")):
        target = report_dir / staged.name
        if refresh or not target.exists():
            shutil.copyfile(staged, target)
            copied.append(target)
    logger.info("drift_html_reports", refreshed=refresh, copied=len(copied))
    return copied


def load_context(reference_dir: Path, model_dir: Path, staging_dir: Path) -> DriftContext:
    """Carrega o modelo, monta a janela de referencia e mede a linha de base.

    Raises:
        FileNotFoundError: Se o modelo nao tiver sido treinado.
        ValueError: Se modelo e referência tiverem origens diferentes.
    """
    model_file = model_dir / "model.joblib"
    if not model_file.is_file():
        raise FileNotFoundError(
            f"{model_file} nao encontrado. Rode `uv run python scripts/train_model.py`."
        )
    metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
    split = read_split_metadata(reference_dir)
    if any(metadata[key] != split[key] for key in ("source", "source_sha256")):
        raise ValueError("Modelo e referência têm origens diferentes; prepare e treine novamente.")
    model_bytes = model_file.read_bytes()
    model, features = joblib.load(io.BytesIO(model_bytes)), metadata["features"]
    threshold = metadata["threshold"]
    drift_config = load_config()["drift"]
    subsets = drift_config["reference_window"]
    window = pd.concat(
        [read_prepared(reference_dir / f"{name}.parquet") for name in subsets], ignore_index=True
    )
    window[SCORE_COLUMN] = predict_scores(model, window[features])
    return DriftContext(
        model=model,
        threshold=threshold,
        features=features,
        population=drift_config["population_columns"],
        reference=window,
        baseline=classification_metrics(
            window[TARGET_COLUMN].to_numpy(), window[SCORE_COLUMN].to_numpy(), threshold
        ),
        source=read_split_metadata(reference_dir)["source"],
        train=read_prepared(reference_dir / "train.parquet"),
        staging_dir=staging_dir,
        model_sha256=hashlib.sha256(model_bytes).hexdigest(),
        model_metadata=metadata,
    )


def ingest_scenario_batch(
    batch_id: str,
    pool: pd.DataFrame,
    scenario: dict[str, Any],
    rows: int,
    seed: int,
    context: DriftContext,
) -> IngestedBatch:
    """Estagio de ingestao: gera o lote do cenario a partir do pool de producao."""
    started = time.perf_counter()
    batch = simulate_batch(pool, scenario, rows, seed)
    logger.info(
        "stage_ingestion",
        stage="ingestion",
        status="success",
        rows_in=len(batch),
        rows_out=len(batch),
        duration_s=round(time.perf_counter() - started, 3),
        source=context.source,
    )
    return IngestedBatch(batch_id, batch, context.source, rows, context.train)


def model_stages(
    recorder: BatchRecorder, ingested: IngestedBatch, context: DriftContext
) -> tuple[dict[str, float], dict[str, Path]]:
    """Predicao, drift e performance de um lote aprovado no contrato.

    Returns:
        Metricas do lote (nomes de docs/MONITORING.md) e o relatorio HTML do Evidently.
    """
    batch = ingested.batch.copy()
    rows = len(batch)
    with recorder.stage("prediction", rows_in=rows) as stage:
        batch[SCORE_COLUMN] = predict_scores(context.model, batch[context.features])
        stage.rows_out = rows
    with recorder.stage("drift", rows_in=rows) as stage:
        drift, snapshot = detect_drift(context.reference, batch, context.monitored)
        html = context.staging_dir / report_name(f"{ingested.batch_id}.html", context.source)
        snapshot.save_html(str(html))
        stage.rows_out = rows
    with recorder.stage("performance", rows_in=rows) as stage:
        performance = classification_metrics(
            batch[TARGET_COLUMN].to_numpy(), batch[SCORE_COLUMN].to_numpy(), context.threshold
        )
        stage.rows_out = rows
    context.results[ingested.batch_id] = {
        "drift": drift,
        "performance": performance,
        "default_rate": float(batch[TARGET_COLUMN].mean()),
    }
    return _batch_metrics(drift, performance, context), {"drift_report": html}


def _batch_metrics(
    drift: dict[str, ColumnDrift], performance: dict[str, float], context: DriftContext
) -> dict[str, float]:
    """Metricas do lote: as do adaptador da Etapa 3 mais populacao, KS e aprovacao."""
    metrics = build_model_metrics(
        {name: drift[name].psi for name in context.features},
        score_psi=drift[SCORE_COLUMN].psi,
        feature_ks_d={name: drift[name].ks_d for name in context.features},
        baseline_auc=context.baseline["auc"],
        batch_auc=performance["auc"],
        baseline_recall=context.baseline["recall_default"],
        batch_recall=performance["recall_default"],
    )
    for name in context.population:
        metrics[f"psi_{name}"] = drift[name].psi
        metrics[f"ks_d_{name}"] = drift[name].ks_d
    metrics["ks_score"] = performance["ks"]
    metrics["approval_rate"] = performance["approval_rate"]
    return metrics


def build_summary(
    context: DriftContext, outcomes: dict[str, BatchOutcome], reference_dir: Path
) -> dict[str, Any]:
    """Resumo deterministico de todos os lotes (conferido byte a byte pelo CI)."""
    thresholds = load_config()["monitoring"]["thresholds"]
    split = read_split_metadata(reference_dir)
    scenarios = load_scenarios()
    return {
        "source": context.source,
        "source_sha256": split["source_sha256"],
        "seed": get_seed(),
        "library_versions": {lib: version(lib) for lib in ("evidently", "scikit-learn", "xgboost")},
        "reference": {
            "window": load_config()["drift"]["reference_window"],
            "rows": len(context.reference),
            "baseline": _rounded(context.baseline),
        },
        "monitored": {"features": context.features, "population": context.population},
        "thresholds": thresholds,
        "batches": {
            batch_id: _batch_summary(
                scenarios[batch_id], outcome, context.results.get(batch_id), context, thresholds
            )
            for batch_id, outcome in outcomes.items()
        },
    }


def _batch_summary(
    scenario: dict[str, Any],
    outcome: BatchOutcome,
    result: dict[str, Any] | None,
    context: DriftContext,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    mechanisms = ("resample", "relabel", "scale")
    perturbations = {key: scenario[key] for key in mechanisms if key in scenario}
    summary: dict[str, Any] = {
        "narrative": scenario["narrative"],
        "perturbations": perturbations,
        "status": outcome.status,
        "contract_warnings": {
            key.removeprefix(CONTRACT_WARNING_PREFIX): int(value)
            for key, value in sorted(outcome.metrics.items())
            if key.startswith(CONTRACT_WARNING_PREFIX)
        },
        "alerts": outcome.alerts,
    }
    if result is None:  # bloqueado ou com falha: nao chegou ao modelo
        return summary
    drift: dict[str, ColumnDrift] = result["drift"]
    drifted = [
        name
        for name in [*context.features, *context.population]
        if drift[name].psi >= thresholds["psi_warning"]
    ]
    performance_alert = any(alert["name"] in PERFORMANCE_ALERTS for alert in outcome.alerts)
    expected = scenario["expected"]
    return {
        **summary,
        "default_rate": round(result["default_rate"], DIGITS),
        "columns": {name: _column(drift[name], thresholds) for name in context.monitored},
        "drifted": drifted,
        "share_features_drifted": round(outcome.metrics["share_features_drifted"], DIGITS),
        "performance": _performance(result["performance"], context.baseline),
        "performance_alert": performance_alert,
        "expected": expected,
        "expectation_met": sorted(drifted) == sorted(expected["drifted"])
        and performance_alert == expected["performance_alert"],
    }


def _column(drift: ColumnDrift, thresholds: dict[str, float]) -> dict[str, Any]:
    level = "stable"
    if drift.psi >= thresholds["psi_critical"]:
        level = "critical"
    elif drift.psi >= thresholds["psi_warning"]:
        level = "warning"
    return {
        "psi": round(drift.psi, DIGITS),
        "ks_d": round(drift.ks_d, DIGITS),
        "ks_pvalue": round(drift.ks_pvalue, DIGITS),
        "level": level,
    }


def _performance(performance: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    """Performance do lote e a variacao contra a referencia (negativa = piorou)."""
    return {
        **_rounded(performance),
        "auc_change": round(performance["auc"] - baseline["auc"], DIGITS),
        "recall_change": round(performance["recall_default"] - baseline["recall_default"], DIGITS),
    }


def _rounded(values: dict[str, float]) -> dict[str, float]:
    return {key: round(float(value), DIGITS) for key, value in values.items()}
