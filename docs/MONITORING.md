# 📈 Observabilidade e Monitoramento

> Métricas de saúde do pipeline, da infraestrutura e do modelo; regras de alerta e
> playbook de resposta. Implementação na Etapa 3, em `src/monitoring/`.

> 🟡 **Status: implementada para ingestão e validação.** Predição, drift e performance entram
> no mesmo fluxo quando a Etapa 2 existir; as regras de alerta deles já estão implementadas e testadas.

---

## 🎯 O que o enunciado pede

1. **Centralizar logs e métricas** — execução do pipeline (sucesso/falha na ingestão e
   transformação) e resultados dos testes de drift
2. **Rastreamento/monitoramento** — MLflow, Datadog, cloud nativo ou open source
3. **Definir e documentar métricas** — status das tarefas, latência, volume, alertas

---

## 🧱 Como os sinais fluem

```
 cada estágio do pipeline (ingest · validate · predict · drift · performance)
          │
          ├── structlog (JSON) ──────────► logs/pipeline.jsonl
          │                                       │
          └── métricas do estágio ─┐              │ anexado como artefato
                                   ▼              ▼
                         ┌──────────────────────────────────┐
                         │ MLflow — 1 execução por lote     │
                         │ params · métricas · HTML · logs  │
                         └───────────────┬──────────────────┘
                                         ▼
                      reports/monitoring/dashboard.html (versionado)
```

- **Uma execução MLflow por lote**, com tags `batch_id` e `scenario`. A interface do MLflow
  plota qualquer métrica ao longo dos lotes — é a série temporal da degradação.
- **Dashboard HTML estático** consolidado a partir das execuções. Existe para o avaliador
  ver o resultado **sem subir nenhum serviço**.
