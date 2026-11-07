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
- **Etapa 3 — Observabilidade:** logs estruturados, métricas do pipeline e alertas de drift no MLflow + dashboard
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
| Métricas (opcional) | prometheus-client | Integração com a stack da Fase 3 | ⚪ Opcional |
| Ambiente | uv + `pyproject.toml` | Versões travadas em `uv.lock` | — |
| Qualidade | ruff + pytest + GitHub Actions | Lint, testes e execução do pipeline no CI | — |
| Padrão de commits | Commitlint + Husky | Histórico semântico | ✅ Requerido |

---

## 📂 Estrutura do Repositório

```
tc04-monitoramento-drift/
├── configs/
│   ├── pipeline.yaml           # ✅ Seed, dataset, limpeza e split (limiares nas próximas etapas)
│   └── drift_scenarios.yaml    # ⬜ Perturbações de cada lote simulado (Etapa 2)
├── data/                       # Não versionado — gerado pelos scripts
│   ├── raw/                    #   dataset original (e o sintético, se gerado)
│   ├── reference/              #   dataset de referência (treino)
│   ├── production/             #   lotes simulados M01…M06
│   └── quarantine/             #   lotes rejeitados pelo contrato
├── docs/                       # ✅ Documentação do projeto
├── models/                     # Não versionado — artefato do modelo baseline
├── notebooks/                  # ✅ 01_eda · ⬜ baseline e análise de drift
├── reports/                    # ⬜ VERSIONADO — evidências HTML do monitoramento
│   ├── validation/             #   resultado dos contratos por lote
│   ├── drift/                  #   relatórios Evidently por lote
│   └── monitoring/             #   dashboard consolidado
├── scripts/
│   ├── download_data.py        # ✅ Dataset real (SHA256) ou sintético
│   ├── prepare_data.py         # ✅ Limpeza e split referência × produção
│   └── verify_setup.py         # ✅ Diz se o ambiente está pronto e o que falta
├── src/
│   ├── config.py               # ✅ Caminhos, seed e configuração
│   ├── data/                   # ✅ Esquema, download, sintético, carga, limpeza e split
│   ├── contracts/              # ⬜ Schemas Pandera e validação (Etapa 1)
│   ├── models/                 # ⬜ Treino e predição do baseline (Etapa 1)
│   ├── drift/                  # ⬜ Simulação e detecção (Etapa 2)
│   ├── monitoring/             # ✅ Logging (structlog) · ⬜ métricas e alertas (Etapa 3)
│   └── pipeline/               # ✅ Preparo dos dados · ⬜ demais estágios
├── tests/                      # ✅ pytest, sem dependência de rede
└── .github/workflows/          # ✅ CI: lint → testes · dataset real · commitlint
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

### 3. Análise exploratória

O notebook [`notebooks/01_eda.ipynb`](notebooks/01_eda.ipynb) está versionado **com as
saídas**: dá para lê-lo direto no GitHub, sem executar nada. Para reexecutar:

```bash
uv run jupyter lab notebooks/
```

### 4. Testes e qualidade de código

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

## 🗺️ Roadmap das Etapas

| Etapa | Disciplina | Entregável | Status |
|-------|-----------|-----------|--------|
| **0** | — | Documentação, regras, ambiente, download do dataset e CI | ✅ Concluída |
| **1** | Validação de Dados e Bibliotecas de Qualidade | Contrato Pandera + lote ruim bloqueado + modelo baseline | ⬜ Não iniciada |
| **2** | Data Drift | Lotes simulados + relatórios Evidently (PSI/KS) | ⬜ Não iniciada |
| **3** | Monitoramento de Pipelines e Infraestrutura | Logs centralizados + MLflow + dashboard | ⬜ Não iniciada |
| **4** | Privacy by Design e by Default | Governança LGPD + análise causal + vídeo STAR | ⬜ Não iniciada |

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
| `AGE` | Dado pessoal | 🟡 A decidir na Etapa 1 | Necessária ao contrato (≥ 18); uso como feature depende da auditoria de viés |
| `EDUCATION` | Dado pessoal (proxy socioeconômico) | 🟡 A decidir na Etapa 1 | Decisão por ablação: removida se o custo em AUC for desprezível |
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
| Necessidade (minimização) | `ID`, `SEX` e `MARRIAGE` não chegam ao modelo; o contrato rejeita colunas fora do esquema |
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

> 🟡 **A preencher na Etapa 1** com números medidos: taxa de aprovação e recall por grupo
> de `SEX`, `AGE` (faixas) e `EDUCATION`, razão de impacto desigual (regra dos 4/5) e o
> resultado da ablação de `AGE`/`EDUCATION`.

---

## 🔬 Análise Causal da Degradação

> 🟡 **A preencher nas Etapas 2 e 4.** Estrutura definida em
> [docs/DRIFT.md](docs/DRIFT.md#-análise-causal).

A pergunta não é *"houve drift?"*, e sim *"qual mudança causou a queda de performance?"*.
Drift detectado não implica degradação, e degradação pode ocorrer sem drift detectável
nas features (concept drift). Como a simulação é controlada, cada perturbação é aplicada
**isoladamente** e o impacto em AUC, recall e taxa de aprovação é medido — uma
intervenção, não uma correlação.

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

**Última atualização:** 2026-11-07
