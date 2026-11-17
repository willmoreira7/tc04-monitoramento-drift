"""Dashboard HTML estatico consolidado a partir das execucoes do MLflow.

Existe para o avaliador ver a saude do pipeline sem subir nenhum servico. Mostra a
execucao mais recente de cada lote; o historico completo fica no MLflow. So agregados:
nenhuma linha de lote entra no HTML.
"""

from datetime import UTC, datetime
from html import escape
from pathlib import Path

from src.config import REPORTS_DIR, load_config
from src.monitoring.alerts import SEVERITY_CRITICAL
from src.monitoring.stages import STAGES, STATUS_BLOCKED, STATUS_FAILED, STATUS_VALUES
from src.monitoring.tracking import SOURCE_UNKNOWN, BatchRun, load_batch_runs
from src.pipeline.io import report_name

DASHBOARD_DIR = REPORTS_DIR / "monitoring"
DASHBOARD_FILE = "dashboard.html"
MISSING = "—"

STAGE_LABELS = {
    "ingestion": "Ingestão",
    "validation": "Validação",
    "prediction": "Predição",
    "drift": "Drift",
    "performance": "Performance",
}
STATUS_LABELS = {"success": "sucesso", "failed": "falha", "blocked": "bloqueado"}
STATUS_BY_VALUE = {value: status for status, value in STATUS_VALUES.items()}

CSS = """
:root{--bg:#fff;--fg:#17202a;--muted:#5d6d7e;--line:#d5dbdf;--head:#eef3f7;
--ok:#176b36;--bad:#a93226;--warn:#8a5a00;--tile:#f7f9fa}
@media (prefers-color-scheme:dark){:root{--bg:#14181c;--fg:#e6eaee;--muted:#9aa7b3;
--line:#34404b;--head:#1e262d;--ok:#6fcf97;--bad:#f1948a;--warn:#f0c674;--tile:#1a2026}}
body{font:15px/1.45 system-ui,sans-serif;margin:0;padding:1.5rem 1rem;background:var(--bg);
color:var(--fg)}
main{max-width:1200px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 .25rem}h2{font-size:1.1rem;margin:2rem 0 .5rem}
p{color:var(--muted);margin:.25rem 0 1rem}
.tiles{display:flex;flex-wrap:wrap;gap:.75rem}
.tile{background:var(--tile);border:1px solid var(--line);border-radius:8px;
padding:.6rem 1rem;min-width:8rem}
.tile b{display:block;font-size:1.6rem}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{border:1px solid var(--line);padding:.45rem .6rem;text-align:left;white-space:nowrap}
th{background:var(--head)}td.num{text-align:right}
.success{color:var(--ok)}.blocked,.failed,.critical{color:var(--bad);font-weight:600}
.warning{color:var(--warn);font-weight:600}.none{color:var(--muted)}
"""


def build_dashboard(source: str = "real", output: Path | None = None) -> Path:
    """Gera o dashboard a partir das execucoes locais de uma origem de dados.

    Args:
        source: ``real`` ou ``synthetic``. O dashboard do sintetico ganha o sufixo
            ``.synthetic`` e nao e versionado: nunca sobrescreve a evidencia real.
        output: Destino; por padrao ``reports/monitoring/dashboard[.synthetic].html``.

    Returns:
        Caminho do HTML gerado.
    """
    runs = [run for run in load_batch_runs() if run.source in {source, SOURCE_UNKNOWN}]
    destination = output or DASHBOARD_DIR / report_name(DASHBOARD_FILE, source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_dashboard(runs, source), encoding="utf-8", newline="\n")
    return destination


def render_dashboard(runs: list[BatchRun], source: str) -> str:
    """Monta o HTML a partir das execucoes (da mais recente para a mais antiga)."""
    latest: dict[str, BatchRun] = {}
    for run in runs:
        latest.setdefault(run.batch_id, run)
    batches = [latest[batch_id] for batch_id in sorted(latest)]
    failures = sum(run.status == STATUS_FAILED for run in runs)
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Monitoramento TC04</title><style>{CSS}</style></head><body><main>"
        "<h1>Monitoramento do pipeline de credit scoring</h1>"
        f"<p>Origem dos dados: <b>{escape(source)}</b>. Execução mais recente de cada lote; "
        f"{len(runs)} execuções no histórico do MLflow, {failures} com falha inesperada.</p>"
        f"{_tiles(batches)}"
        f"<h2>Saúde por lote</h2>{_batch_table(batches)}"
        f"<h2>Drift e performance do modelo</h2>{_model_table(batches)}"
        f"<h2>Alertas</h2>{_alert_table(batches)}"
        "<p>Status de estágio: sucesso, falha (erro inesperado) ou bloqueado (contrato de "
        f"dados reprovou o lote na entrada). “{MISSING}” = estágio não executado ou métrica "
        "ainda não disponível. Métricas de performance dependem da chegada dos rótulos. "
        "Fonte: MLflow local; definições em docs/MONITORING.md.</p>"
        "</main></body></html>\n"
    )


