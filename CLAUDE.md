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
  target binário de inadimplência. 🟡 Proposta — ver `docs/DATASET.md`
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

> Preencher **apenas** com comandos que já existem e foram executados. Hoje nenhum
> comando de pipeline existe ainda.

```bash
uv sync --group dev        # ambiente (quando pyproject.toml existir)
```

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

- Dataset: UCI Default of Credit Card Clients — 🟡 proposta
- Biblioteca de contrato: Pandera — 🟡 proposta (ADR 02)
- Rastreamento da Etapa 3: MLflow local (SQLite) + dashboard HTML estático — 🟡 proposta (ADR 05)
- Limiares de drift: PSI ≥ 0,10 atenção · PSI ≥ 0,25 crítico · KS confirma — 🟡 proposta
- Gate do baseline: AUC-ROC ≥ 0,75 no teste e acima do Dummy — 🟡 revisar após EDA
- `SEX` e `MARRIAGE` fora das features; `AGE` e `EDUCATION` decididos por ablação na Etapa 1
- Versões de Pandera e Evidently: fixar no `uv.lock` e anotar aqui (APIs mudaram de forma
  incompatível entre versões recentes)