- ⚪ Opcional: as mesmas métricas enviadas a um Pushgateway e exibidas no Grafana da
  Fase 3 — ver [Grafana e Prometheus](#-grafana-e-prometheus-opcional).

### Onde cada parte mora

| Peça | Arquivo | O que faz |
|------|---------|-----------|
| Log centralizado | `src/monitoring/log.py` | Todo evento do structlog vira uma linha JSON em `logs/pipeline.jsonl`, qualquer que seja o formato do terminal |
| Estágios | `src/monitoring/stages.py` | `BatchRecorder` mede status, latência e volume de cada estágio e o pico de memória |
| Alertas | `src/monitoring/alerts.py` | `evaluate_alerts`: função pura, limiares em `configs/pipeline.yaml` |
| Rastreamento | `src/monitoring/tracking.py` | Uma execução MLflow por lote, com métricas, alertas, relatório e os eventos de log do lote |
| Dashboard | `src/monitoring/dashboard.py` | HTML estático com a execução mais recente de cada lote |
| Prometheus (opcional) | `src/monitoring/prometheus.py` | Envia as métricas do lote ao Pushgateway quando `TC04_PUSHGATEWAY_URL` está definida |
| Orquestração | `src/pipeline/monitor.py` | Liga os estágios às peças acima; lote bloqueado ou com falha também é registrado |

Um novo estágio (predição, drift, performance) entra como um bloco
`with recorder.stage("prediction"): ...` em `src/pipeline/monitor.py`; métricas, alertas,
MLflow e dashboard já o reconhecem.

---

## ▶️ Execução local

Pré-requisito: `uv run python scripts/prepare_data.py`.

```bash
uv run python scripts/run_monitoring_demo.py --demo valid       # exit 0
uv run python scripts/run_monitoring_demo.py --demo corrupted   # exit 2: bloqueado pelo contrato
uv run python scripts/build_monitoring_dashboard.py             # regenera o dashboard
uv run mlflow ui                                                # http://127.0.0.1:5000
```

- Exit codes: `0` aprovado · `1` falha inesperada (ex.: dados não preparados) · `2` bloqueado.
  Os três casos ficam registrados no MLflow.
- O banco é `mlflow.db` na raiz do projeto — o que `uv run mlflow ui` abre por padrão — e
  os artefatos ficam em `mlartifacts/`. `MLFLOW_TRACKING_URI` aponta para outro servidor.
- Execuções sobre o dataset sintético geram `dashboard.synthetic.html` (não versionado) e
  nunca aparecem no dashboard real.
- O lote corrompido passa pela ingestão e é **bloqueado na validação**: nenhuma linha
  segue adiante (`rows_out = 0`) e o alerta crítico `batch_blocked` é disparado.

---

## 📡 Grafana e Prometheus (opcional)

O ambiente da Fase 3 (Prometheus + Grafana no EKS do laboratório) é reaproveitado como
vitrine ao vivo. **Não substitui** o MLflow nem o dashboard HTML: quem não tem acesso ao
cluster continua vendo tudo pelo repositório.

```
 lote (batch) ──push──► Pushgateway ◄──scrape── Prometheus ──► Grafana
```

O pipeline é batch e termina antes de qualquer scrape; por isso ele **empurra** as
métricas para um Pushgateway, que o Prometheus coleta. Cada lote é um grupo
(`batch_id` + `source`) e um novo envio substitui o grupo: o Grafana mostra sempre a
execução mais recente de cada lote.

| Série | Labels | Origem (métrica do lote) |
|-------|--------|--------------------------|
| `tc04_batch_status` | — | status do lote (1 · 0 · −1) |
| `tc04_stage_status`, `tc04_stage_duration_seconds` | `stage` | `stage_status_<stage>`, `stage_duration_s_<stage>` |
| `tc04_contract_violations`, `tc04_contract_warnings` | `rule` | `contract_violations_<regra>`, `contract_warnings_<regra>` |
| `tc04_feature_psi`, `tc04_feature_ks_d` | `feature` | `psi_<feature>`, `ks_d_<feature>` |
| `tc04_batch_alert` | `alert`, `severity`, `action` | alertas disparados |
| `tc04_batch_<métrica>` | — | demais métricas (`rows_in`, `psi_score`, `auc_roc`, …) |

Todas levam também `batch_id` e `source`. A cardinalidade é limitada por construção:
lotes, estágios, regras do contrato e features.

**Como usar**

```bash
TC04_PUSHGATEWAY_URL=https://pushgateway.pocsarcotech.com uv run python scripts/run_monitoring_demo.py --demo valid
TC04_PUSHGATEWAY_URL=https://pushgateway.pocsarcotech.com uv run python scripts/run_monitoring_demo.py --demo corrupted  # exit 2
```

| Serviço | URL |
|---------|-----|
| Pushgateway | <https://pushgateway.pocsarcotech.com> |
| Prometheus | <https://prometheus.pocsarcotech.com> |
| Grafana | <https://grafana.pocsarcotech.com/d/tc04-batch-monitoring> |

> ⚠️ **O Pushgateway está aberto, sem autenticação** (ambiente de laboratório acadêmico,
> como o Prometheus da Fase 3): qualquer pessoa com a URL pode enviar ou apagar métricas.
> Nenhum dado de lote trafega por ele, só agregados. Para fechar, basta desligar o
> Ingress (`prometheus-pushgateway.ingress.enabled=false`) e usar
> `kubectl -n monitoring port-forward svc/prometheus-prometheus-pushgateway 9091:9091`
> com `TC04_PUSHGATEWAY_URL=http://localhost:9091`.

O Pushgateway é um subchart do Prometheus da Fase 3 (chart `prometheus-community/prometheus`
29.30.0, release `prometheus`, namespace `monitoring`), ligado com estes values:

```yaml
prometheus-pushgateway:
  enabled: true
  ingress:
    enabled: true
    className: alb
    path: /
    pathType: Prefix
    hosts:
      - pushgateway.pocsarcotech.com
    annotations:
      alb.ingress.kubernetes.io/group.name: mlops-tools
      alb.ingress.kubernetes.io/scheme: internet-facing
      alb.ingress.kubernetes.io/target-type: ip
      alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80},{"HTTPS":443}]'
      alb.ingress.kubernetes.io/ssl-redirect: "443"
      alb.ingress.kubernetes.io/healthcheck-path: /-/healthy
```

O registro `pushgateway.pocsarcotech.com` no Route53 é um alias A para o ALB compartilhado,
criado à mão (o cluster não tem external-dns).

O dashboard do Grafana é versionado em
[`monitoring/grafana/tc04-batch-monitoring.json`](../monitoring/grafana/tc04-batch-monitoring.json)
(Dashboards → New → Import). Pushgateway fora do ar gera só um aviso no log
(`pushgateway_unreachable`): o lote, o MLflow e o dashboard HTML não são afetados.

> ℹ️ O eixo do tempo do Grafana é o relógio real, e os lotes M01…M06 simulam meses em
> segundos. Por isso os painéis comparam **lotes lado a lado** (valor mais recente de cada
> um), não uma série temporal.

---

## 📏 Métricas de saúde

### Pipeline de dados

| Métrica | Tipo | Significado |
|---------|------|-------------|
| `stage_status_<stage>` | 1 sucesso · 0 falha · −1 bloqueado | Estado de cada tarefa |
| `stage_duration_s_<stage>` | segundos | Latência de cada estágio |
| `rows_in`, `rows_out`, `rows_expected` | contagem | Volume recebido, entregue e esperado; `rows_out = 0` em lote bloqueado |
| `contract_violations`, `contract_violations_<regra>` | contagem | Ocorrências de violação, no total e por regra (C1…C8) |
| `contract_warnings`, `contract_warnings_<regra>` | contagem | Avisos não bloqueantes, no total e por regra (W1…W4) |
| `batch_blocked`, `batch_failed` | 0/1 | Lote enviado para quarentena · lote com erro inesperado |

### Infraestrutura

| Métrica | Tipo | Significado |
|---------|------|-------------|
| `pipeline_duration_s` | segundos | Tempo total do lote |
| `peak_memory_mb` | MB | Pico de memória do processo |
| `throughput_rows_s` | linhas/s | Vazão do pipeline: linhas recebidas ÷ tempo total do lote |
| Falhas no histórico | contagem | Execuções com `batch_failed = 1`, somadas no cabeçalho do dashboard |

### Modelo

| Métrica | Tipo | Disponível quando |
|---------|------|-------------------|
| `n_features_drifted` / `share_features_drifted` | contagem / fração | Imediatamente |
| `psi_<feature>`, `ks_d_<feature>` | float | Imediatamente |
| `psi_score` | float | Imediatamente (drift de predição) |
| `approval_rate` | fração | Imediatamente |
| `auc_roc`, `recall_default`, `ks_score` | float | **Só quando os rótulos chegam** |
| `alerts_warning`, `alerts_critical` | contagem | Imediatamente |

> ℹ️ Em crédito, o rótulo (inadimplência) chega meses depois da decisão. As métricas de
> drift são o **alarme antecipado**; as de performance são a **confirmação**. Na
> simulação, os rótulos de cada lote são revelados no próprio lote para encurtar o ciclo
> — ressalva declarada no vídeo.

---

## 🚨 Alertas

| Alerta | Condição | Severidade | Ação (playbook) |
|--------|----------|-----------|-----------------|
| Lote bloqueado (`batch_blocked`) | Violação crítica no contrato | 🔴 Crítico | Investigar a origem; reprocessar após correção. Nunca liberar manualmente |
| Falha de estágio (`stage_failure`) | Exceção inesperada | 🔴 Crítico | Ver log JSON do estágio; reexecutar |
| Drift de feature | PSI ≥ 0,25 | 🔴 Crítico | Abrir análise causal; avaliar impacto antes de retreinar |
| Drift de feature | 0,10 ≤ PSI < 0,25 | 🟡 Atenção | Acompanhar a tendência nos próximos lotes |
| Drift de predição | PSI do score ≥ 0,10 | 🟡 Atenção | Checar taxa de aprovação; avisar o negócio |
| Degradação | Queda de AUC ≥ 0,05 | 🔴 Crítico | Retreino candidato, com o mesmo gate do baseline |
| Volume anômalo (`volume_anomaly`) | `rows_in` fora de ±30% de `rows_expected` | 🟡 Atenção | Checar a extração |

> ⚠️ **Retreinar não é a resposta padrão a drift.** Se o drift é nominal (inflação), a
> correção certa pode ser deflacionar as features, não retreinar. Se é concept drift,
> retreinar com dados antigos não resolve. A análise causal decide — ver
> [DRIFT.md](DRIFT.md#-análise-causal).

---

## 📂 Evidências

| Artefato | Onde |
|----------|------|
| Logs estruturados | `logs/pipeline.jsonl` (não versionado); os eventos de cada lote são anexados à execução em `logs/pipeline.jsonl` |
| Execuções | MLflow local (`mlflow.db` + `mlartifacts/`, não versionados) |
| Dashboard consolidado | `reports/monitoring/dashboard.html` (versionado; só dataset real) |
| Prints do MLflow | `docs/assets/` (versionado) — ⬜ pendente, tirar com os lotes M01…M06 |

---

**Última atualização:** 2026-11-16