def _tiles(batches: list[BatchRun]) -> str:
    tiles = {
        "Lotes": len(batches),
        "Bloqueados": sum(run.status == STATUS_BLOCKED for run in batches),
        "Com falha": sum(run.status == STATUS_FAILED for run in batches),
        "Alertas críticos": sum(int(run.metrics.get("alerts_critical", 0)) for run in batches),
        "Alertas de atenção": sum(int(run.metrics.get("alerts_warning", 0)) for run in batches),
    }
    cells = "".join(
        f"<div class='tile'><b>{value}</b>{label}</div>" for label, value in tiles.items()
    )
    return f"<div class='tiles'>{cells}</div>"


def _batch_table(batches: list[BatchRun]) -> str:
    header = ["Lote", "Cenário", "Executado em (UTC)", "Status"]
    header += [STAGE_LABELS[stage] for stage in STAGES]
    header += ["Linhas entrada", "Linhas saída", "Duração (s)", "Linhas/s", "Pico memória (MB)"]
    rows = []
    for run in batches:
        started = datetime.fromtimestamp(run.started_ms / 1000, UTC).strftime("%Y-%m-%d %H:%M")
        cells = [_text(run.batch_id), _text(run.scenario), _text(started), _status(run.status)]
        cells += [_stage(run, stage) for stage in STAGES]
        cells += [
            _number(run, "rows_in", 0),
            _number(run, "rows_out", 0),
            _number(run, "pipeline_duration_s", 2),
            _number(run, "throughput_rows_s", 0),
            _number(run, "peak_memory_mb", 0),
        ]
        rows.append(cells)
    return _table(header, rows)


def _model_table(batches: list[BatchRun]) -> str:
    header = [
        "Lote",
        "Features com drift",
        "Maior PSI de feature",
        "PSI do score",
        "Taxa de aprovação",
        "AUC",
        "Recall inadimplentes",
    ]
    rows = []
    population = set(load_config()["drift"]["population_columns"])
    for run in batches:
        feature_psi = {
            key.removeprefix("psi_"): value
            for key, value in run.metrics.items()
            if key.startswith("psi_") and key.removeprefix("psi_") not in population | {"score"}
        }
        worst = max(feature_psi, key=feature_psi.get, default=None)
        worst_cell = (
            f"<td>{escape(worst)} ({feature_psi[worst]:.3f})</td>" if worst else _text(MISSING)
        )
        rows.append(
            [
                _text(run.batch_id),
                _number(run, "n_features_drifted", 0),
                worst_cell,
                _number(run, "psi_score", 3),
                _number(run, "approval_rate", 3),
                _number(run, "auc_roc", 4),
                _number(run, "recall_default", 4),
            ]
        )
    return _table(header, rows)


def _alert_table(batches: list[BatchRun]) -> str:
    rows = [
        [
            _text(run.batch_id),
            f"<td class='{escape(alert['severity'])}'>"
            f"{'crítico' if alert['severity'] == SEVERITY_CRITICAL else 'atenção'}</td>",
            _text(alert["name"]),
            _text(alert["action"]),
        ]
        for run in batches
        for alert in run.alerts
    ]
    if not rows:
        return "<p>Nenhum alerta disparado.</p>"
    return _table(["Lote", "Severidade", "Alerta", "Ação do playbook"], rows)


def _stage(run: BatchRun, stage: str) -> str:
    value = run.metrics.get(f"stage_status_{stage}")
    if value is None:
        return f"<td class='none'>{MISSING}</td>"
    status = STATUS_BY_VALUE[value]
    duration = run.metrics.get(f"stage_duration_s_{stage}", 0.0)
    return f"<td class='{status}'>{STATUS_LABELS[status]} · {duration:.2f} s</td>"


def _status(status: str) -> str:
    return f"<td class='{escape(status)}'>{escape(STATUS_LABELS.get(status, status))}</td>"


def _number(run: BatchRun, metric: str, digits: int) -> str:
    value = run.metrics.get(metric)
    if value is None:
        return f"<td class='num none'>{MISSING}</td>"
    return f"<td class='num'>{value:.{digits}f}</td>"


def _text(value: str) -> str:
    return f"<td>{escape(str(value))}</td>"


def _table(header: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(title)}</th>" for title in header)
    body = "".join(f"<tr>{''.join(cells)}</tr>" for cells in rows)
    return (
        f"<div class='scroll'><table><thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )
