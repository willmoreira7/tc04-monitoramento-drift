# 💳 tc04-monitoramento-drift — Sustentação e Confiabilidade de um Modelo de Credit Scoring

[![CI](https://github.com/willmoreira7/tc04-monitoramento-drift/actions/workflows/ci.yml/badge.svg)](https://github.com/willmoreira7/tc04-monitoramento-drift/actions/workflows/ci.yml)

> Contratos de dados, detecção de Data/Concept Drift, observabilidade do pipeline e
> governança LGPD para um modelo de crédito em produção.

---

## 🎯 Contexto e Problema

Uma fintech de concessão de crédito tem um modelo de **Credit Scoring** em produção. Com
mudanças recentes na economia (inflação, novos perfis de clientes), a diretoria suspeita
que o modelo está tomando decisões erradas e sofrendo **degradação silenciosa**: as
predições continuam saindo, a API continua respondendo, e ninguém percebe que a qualidade
caiu até a inadimplência aparecer no balanço, meses depois.

| Sintoma em produção | Por que é silencioso | O que este projeto faz |
|---------------------|---------------------|------------------------|
| Lote com dados inválidos (nulos, idade < 18, duplicatas) | O modelo pontua lixo sem reclamar | **Contrato de dados** bloqueia o lote antes da inferência |
| Perfil dos clientes muda (Data Drift) | Nenhum erro técnico é disparado | **Testes estatísticos** (PSI, KS) comparam produção × referência |
| A relação perfil → inadimplência muda (Concept Drift) | As features parecem normais | **Monitoramento de performance** quando os rótulos chegam |
| Ninguém sabe o estado do pipeline | Falhas e alertas ficam espalhados | **Logs e métricas centralizados** + dashboard |

> 🔴 **O drift deste projeto é simulado.** O dataset é público e estático; a passagem do
> tempo, a inflação e os novos perfis são introduzidos de forma controlada sobre um
> conjunto separado de produção. Isso é o que permite **saber a causa verdadeira** de cada
> degradação e verificar se os detectores apontam para ela — ver
> [Análise Causal](#-análise-causal-da-degradação).

---

## 🧩 Escopo do Projeto

O foco **não é maximizar o AUC do modelo**. O modelo é deliberadamente simples; o
entregável é a camada de **sustentação** em torno dele:

- **Etapa 1 — Validação de dados:** contrato com Pandera que intercepta e bloqueia lotes inválidos
- **Etapa 2 — Drift:** lotes mensais simulados + Evidently AI com PSI e Kolmogorov-Smirnov
- **Etapa 3 — Observabilidade:** logs centralizados, métricas por estágio, alertas, uma execução MLflow por lote e dashboard HTML, com predição, drift e performance de cada lote
- **Etapa 4 — Governança:** plano LGPD, mitigação de vieses e análise causal (neste README)

> O andamento de cada item está em [docs/ROADMAP.md](docs/ROADMAP.md).

---

## 🏗️ Arquitetura

```
                 ┌──────────────────────────────────────────────┐
  UCI dataset ─► │ split 50/50 (estratificado, seed 42)         │
                 └───────────┬──────────────────────┬───────────┘
                             ▼                      ▼
                 ┌──────────────────────┐  ┌──────────────────────────┐
                 │ REFERÊNCIA           │  │ POOL DE PRODUÇÃO         │
                 │ treino / val / teste │  │ nunca visto pelo modelo  │
                 └──────────┬───────────┘  └────────────┬─────────────┘
                            ▼                           ▼
                 ┌──────────────────────┐  ┌──────────────────────────┐
                 │ contrato (Pandera)   │  │ simulador de drift       │
                 │ → treino baseline    │  │ → lotes M01 … M06        │
                 └──────────┬───────────┘  └────────────┬─────────────┘
                            │                           ▼
                            │              ┌──────────────────────────┐
                            │              │ contrato (Pandera)       │──✖──► quarentena + alerta
                            │              └────────────┬─────────────┘
                            │                           ▼ aprovado
                            └────────────► ┌──────────────────────────┐
                                 modelo    │ predição do lote         │
                                           └────────────┬─────────────┘
                                                        ▼
                                           ┌──────────────────────────┐
                                           │ Evidently: drift (PSI/KS)│
                                           │ + performance (rótulos)  │
                                           └────────────┬─────────────┘
                                                        ▼
                         logs JSON (structlog) · métricas e artefatos (MLflow)
                                                        ▼
                                  relatórios HTML + dashboard de monitoramento
```

**Princípio:** o pool de produção sai do **mesmo** dataset da referência, antes de
qualquer perturbação. Por isso o lote de controle (M01) **não deve** acusar drift — se
acusar, o detector está calibrado errado. Tudo o que for detectado nos lotes seguintes é
atribuível à simulação.

> 📄 Decisões, alternativas descartadas e ADRs em **[docs/ARQUITETURA.md](docs/ARQUITETURA.md)**.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Papel | Exigência do enunciado |
|--------|-----------|-------|------------------------|
| Modelo | Scikit-Learn / XGBoost | Classificador base de risco de crédito | ✅ Requerida |
| Contratos de dados | **Pandera** | Regras rígidas e bloqueio de ingestão | ✅ Requerida (GE ou Pandera) |
| Drift | **Evidently AI** | PSI, KS, relatórios HTML | ✅ Requerida |
| Rastreamento | MLflow | Métricas de saúde por execução e por lote | ✅ Sugerida na Etapa 3 |
| Logs | structlog (JSON) | Logs centralizados do pipeline | ✅ Etapa 3 |
| Métricas (opcional) | prometheus-client + Pushgateway + Grafana | Painel ao vivo no ambiente da Fase 3 ([Ambiente Publicado](#-ambiente-publicado-opcional)) | ⚪ Opcional |
| Ambiente | uv + `pyproject.toml` | Versões travadas em `uv.lock` | — |
| Qualidade | ruff + pytest + GitHub Actions | Lint, testes e execução do pipeline no CI | — |
| Padrão de commits | Commitlint + Husky | Histórico semântico | ✅ Requerido |

---

## 📂 Estrutura do Repositório

```
tc04-monitoramento-drift/
├── configs/
│   ├── pipeline.yaml           # ✅ Seed, dataset, limpeza, split, contrato e limiares de alerta
│   └── drift_scenarios.yaml    # ✅ Perturbações de cada lote simulado M01…M06 (Etapa 2)
├── data/                       # Não versionado — gerado pelos scripts
│   ├── raw/                    #   dataset original (e o sintético, se gerado)
│   ├── reference/              #   dataset de referência (treino)
│   ├── production/             #   lotes simulados M01…M06
│   └── quarantine/             #   lotes rejeitados pelo contrato
├── docs/                       # ✅ Documentação do projeto
├── models/                     # Não versionado — artefato do modelo baseline
├── monitoring/
│   ├── grafana/                # ✅ Dashboard do Grafana (JSON) — camada opcional
│   └── helm/                   # ✅ Values do MLflow compartilhado — camada opcional
├── notebooks/                  # ✅ 01_eda · 03 análise de drift e ablação causal
├── reports/                    # ✅ VERSIONADO — evidências (só agregados; nada do sintético)
│   ├── model/                  # ✅ comparação dos candidatos (model_comparison.json)
│   ├── validation/             # ✅ resultado dos contratos por lote
│   ├── drift/                  # ✅ relatórios Evidently por lote + drift_summary.json + ablação causal
│   └── monitoring/             # ✅ dashboard consolidado (dashboard.html)
├── scripts/
│   ├── download_data.py        # ✅ Dataset real (SHA256) ou sintético
│   ├── prepare_data.py         # ✅ Limpeza e split referência × produção
│   ├── train_model.py          # ✅ Treina, compara e promove o modelo (ADR 04)
│   ├── audit_model.py          # ✅ Ablação de AGE/EDUCATION e auditoria de viés (ADR 13)
│   ├── validate_batch.py       # ✅ Demonstra o contrato: lote válido passa, corrompido é bloqueado
│   ├── run_monitoring_demo.py  # ✅ Lote monitorado: estágios, alertas e execução no MLflow
│   ├── build_monitoring_dashboard.py  # ✅ Regenera o dashboard HTML a partir do MLflow
│   ├── run_drift_simulation.py # ✅ Lotes M01…M06: drift (PSI/KS) e performance por lote
│   ├── run_causal_ablation.py  # ✅ Intervenções isoladas e efeito na performance
│   └── verify_setup.py         # ✅ Diz se o ambiente está pronto e o que falta
├── src/
│   ├── config.py               # ✅ Caminhos, seed e configuração
│   ├── data/                   # ✅ Esquema, download, sintético, carga, limpeza e split
│   ├── contracts/              # ✅ Contrato Pandera (C1–C8), avisos e lote corrompido
│   ├── models/                 # ✅ Candidatos, métricas, promoção, ablação e auditoria de viés
│   ├── drift/                  # ✅ Simulação dos cenários e detecção com o Evidently
│   ├── monitoring/             # ✅ Logging · estágios · alertas · MLflow · dashboard · Pushgateway
│   └── pipeline/               # ✅ Preparo, validação, treino, lote monitorado e drift
├── tests/                      # ✅ pytest, sem dependência de rede
└── .github/workflows/          # ✅ CI: lint → testes (contrato + monitoramento) · dataset real · commitlint
                                #    + publicação opcional no ambiente compartilhado
```

**Legenda:** ✅ existe · ⬜ a construir na etapa indicada

> ℹ️ `reports/` é versionado de propósito: o enunciado exige *"relatórios HTML gerados
> comprovando o monitoramento"*. O avaliador precisa conseguir abrir as evidências
> **sem executar nada**.

---

## 🚀 Como Executar

> 🚧 **Esta seção cresce conforme cada etapa é entregue.** Nenhum comando é documentado
> aqui antes de existir no repositório e ter sido executado num clone limpo — ver
> [CLAUDE.md](CLAUDE.md).

### Pré-requisitos

| Ferramenta | Versão | Para quê | Como instalar |
|-----------|--------|----------|---------------|
| **uv** | 0.5+ | Ambiente Python com versões travadas | `pip install uv` ou [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| **Git** | — | Clonar o repositório | — |

O dataset (UCI *Default of Credit Card Clients*, licença CC BY 4.0) é baixado por script,
**sem conta e sem credencial**, e tem a integridade conferida por SHA256 — ver
[docs/DATASET.md](docs/DATASET.md).

O Python 3.12 é instalado pelo próprio `uv`; não é preciso tê-lo no sistema.

> ⚠️ **Todos os comandos usam `uv run`.** Isso executa dentro do ambiente do projeto sem
> ativar venv. Rodar `python ...` direto usaria o Python do sistema, sem as dependências.
> `pip install -e ".[dev]"` **não funciona**: as dependências de desenvolvimento estão em
> `[dependency-groups]` (PEP 735), que o pip ignora.

### 1. Ambiente e dataset

```bash
git clone https://github.com/willmoreira7/tc04-monitoramento-drift.git
cd tc04-monitoramento-drift

uv sync --group dev                          # cria o .venv com as versões do uv.lock
uv run python scripts/download_data.py       # baixa o dataset da UCI e confere o SHA256
uv run python scripts/verify_setup.py        # confirma que está tudo pronto
```

O `verify_setup.py` termina com `ready=True` quando o ambiente está correto; se algo
faltar, ele diz qual comando rodar. Rodar o download de novo é seguro: um arquivo íntegro
não é baixado outra vez, e um arquivo corrompido é substituído.

> ℹ️ Na primeira execução, o Evidently emite um `SyntaxWarning` interno ao ser importado.
> É inofensivo e não se repete.

**Sem acesso à UCI?** Gere um substituto sintético com o mesmo esquema. Ele valida o
pipeline, mas **não** reproduz as métricas documentadas:

```bash
uv run python scripts/download_data.py --synthetic
```

### 2. Limpeza e separação referência × produção

```bash
uv run python scripts/prepare_data.py              # com o sintético: --synthetic
```

Aplica a limpeza declarada em [`configs/pipeline.yaml`](configs/pipeline.yaml) e faz o
split **uma única vez**, estratificado e com seed 42:

| Conjunto | Arquivo | Linhas | Inadimplência |
|----------|---------|--------|---------------|
| Treino | `data/reference/train.parquet` | 10.487 | 22,12% |
| Validação | `data/reference/validation.parquet` | 2.247 | 22,12% |
| Teste | `data/reference/test.parquet` | 2.248 | 22,15% |
| Pool de produção | `data/production/pool.parquet` | 14.983 | 22,13% |

Contagens, taxas e o SHA256 de origem ficam em `data/reference/split_metadata.json`. As
decisões de limpeza estão justificadas no notebook de EDA.

Antes de gravar, referência e pool passam pelo **contrato de dados**: se a limpeza deixar
passar algo inválido, nada é gravado e o treino não roda. Resultado em
[`reports/validation/reference.json`](reports/validation/reference.json) e
[`production_pool.json`](reports/validation/production_pool.json): ambos aprovados, com
um aviso W1 (faturas abaixo de −100 mil, que é um aviso e não bloqueia).

### 3. Análise exploratória

O notebook [`notebooks/01_eda.ipynb`](notebooks/01_eda.ipynb) está versionado **com as
saídas**: dá para lê-lo direto no GitHub, sem executar nada. Para reexecutar:

```bash
uv run jupyter lab notebooks/
```

### 4. Contrato de dados: lote válido × lote corrompido

```bash
uv run python scripts/validate_batch.py --demo valid       # aprovado → exit 0
uv run python scripts/validate_batch.py --demo corrupted   # bloqueado → exit 2
```

Os dois lotes partem de uma amostra do pool de produção. No corrompido (500 linhas) são
injetados defeitos declarados em [`configs/pipeline.yaml`](configs/pipeline.yaml). O
contrato coleta **todas** as violações de uma vez, move o lote inteiro para
`data/quarantine/demo_corrupted/` e encerra com exit code ≠ 0. O lote não chega ao modelo.

| Defeito injetado | Regra | Casos |
|------------------|-------|-------|
| Coluna extra `CPF` (valor fictício) | C1 — esquema exato | 1 coluna |
| `LIMIT_BAL` nulo | C2 — sem nulos (e C1: tipo) | 5 |
| `ID` repetido | C3 — chave única | 10 |
| `AGE` = 15 e 130 | C4 — idade entre 18 e 100 | 5 |
| `EDUCATION` = 7 | C6 — código no dicionário | 5 |
| `PAY_AMT1` negativo | C8 — pagamento ≥ 0 | 5 |

Relatório: [`reports/validation/demo_corrupted.json`](reports/validation/demo_corrupted.json).
As 8 regras críticas e os 4 avisos estão em [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md).

### 5. Monitoramento por lote (Etapa 3)

Cada lote roda pelos estágios do pipeline com latência, volume e status medidos; os alertas
são avaliados e a execução é registrada no MLflow local — inclusive a do lote bloqueado.

```bash
uv run python scripts/run_monitoring_demo.py --demo valid       # exit 0
uv run python scripts/run_monitoring_demo.py --demo corrupted   # exit 2: bloqueado pelo contrato
uv run python scripts/build_monitoring_dashboard.py             # regenera o dashboard
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db         # execuções em http://127.0.0.1:5000
```

| Evidência | Onde |
|-----------|------|
| Dashboard consolidado (abre no navegador, sem subir serviço) | `reports/monitoring/dashboard.html` |
| Execuções, métricas e artefatos por lote | MLflow local (`mlflow.db`, não versionado) |
| Log centralizado de todos os estágios | `logs/pipeline.jsonl` (não versionado; anexado a cada execução) |

Métricas, alertas e playbook: [docs/MONITORING.md](docs/MONITORING.md). Os lotes M01…M06
da Etapa 2 passam pelo mesmo fluxo, com os estágios de predição, drift e performance
(passo 8).

> 📡 **Opcional — Grafana ao vivo.** Os mesmos lotes podem ser acompanhados no Grafana do
> laboratório: ver [Ambiente Publicado](#-ambiente-publicado-opcional).

### 6. Modelo base

```bash
uv run python scripts/train_model.py
```

Treina três candidatos no mesmo split, com parâmetros padrão, e promove pelo critério
declarado antes do treino. A comparação é **enxuta de propósito**: o modelo é o objeto
monitorado, não o entregável (ADR 04 em [docs/ARQUITETURA.md](docs/ARQUITETURA.md)).

| Modelo | AUC validação | AUC teste | KS teste | |
|--------|---------------|-----------|----------|---|
| **XGBoost** | **0,7622** | **0,7368** | 0,3779 | ✅ promovido |
| LogisticRegression | 0,7081 | 0,7183 | 0,3938 | elegível |
| Dummy | 0,4902 | 0,4910 | 0,0000 | piso |

O modelo vai para `models/baseline/` (não versionado); a comparação completa fica em
[`reports/model/model_comparison.json`](reports/model/model_comparison.json) (versionado).
Leitura dos resultados e limitações no [Model Card](docs/MODEL_CARD.md).

O modelo usa **só as 19 variáveis financeiras**: `AGE` e `EDUCATION` saíram pela ablação
do passo 7.

### 7. Ablação e auditoria de viés

```bash
uv run python scripts/audit_model.py
```

- **Ablação** ([`reports/model/ablation.json`](reports/model/ablation.json)): repete a
  comparação com e sem `AGE`/`EDUCATION` e aplica o critério declarado antes de rodar (ADR
  13). Sem os dois, a AUC de validação vai de 0,7602 para 0,7622, então eles saem.
- **Viés** ([`reports/model/fairness_audit.json`](reports/model/fairness_audit.json)):
  aprovação e recall por grupo de sexo, idade, escolaridade e estado civil, no teste,
  com o modelo promovido. Leitura na [seção 6 de Governança](#6-mitigação-de-vieses).

### 8. Simulação e detecção de drift (Etapa 2)

```bash
uv run python scripts/run_drift_simulation.py      # exige os passos 2 e 6
```

Gera seis lotes mensais de 2.400 linhas a partir do pool de produção, com as perturbações
declaradas em [`configs/drift_scenarios.yaml`](configs/drift_scenarios.yaml). Cada lote
passa pelo contrato, pelo modelo e pela detecção, que usa **PSI e KS configurados
explicitamente** no Evidently, coluna a coluna, contra a janela de referência
(validação + teste). Cada lote também vira uma execução no MLflow, e o dashboard é
regenerado.

> 🔴 **O drift é simulado.** Os rótulos de cada lote são revelados no próprio lote.

| Lote | Cenário | Colunas com PSI ≥ 0,10 | AUC | Alertas |
|------|---------|------------------------|-----|---------|
| Referência | — | — | 0,7495 | — |
| M01 | Controle, sem perturbação | nenhuma | 0,7496 | nenhum |
| M02 | Faturas +10% | nenhuma (o KS acusa; o PSI, não) | 0,7489 | nenhum |
| M03 | Mais jovens, faturas +25% | `AGE` | 0,7654 | atenção |
| M04 | Aperto de crédito | `LIMIT_BAL`, `PAY_0`, `AGE` e o score | 0,7930 | atenção (drift sem degradação) |
| M05 | Concept drift | nenhuma | 0,6821 | **crítico: AUC e recall** |
| M06 | Crise (M04 + M05) | `LIMIT_BAL`, `PAY_0`, `AGE` e o score | 0,7286 | atenção — a queda de performance fica escondida |

| Evidência | Onde |
|-----------|------|
| Números de todos os lotes | [`reports/drift/drift_summary.json`](reports/drift/drift_summary.json) |
| Relatório do Evidently por lote (baixe e abra no navegador) | `reports/drift/M01.html` … `M06.html` |
| Contrato de cada lote | `reports/validation/M01.json` … `M06.json` |

A análise causal da interação e as limitações estão em [docs/DRIFT.md](docs/DRIFT.md#-análise-causal).

A ablação por intervenção isolada é reprodutível com:

```bash
uv run python scripts/run_causal_ablation.py      # exige preparo e modelo; saída em reports/drift/
```

O JSON completo e o notebook estão versionados: [causal_ablation.json](reports/drift/causal_ablation.json) · [03_drift_analysis.ipynb](notebooks/03_drift_analysis.ipynb).

### 9. Testes e qualidade de código

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run nbqa ruff notebooks/
```

### Padrão de commits (opcional, só para contribuir)

```bash
npm install
npm run prepare
```

Requer Node.js. **Não é necessário para rodar nem avaliar o projeto** — serve apenas para
validar mensagens de commit. Ver [docs/COMMITLINT.md](docs/COMMITLINT.md).

---

## 🌐 Ambiente Publicado (opcional)

O Prometheus e o Grafana da Fase 3
([tc03-cloud-mlops](https://github.com/willmoreira7/tc03-cloud-mlops), cluster EKS do
laboratório) são reaproveitados como painel ao vivo, e o mesmo cluster hospeda um MLflow
compartilhado (`MLFLOW_TRACKING_URI`). O pipeline é batch, então cada lote
**envia** suas métricas a um Pushgateway, que o Prometheus coleta e o Grafana exibe.

O avaliador pode abrir o [MLflow compartilhado](https://mlflow.pocsarcotech.com) e o
[dashboard Grafana](https://grafana.pocsarcotech.com/d/tc04-batch-monitoring), se tiver
acesso ao laboratório. Para enviar métricas ao Pushgateway, configure `TC04_PUSHGATEWAY_URL`,
`TC04_PUSHGATEWAY_USERNAME` e `TC04_PUSHGATEWAY_PASSWORD` por um gerenciador de segredos
local; para rastrear no servidor, configure `MLFLOW_TRACKING_URI`,
`MLFLOW_TRACKING_USERNAME` e `MLFLOW_TRACKING_PASSWORD`. **Credenciais não são publicadas
neste repositório**; solicite acesso pelos canais autorizados. Os comandos abaixo também
funcionam sem credenciais, usando o MLflow local e o dashboard HTML versionado:

```bash
uv run python scripts/run_monitoring_demo.py --demo valid
uv run python scripts/run_monitoring_demo.py --demo corrupted   # exit 2
```

| Serviço | URL | Acesso |
|---------|-----|--------|
| Grafana — dashboard do TC04 | <https://grafana.pocsarcotech.com/d/tc04-batch-monitoring> | Autenticado; solicitar acesso |
| Prometheus | <https://prometheus.pocsarcotech.com> | Conforme configuração do laboratório |
| Pushgateway | <https://pushgateway.pocsarcotech.com> | Basic Auth; credenciais por canal autorizado |
| MLflow — execuções por lote | <https://mlflow.pocsarcotech.com> | Autenticado; solicitar acesso |

- No Prometheus, as séries do projeto começam com `tc04_` (ex.: `tc04_batch_status`,
  `tc04_stage_status`).
- O dashboard do Grafana é versionado em
  [`monitoring/grafana/tc04-batch-monitoring.json`](monitoring/grafana/tc04-batch-monitoring.json).
- Para registrar os lotes no MLflow compartilhado em vez do `mlflow.db` local, ver
  [docs/MONITORING.md](docs/MONITORING.md#-mlflow-compartilhado-opcional).
- A cada merge na `main` (ou por disparo manual), o workflow
  [`publish-monitoring.yml`](.github/workflows/publish-monitoring.yml) publica os lotes do
  dataset real nesse ambiente. É separado do CI: ambiente fora do ar não bloqueia PR.
  Configuração, gatilhos e leitura do resultado em
  [docs/MONITORING.md](docs/MONITORING.md#-publicação-automática-workflow-opcional).

> 🔐 Não versionamos segredos nem os incluímos em exemplos. Como credenciais antigas
> chegaram a constar no histórico do repositório, os responsáveis pelo laboratório devem
> revogá-las/rotacioná-las antes da entrega pública; apagar os valores do arquivo não os
> remove do histórico Git.

> ℹ️ Este ambiente é **demonstração** e não substitui a evidência versionada. Sem as variáveis
> `TC04_PUSHGATEWAY_URL` e `MLFLOW_TRACKING_URI` nada é enviado, e o avaliador vê tudo pelo MLflow local e por
> `reports/monitoring/dashboard.html`. O Pushgateway exige o login da tabela para enviar,
> apagar ou ler métricas; só métricas agregadas trafegam por ele. Detalhes em
> [docs/MONITORING.md](docs/MONITORING.md#-grafana-e-prometheus-opcional).

---

## 🗺️ Roadmap das Etapas

| Etapa | Disciplina | Entregável | Status |
|-------|-----------|-----------|--------|
| **0** | — | Documentação, regras, ambiente, download do dataset e CI | ✅ Concluída |
| **1** | Validação de Dados e Bibliotecas de Qualidade | Contrato Pandera + lote ruim bloqueado + modelo baseline | ✅ Concluída |
| **2** | Data Drift | Lotes simulados + relatórios Evidently (PSI/KS) + ablação causal | ✅ Concluída |
| **3** | Monitoramento de Pipelines e Infraestrutura | Logs centralizados + MLflow + dashboard HTML | ✅ Concluída; MLflow externo opcional |
| **4** | Privacy by Design e by Default | Governança LGPD + análise causal + vídeo STAR | 🟡 Em andamento: falta o vídeo |

> 📄 Tarefas, critérios de aceite e conformidade item a item com o enunciado em
> **[docs/ROADMAP.md](docs/ROADMAP.md)**.

---

## 📊 Critérios de Avaliação

| Critério | Peso | Onde é atendido |
|----------|------|-----------------|
| Validação de Dados | 25% | Etapa 1 — [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md) + `reports/validation/` |
| Detecção de Drift | 25% | Etapa 2 — [docs/DRIFT.md](docs/DRIFT.md) + `reports/drift/` |
| Observabilidade e Logs | 20% | Etapa 3 — [docs/MONITORING.md](docs/MONITORING.md) + `reports/monitoring/` |
| Governança (LGPD) | 15% | Etapa 4 — [seção de Governança](#%EF%B8%8F-governança-e-lgpd) deste README |
| Vídeo STAR (≤ 5 min) | 15% | Etapa 4 — [docs/VIDEO_STAR.md](docs/VIDEO_STAR.md) |

---

## ⚖️ Governança e LGPD

> O enunciado exige esta documentação **consolidada no README**. Ela vive aqui, não em
> `docs/`.

> ℹ️ **Premissa.** O dataset é público, de origem taiwanesa e já anonimizado na fonte. A
> análise abaixo trata o projeto **como se fosse a operação de uma fintech brasileira**
> sujeita à Lei 13.709/2018 (LGPD), que é o cenário do enunciado.

### 1. Origem dos dados e termos de uso

Antes de governar os dados dos clientes da fintech fictícia, o grupo precisa ter o
**direito de usar** os dados que ele mesmo obteve. É o princípio da finalidade (art. 6º, I)
aplicado ao próprio projeto.

| Item | Situação |
|------|----------|
| Fonte | [UCI ML Repository, id 350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) |
| Licença | **CC BY 4.0** — permite usar, **adaptar** e redistribuir, com atribuição |
| Atribuição | Yeh, I. (2009). *Default of Credit Card Clients* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C55S3H |
| Anonimização | Feita na fonte: sem nome, documento ou contato |
| Integridade | SHA256 registrado em [docs/DATASET.md](docs/DATASET.md#-proveniência) e conferido no download |

#### 🚫 Por que não usamos o Home Credit Default Risk

O Home Credit foi a **primeira escolha** do grupo: é sugerido pelo próprio enunciado e é
mais rico (renda, emprego, scores de bureau). Chegamos a baixá-lo. Ao ler as regras da
competição do Kaggle — aceitas por todo usuário antes do download — encontramos:

> *"After your acceptance of these Rules, you may access and use the Competition Data
> **only for the purposes of the Competition**."* — regra específica da competição, que
> **substitui** a permissão genérica para uso acadêmico (regra geral 7.A)

> *"You agree **not to manipulate the data** and not to use it for any other purpose other
> than to participate in the Competition."* — regra geral 7.B

Este projeto é acadêmico (fora da finalidade permitida), **altera a distribuição dos dados
de propósito** para simular drift (manipulação proibida) e precisa mostrar resultados a um
avaliador que não aceitou as regras (disponibilização proibida). Os três pontos conflitam
com os termos. **Trocamos de dataset e eliminamos a cópia local.**

> 💡 **"Público" não significa "de uso livre".** O dataset estava a um clique, era sugerido
> pelo enunciado e é amplamente usado em cursos — e ainda assim os termos não cobriam este
> uso. Verificar a licença virou passo obrigatório da escolha de dados (ADR 12). O custo
> da troca (perder renda e emprego) está detalhado em
> [docs/DATASET.md](docs/DATASET.md#-por-que-não-o-home-credit).

### 2. Inventário de dados pessoais

| Coluna | Classificação LGPD | Usada no modelo? | Tratamento |
|--------|-------------------|------------------|------------|
| `ID` | Chave sequencial atribuída na fonte (pseudônimo) | ❌ Não | Usada só para unicidade e rastreio; nunca é feature |
| `SEX` | Dado pessoal com potencial discriminatório | ❌ Não | Fora das features; mantida só no conjunto de **auditoria de viés** |
| `MARRIAGE` | Dado pessoal com potencial discriminatório | ❌ Não | Idem `SEX` |
| `AGE` | Dado pessoal | ❌ Não (ADR 13) | Removida pela ablação: sem ela a AUC não cai. Continua no lote para o contrato (≥ 18) e para a auditoria de viés |
| `EDUCATION` | Dado pessoal (proxy socioeconômico) | ❌ Não (ADR 13) | Removida pela ablação, junto com `AGE`. Continua só na auditoria de viés |
| `LIMIT_BAL`, `PAY_*`, `BILL_AMT*`, `PAY_AMT*` | Dados financeiros pessoais | ✅ Sim | Necessários à finalidade (avaliação de risco) |

Nenhuma coluna do dataset é **dado pessoal sensível** no sentido do art. 5º, II (origem
racial, saúde, religião, biometria etc.). Sexo e estado civil não estão nessa lista, mas
o **princípio da não discriminação** (art. 6º, IX) justifica tirá-los do modelo.

### 3. Base legal da decisão de crédito

| Tratamento | Base legal | Fundamento |
|-----------|-----------|-----------|
| Avaliar o risco de crédito do proponente | **Proteção do crédito** — art. 7º, X | Hipótese própria da LGPD para análise de crédito; dispensa consentimento |
| Usar histórico de adimplemento | Lei 12.414/2011 (Cadastro Positivo) | Regula a formação de histórico de crédito |
| Monitorar o modelo e auditar viés | Legítimo interesse — art. 7º, IX | Garantir qualidade e não discriminação da decisão; balanceado pelo art. 10 |

**Decisão automatizada (art. 20).** O titular pode pedir revisão de decisões tomadas
unicamente com base em tratamento automatizado, incluindo a definição do perfil de
crédito. Consequências para este projeto:

- O score é **apoio à decisão**; recusas ficam sujeitas a revisão humana
- O Model Card documenta os critérios de forma compreensível (art. 20, §1º)
- Cada predição é rastreável à versão do modelo e ao lote que a gerou (logs + MLflow)

### 4. Privacy by Design e by Default no pipeline

| Princípio (art. 6º) | Como o pipeline aplica |
|--------------------|------------------------|
| Necessidade (minimização) | O modelo usa só variáveis financeiras: `ID`, `SEX`, `MARRIAGE`, `AGE` e `EDUCATION` não chegam a ele (ADR 08 e 13); o contrato rejeita colunas fora do esquema |
| Finalidade | Dados de produção usados só para scoring e monitoramento; nenhum uso secundário |
| Qualidade dos dados | O contrato de dados **é** a implementação deste princípio |
| Segurança | Dados brutos fora do Git (`.gitignore`); relatórios versionados não contêm linhas individuais |
| Transparência | Model Card público; critérios de decisão documentados |
| Não discriminação | Atributos sensíveis fora das features + métricas de viés por grupo |
| Responsabilização | Logs estruturados e execuções no MLflow formam a trilha de auditoria (art. 37) |

> ⚠️ **Relatórios versionados não podem vazar dados pessoais.** Os HTML do Evidently
> trazem distribuições agregadas por feature; o pipeline **não** versiona amostras de
> linhas. Isso é verificado antes de cada commit em `reports/`.

### 5. Plano de retenção

| Dado | Retenção | Fundamento | Destino ao fim |
|------|----------|-----------|----------------|
| Dados brutos de proponentes | Enquanto durar a relação + prazo legal | Art. 15 e 16 | Eliminação |
| Histórico de adimplemento | Até 15 anos | Lei 12.414/2011, art. 14 | Eliminação |
| Informação negativa (inadimplência) | Até 5 anos | CDC, art. 43, §1º | Eliminação |
| Dataset de referência do modelo | Vida útil do modelo + auditoria | Art. 16, II (obrigação regulatória) | Anonimização |
| Lotes em quarentena | 30 dias 🟡 *proposta* | Investigação da falha | Eliminação |
| Logs e métricas de monitoramento | Sem dado pessoal; retenção livre | Agregados, não identificam titular | — |

### 6. Mitigação de vieses

**1. Minimização por evidência (ADR 13).** Antes de rodar, ficou declarado que um
atributo pessoal só fica no modelo se pagar por si (perda < 0,01 de AUC na validação ao
removê-lo). Resultado: sem `AGE` e `EDUCATION`, a AUC de validação foi de 0,7602 para
0,7622. Os dois saíram, e o modelo usa só dados financeiros.

> ⚠️ No teste, a mesma remoção custou 0,011 de AUC (0,7479 para 0,7368). A decisão é
> tomada na validação, e o teste só reporta. Detalhes no [Model Card](docs/MODEL_CARD.md#-ablação-de-age-e-education-adr-13).

**2. Auditoria do resultado por grupo** (teste, n = 2.248, modelo promovido). Fonte:
[`reports/model/fairness_audit.json`](reports/model/fairness_audit.json).

| Atributo | Menor razão de impacto | Menor razão entre bons pagadores | Abaixo de 4/5? |
|----------|------------------------|----------------------------------|----------------|
| `SEX` | 0,937 | 0,984 | Não |
| `AGE` (faixas) | 0,939 | 0,956 | Não |
| `EDUCATION` | 0,872 | **0,864** | Não |
| `MARRIAGE` | 0,961 | 0,963 | Não |

A razão entre bons pagadores é a leitura principal. Ela compara a aprovação de quem
**não** ficou inadimplente: um bom pagador tem a mesma chance em qualquer grupo?

**O que os números dizem:**

- **Nenhum grupo fica abaixo da regra dos 4/5.**
- **O ponto de atenção é a escolaridade "ensino médio":**
  - Com a mesma inadimplência real da pós-graduação (cerca de 21%), bons pagadores desse
    grupo são aprovados em 73,1% dos casos, contra 84,7%.
  - O grupo tem metade do limite mediano e mais atraso recente. São variáveis financeiras
    legítimas, mas correlacionadas com escolaridade.
  - **Remover `EDUCATION` não removeu a diferença:** na validação, a razão foi de 0,87 para
    0,82. Tirar o atributo não basta; é preciso medir o resultado.
- **Sexo:** o modelo identifica menos inadimplentes entre mulheres (recall 51% contra 62%).
  Isso favorece a aprovação delas sem prejudicar bons pagadores.

**3. Mitigação:**

- Atributos pessoais fora das features.
- Auditoria por grupo reexecutada a cada treino.
- Revisão humana das recusas (art. 20).
- 🟡 Razões por grupo acompanhadas por lote no monitoramento (Etapa 3).
- **Descartado:** limiar diferente por grupo, porque exigiria usar o atributo protegido na
  própria decisão.

Tabela completa por grupo no [Model Card](docs/MODEL_CARD.md#️-vieses-e-equidade).

---

## 🔬 Análise Causal da Degradação

A pergunta não é apenas *"houve drift?"*, mas *"qual mecanismo mudou a carteira e o que aconteceu com o modelo?"*. Aplicamos as perturbações isoladamente sobre lotes de 2.400 registros, com seed 42, e comparamos com M01 (controle). As diferenças são **efeitos observados nesta simulação controlada**, não estimativas causais generalizáveis nem evidência sobre uma carteira real.

| Intervenção isolada | Features com PSI ≥ 0,10 | Δ AUC vs. M01 | Δ recall inadimplentes | Δ aprovação | Leitura |
|---|---|---:|---:|---:|---|
| Inflação nominal (`BILL_AMT*` +10%) | nenhuma (PSI máx. 0,016) | −0,0007 | −0,0020 | −0,0021 | KS D nas faturas aumenta (máx. 0,052), mas a magnitude PSI é pequena e a performance quase não muda. |
| Mais clientes jovens | `AGE` | +0,0142 | +0,0240 | −0,0079 | AUC e recall melhoram ligeiramente; drift não implica degradação. `AGE` é atributo monitorado, não feature do modelo. |
| Mais clientes em atraso (`PAY_0` ≥ 2) | `PAY_0` | +0,0588 | +0,1573 | −0,1404 | A inadimplência sobe 10,33 p.p.; a discriminação melhora nesta carteira, com menor aprovação. |
| Limites menores (`LIMIT_BAL` × 0,85) | `LIMIT_BAL` | −0,0076 | −0,0233 | 0,0000 | Mudança de limite sem mudança da taxa de inadimplência; efeito pequeno na performance nesta amostra. |
| Concept drift (reetiquetagem) | nenhuma | −0,0675 | −0,1225 | 0,0000 | Features e score permanecem estáveis; a degradação aparece quando os rótulos simulados são revelados. |

**Interação na crise (M06):** combinado ao aperto, o concept drift reduz AUC em 0,0644 e recall em 0,1036 contra M04, mas contra a referência agregada M01 a queda de AUC é apenas 0,021 e o recall ainda sobe. Assim, o baseline agregado não dispara alerta de performance para M06: a composição da carteira mascara a mudança condicional. O detector continua apontando drift nas features/score, mas não deve ser interpretado como prova de queda de performance.

> **Limites:** os rótulos dos lotes são sintéticos e imediatamente disponíveis; em crédito real chegam com atraso. A ablação usa uma seed e uma população de origem; os deltas são descritivos, sem intervalo de confiança. O experimento mostra os mecanismos deste projeto, não estima impacto em uma fintech real.

Resultados completos e definições: [relatório causal JSON](reports/drift/causal_ablation.json), [notebook 03](notebooks/03_drift_analysis.ipynb) e [docs/DRIFT.md](docs/DRIFT.md#-análise-causal).

---

## 🎥 Vídeo

🟡 Pendente — roteiro em [docs/VIDEO_STAR.md](docs/VIDEO_STAR.md).

---

## 📚 Documentação

| Documento | Conteúdo |
|-----------|----------|
| [docs/ROADMAP.md](docs/ROADMAP.md) | Etapas, tarefas, critérios de aceite e **conformidade com o enunciado** |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Decisões de ferramenta e de desenho, com ADRs |
| [docs/DATASET.md](docs/DATASET.md) | Escolha do dataset, esquema e separação referência × produção |
| [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md) | Regras do contrato, severidade e comportamento de bloqueio |
| [docs/DRIFT.md](docs/DRIFT.md) | Desenho da simulação, testes estatísticos, limiares e análise causal |
| [docs/MONITORING.md](docs/MONITORING.md) | Métricas de saúde, alertas e playbook de resposta |
| [docs/MODEL_CARD.md](docs/MODEL_CARD.md) | Model Card do modelo baseline |
| [docs/VIDEO_STAR.md](docs/VIDEO_STAR.md) | Roteiro do vídeo |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Fluxo de branches, PRs e ambiente local |
| [docs/COMMITLINT.md](docs/COMMITLINT.md) | Padrão de mensagens de commit |

---

**Última atualização:** 2026-11-17
