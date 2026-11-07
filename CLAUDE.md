# CLAUDE.md

Leia este arquivo antes de qualquer ação.
Para detalhes, leia os arquivos referenciados em `docs/` e `.claude/rules/`.

<important>
- **Nenhum comando entra no README sem existir no repositório e ter rodado num clone limpo.**
  Não referencie ferramenta que não está versionada (Taskfile, Makefile, alias local).
  Foi isso que derrubou a nota do TC01 para 63.
- Todo comando documentado usa `uv run ...`. Nada de `python ...`, `make` ou `task`.
- RANDOM_SEED = 42 em todo código. Nunca use random/numpy/sklearn/xgboost sem fixar seed.
- Proibido `print()` em `src/` e `scripts/`. Use structlog (JSON). Prints só em notebooks.
- O modelo **nunca** vê dados do pool de produção no treino. Referência e produção são
  separadas uma única vez, no split inicial, e cada uma vive no seu diretório.
- Lote reprovado no contrato **não chega ao modelo**: vai para `data/quarantine/`, gera
  alerta e o processo termina com exit code ≠ 0.
- Testes estatísticos de drift são **configurados explicitamente** (PSI e KS por coluna).
  Nunca confie no stattest padrão do Evidently: ele escolhe Wasserstein/Jensen-Shannon
  para amostras > 1000, e o enunciado pede PSI/KS.
- `docs/MODEL_CARD.md` e `reports/` são entregáveis versionados. Verifique com
  `git ls-files`, não com `test -f`.
- Governança e LGPD ficam **no README.md** (exigência literal do enunciado), não só em docs/.
- ruff (check + format) e pytest devem passar antes de qualquer commit.
</important>

Regras detalhadas:

- Qualidade de código: `.claude/rules/code-quality.md`
- Entrega, reprodutibilidade e avaliação: `.claude/rules/entrega.md`

---

## Visão geral

Camada de **sustentação e confiabilidade** para um modelo de Credit Scoring em produção:
contratos de dados, simulação e detecção de Data/Concept Drift, observabilidade do
pipeline e governança LGPD. O modelo é deliberadamente simples; o foco é o que acontece
em volta dele.

- **Dataset**: Default of Credit Card Clients (UCI id 350) — 30.000 linhas, 23 features,
  target binário de inadimplência. Arquivo `data.csv` da UCI (colunas X1…X23, Y, renomeadas pelo loader)
- **Modelo**: classificador simples (LogisticRegression / XGBoost), comparado com Dummy
- **Stack**: Scikit-Learn · XGBoost · Pandera · Evidently AI · MLflow · structlog · uv · ruff · pytest

---

## Divisão dos dados (invariante do projeto)

```
dataset UCI (30.000)
 ├── referência (50%) ── treino / validação / teste do modelo
 └── pool de produção (50%) ── fonte dos lotes M01…M06 (com drift simulado)
                                + lote corrompido (demonstração do contrato)
```

- O split é estratificado pelo target e feito **uma única vez**, com seed 42
- M01 é o **lote de controle**: sem perturbação, não pode acusar drift
- Qualquer perturbação é declarada em `configs/drift_scenarios.yaml`, nunca hardcoded

---

## Estrutura de pastas

```
src/
├── config.py          # caminhos (Path(__file__)), seed, carregamento de YAML
├── data/              # loader e split referência × produção
├── contracts/         # schemas Pandera e função de validação
├── models/            # treino, avaliação e predição
├── drift/             # simulação (cenários) e detecção (Evidently)
├── monitoring/        # logging, tracking MLflow, alertas, dashboard
└── pipeline/          # orquestração das etapas
scripts/               # entrypoints de linha de comando (finos; lógica fica em src/)
configs/               # YAML com seeds, limiares e cenários
reports/               # HTML versionados (evidência para o avaliador)
docs/                  # documentação (português)
tests/                 # pytest, espelhando src/
```

---

## Comandos

> Preencher **apenas** com comandos que já existem e foram executados num clone limpo.

```bash
uv sync --group dev                                    # ambiente (versões do uv.lock)
uv run python scripts/download_data.py                 # dataset real da UCI, confere SHA256
uv run python scripts/download_data.py --synthetic     # fallback sintético (mesmo esquema)
uv run python scripts/verify_setup.py                  # diagnóstico do ambiente
uv run pytest                                          # testes (sem rede)
uv run ruff check . && uv run ruff format --check .    # lint
```

Variáveis úteis: `TC04_LOG_FORMAT=json` (logs em JSON) · `MLFLOW_DISABLE_AGENT_HINT=1`
(silencia a dica de console do MLflow) · `UV_LINK_MODE=copy` (OneDrive não suporta hardlink).

---

## Contexto detalhado

| Arquivo | Conteúdo |
|---------|----------|
| `docs/ROADMAP.md` | Etapas, critérios de aceite e conformidade com o enunciado |
| `docs/ARQUITETURA.md` | Decisões e ADRs |
| `docs/DATASET.md` | Dataset, esquema, problemas conhecidos e split |
| `docs/DATA_CONTRACTS.md` | Regras do contrato e bloqueio |
| `docs/DRIFT.md` | Cenários de simulação, testes, limiares, análise causal |
| `docs/MONITORING.md` | Métricas de saúde, alertas, playbook |
| `docs/MODEL_CARD.md` | Model Card |
| `docs/CONTRIBUTING.md` | Branches, PRs, convenções |

---

## Decisões ativas

> Atualizar sempre que uma decisão 🟡 Proposta for confirmada ou alterada.

- Dataset: UCI Default of Credit Card Clients, CC BY 4.0 — ✅ decidido (2026-11-07). Home Credit descartado pelos termos de uso (ADR 12)
- Biblioteca de contrato: Pandera — 🟡 proposta (ADR 02)
- Rastreamento da Etapa 3: MLflow local (SQLite) + dashboard HTML estático — 🟡 proposta (ADR 05)
- Limiares de drift: PSI ≥ 0,10 atenção · PSI ≥ 0,25 crítico · KS confirma — 🟡 proposta
- Gate do baseline: AUC-ROC ≥ 0,75 no teste e acima do Dummy — 🟡 revisar após EDA
- `SEX` e `MARRIAGE` fora das features; `AGE` e `EDUCATION` decididos por ablação na Etapa 1
- Versões travadas (2026-11-07): Python 3.12 · pandas 2.3.3 · numpy 2.5.4 · scikit-learn
  1.9.1 · xgboost 3.4.1 · pandera 0.35.0 · evidently 0.7.23 · mlflow 3.18.0
- **pandas fixado em `<3`**: o Evidently 0.7.23 importa `infer_dtype_from_object`, removida no
  pandas 3 — o import quebra. Revisar só quando o Evidently declarar suporte
- Pandera: usar `import pandera.pandas as pa` (o import de topo `pandera` está depreciado)
- Evidently 0.7 (API nova): `from evidently import Report, Dataset, DataDefinition` e
  `from evidently.metrics import ValueDrift, DriftedColumnsCount`. PSI e KS via
  `ValueDrift(column=..., method="psi" | "ks")`. **O KS devolve o p-valor**, não a estatística
  D — a D é calculada à parte (scipy). Exemplos da API antiga (`evidently.report`,
  `ColumnDriftMetric`) não servem
- Relatório HTML do Evidently tem ~3,7 MB — considerar no volume de `reports/` versionado
