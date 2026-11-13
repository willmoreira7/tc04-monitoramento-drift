# 📈 Observabilidade e Monitoramento

> Métricas de saúde do pipeline, da infraestrutura e do modelo; regras de alerta e
> playbook de resposta. Implementação na Etapa 3, em `src/monitoring/`.

> ✅ **Status: implementada para tracking batch e demonstração do contrato.** A integração de métricas detalhadas de drift será conectada quando a Etapa 2 estiver implementada.

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
- O tracking e o dashboard foram implementados em `src/monitoring/tracking.py`; o evento de validação também é anexado a `logs/pipeline.jsonl`.
- `scripts/run_monitoring_demo.py` demonstra uma run por lote para o fluxo de contrato: sucesso, bloqueio esperado ou falha. A etapa 2 ainda não existe, portanto os sinais PSI/KS/performance ainda não estão ligados a execuções reais.
- ⚪ Opcional: expor as mesmas métricas com `prometheus-client` e reaproveitar o Grafana da Fase 3. Não é necessário para o fluxo batch atual.

---

## Execução local

Após preparar os dados, os comandos abaixo executam a demonstração instrumentada. O lote válido deve retornar `0`; o corrompido retorna `2` por bloqueio esperado do contrato. O dashboard pode ser gerado a qualquer momento a partir das runs locais.

```bash
uv run python scripts/run_monitoring_demo.py --demo valid --scenario contract_demo
uv run python scripts/run_monitoring_demo.py --demo corrupted --scenario contract_demo  # esperado: exit 2
uv run python scripts/build_monitoring_dashboard.py
```

`MLFLOW_TRACKING_URI` pode apontar para um tracking server alternativo. O padrão local é `logs/mlflow.db`; banco e JSONL são locais e ignorados pelo Git. Não versionar o tracking store.

## 📏 Métricas de saúde

### Pipeline de dados

| Métrica | Tipo | Significado |
|---------|------|-------------|
| `stage_status{stage}` | 1 sucesso · 0 falha · −1 bloqueado | Estado de cada tarefa |
| `stage_duration_s{stage}` | segundos | Latência de cada estágio |
| `rows_in`, `rows_out` | contagem | Volume processado; diferença = linhas perdidas |
| `contract_violations{rule}` | contagem | Violações por regra do contrato |
| `contract_warnings{rule}` | contagem | Avisos não bloqueantes |
| `batch_blocked` | 0/1 | Lote enviado para quarentena |

### Infraestrutura

| Métrica | Tipo | Significado |
|---------|------|-------------|
| `pipeline_duration_s` | segundos | Tempo total do lote |
| `peak_memory_mb` | MB | Pico de memória do processo |
| `throughput_rows_s` | linhas/s | Vazão da predição |
| `pipeline_failures_total` | contagem | Execuções que terminaram com erro inesperado |

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
| Lote bloqueado | Violação crítica no contrato | 🔴 Crítico | Investigar a origem; reprocessar após correção. Nunca liberar manualmente |
| Falha de estágio | Exceção inesperada | 🔴 Crítico | Ver log JSON do estágio; reexecutar |
| Drift de feature | PSI ≥ 0,25 | 🔴 Crítico | Abrir análise causal; avaliar impacto antes de retreinar |
| Drift de feature | 0,10 ≤ PSI < 0,25 | 🟡 Atenção | Acompanhar a tendência nos próximos lotes |
| Drift de predição | PSI do score ≥ 0,10 | 🟡 Atenção | Checar taxa de aprovação; avisar o negócio |
| Degradação | Queda de AUC ≥ 0,05 | 🔴 Crítico | Retreino candidato, com o mesmo gate do baseline |
| Volume anômalo | Fora de ±30% | 🟡 Atenção | Checar a extração |

> ⚠️ **Retreinar não é a resposta padrão a drift.** Se o drift é nominal (inflação), a
> correção certa pode ser deflacionar as features, não retreinar. Se é concept drift,
> retreinar com dados antigos não resolve. A análise causal decide — ver
> [DRIFT.md](DRIFT.md#-análise-causal).

---

## 📂 Evidências

| Artefato | Onde |
|----------|------|
| Logs estruturados | `logs/pipeline.jsonl` (não versionado; evento de validação; anexado ao MLflow na demonstração) |
| Execuções | MLflow local (`logs/mlflow.db`, não versionado; URI substituível por `MLFLOW_TRACKING_URI`) |
| Dashboard consolidado | `reports/monitoring/dashboard.html` (versionado) |
| Runs de exemplo | geradas localmente pela demonstração; banco não versionado |

---

**Última atualização:** 2026-11-13
