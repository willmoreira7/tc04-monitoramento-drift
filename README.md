# 💳 tc04-monitoramento-drift — Sustentação e Confiabilidade de um Modelo de Credit Scoring

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
| Lote com dados inválidos (renda nula, idade < 18, duplicatas, 1.000 anos de emprego) | O modelo pontua lixo sem reclamar | **Contrato de dados** bloqueia o lote antes da inferência |
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
  Home Credit ─► │ limpeza → split 50/50 estratificado (seed 42)│
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
│   ├── pipeline.yaml           # ⬜ Seed, splits, limiares de drift e de alerta
│   └── drift_scenarios.yaml    # ⬜ Perturbações de cada lote simulado
├── data/                       # Não versionado — gerado pelos scripts
│   ├── raw/                    #   dataset original
│   ├── reference/              #   dataset de referência (treino)
│   ├── production/             #   lotes simulados M01…M06
│   └── quarantine/             #   lotes rejeitados pelo contrato
├── docs/                       # ✅ Documentação do projeto
├── models/                     # Não versionado — artefato do modelo baseline
├── notebooks/                  # ⬜ EDA, baseline e análise de drift
├── reports/                    # ⬜ VERSIONADO — evidências HTML do monitoramento
│   ├── validation/             #   resultado dos contratos por lote
│   ├── drift/                  #   relatórios Evidently por lote
│   └── monitoring/             #   dashboard consolidado
├── scripts/                    # ⬜ Download, verificação de ambiente, pipeline completo
├── src/
│   ├── data/                   # ⬜ Loader e split referência × produção
│   ├── contracts/              # ⬜ Schemas Pandera e validação (Etapa 1)
│   ├── models/                 # ⬜ Treino e predição do baseline (Etapa 1)
│   ├── drift/                  # ⬜ Simulação e detecção (Etapa 2)
│   ├── monitoring/             # ⬜ Logs, métricas, alertas (Etapa 3)
│   └── pipeline/               # ⬜ Orquestração das etapas
├── tests/                      # ⬜ pytest
└── .github/workflows/          # ⬜ CI: lint → testes → pipeline fim a fim
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
| **Conta no Kaggle** | — | Baixar o dataset (não versionado) | [Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk/data) |

> 🔐 **Acesso aos dados — leia antes de começar.** O dataset **Home Credit Default Risk**
> não está neste repositório e não pode ser compartilhado entre pessoas: os termos de uso
> da competição condicionam o acesso a uma conta no Kaggle com as regras aceitas. Cada
> pessoa (integrante do grupo ou avaliador) baixa com **a própria conta e o próprio token**.
>
> 1. Criar conta no Kaggle e aceitar as regras em [Home Credit Default Risk → Rules](https://www.kaggle.com/competitions/home-credit-default-risk/rules)
>    (sem o aceite, a API retorna 403)
> 2. Gerar um token em *Settings → API* e defini-lo na variável de ambiente `KAGGLE_API_TOKEN`
>    — nunca em arquivo dentro do projeto
> 3. Rodar o script de download (⬜ Etapa 0), que confere o SHA256 do arquivo
>
> **Sem conta?** O projeto gera dados sintéticos com o mesmo esquema: validam o pipeline,
> mas não reproduzem as métricas. Os resultados do dataset real estão versionados em
> `reports/` e podem ser lidos sem executar nada. Motivo e detalhes em
> [Governança — Origem dos dados](#1-origem-dos-dados-e-termos-de-uso) e
> [docs/DATASET.md](docs/DATASET.md#-obtenção).

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
| **0** | — | Documentação inicial, regras e definições | 🟡 Em andamento |
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

> ℹ️ **Premissa.** O dataset (Home Credit Default Risk) é público e foi anonimizado pelo
> provedor. A análise abaixo trata o projeto **como se fosse a operação de uma fintech
> brasileira** sujeita à Lei 13.709/2018 (LGPD), que é o cenário do enunciado.

### 1. Origem dos dados e termos de uso

Antes de governar os dados dos clientes da fintech fictícia, o projeto precisa respeitar
as condições sob as quais **nós** obtivemos os dados. É o mesmo princípio da finalidade
(art. 6º, I) aplicado ao próprio grupo.

| Item | Situação |
|------|----------|
| Fonte | Competição pública *Home Credit Default Risk* no Kaggle (Home Credit Group, 2018) |
| Anonimização | Feita pelo provedor; `SK_ID_CURR` é um pseudônimo, sem nome, documento ou contato |
| Condição de acesso | Conta no Kaggle **com as regras da competição aceitas**, individualmente |
| Termos de uso | Uso não comercial, sem redistribuição dos dados a terceiros — 🟡 citar o trecho exato da aba *Rules* |
| Finalidade neste projeto | Acadêmica: demonstrar sustentação de modelos (pós-graduação FIAP) |

**Decisões que decorrem dos termos (ADR 12):**

| Decisão | Como é aplicada |
|---------|-----------------|
| Nenhum dado em nível de linha é versionado | `data/` inteiro no `.gitignore`: bruto, referência, lotes simulados e quarentena — os lotes **derivam** do dado original, então também não podem ser publicados |
| Nenhum dado é repassado por outro canal | Sem Drive, S3 ou mensagem entre integrantes; cada pessoa baixa com a própria conta |
| Credenciais são pessoais | Token do Kaggle só em variável de ambiente; nunca em arquivo do projeto, nunca compartilhado |
| Mesmo arquivo para todos | SHA256 registrado em [docs/DATASET.md](docs/DATASET.md#-proveniência) e conferido pelo script de download |
| Só agregados são publicados | `reports/`, Model Card e métricas trazem distribuições e estatísticas, nunca linhas |
| Alternativa sem conta | Gerador sintético a partir de parâmetros declarados no código, sem copiar linhas do dataset |

### 2. Inventário de dados pessoais

Das 122 colunas originais, o pipeline ingere ~20. O recorte **já é** a primeira medida de
minimização — ver [docs/DATASET.md](docs/DATASET.md#-recorte-de-colunas).

| Coluna(s) | Classificação LGPD | Usada no modelo? | Tratamento |
|-----------|-------------------|------------------|------------|
| `SK_ID_CURR` | Dado pseudonimizado (art. 13, §4º) — continua sendo dado pessoal | ❌ Não | Só como chave de unicidade e rastreio |
| `FLAG_MOBIL`, `FLAG_EMAIL`, `FLAG_PHONE`… | Dados de contato | ❌ Não | **Descartados na ingestão** (necessidade, art. 6º, III) |
| `CODE_GENDER` | Dado pessoal com potencial discriminatório | ❌ Não | Fora das features; mantido só no conjunto de **auditoria de viés** |
| `NAME_FAMILY_STATUS` | Dado pessoal com potencial discriminatório | ❌ Não | Idem `CODE_GENDER` |
| `DAYS_BIRTH` (idade) | Dado pessoal | 🟡 A decidir na Etapa 1 | Necessária ao contrato (≥ 18); uso como feature depende da auditoria de viés |
| `NAME_EDUCATION_TYPE` | Dado pessoal (proxy socioeconômico) | 🟡 A decidir na Etapa 1 | Ablação: removida se o custo em AUC for desprezível |
| `CNT_CHILDREN`, `CNT_FAM_MEMBERS` | Dado pessoal (proxy de estado civil) | 🟡 A decidir na Etapa 1 | Ablação, pelo mesmo critério |
| `REGION_RATING_CLIENT` | Dado de localização (proxy socioeconômico) | 🟡 A decidir na Etapa 1 | Auditado por grupo: risco de discriminação geográfica |
| `EXT_SOURCE_2`, `EXT_SOURCE_3` | Scores de **bureaus externos** | ✅ Sim | Ver "Dependência de score de terceiros" abaixo |
| Renda, crédito, parcela, emprego, moradia, ocupação | Dados financeiros e profissionais | ✅ Sim | Necessários à finalidade (avaliação de risco) |

Nenhuma coluna do recorte é **dado pessoal sensível** no sentido do art. 5º, II (origem
racial, saúde, religião, biometria etc.). Gênero e estado civil não estão nessa lista,
mas o **princípio da não discriminação** (art. 6º, IX) justifica tirá-los do modelo.

**Dependência de score de terceiros.** `EXT_SOURCE_*` são os preditores mais fortes do
dataset, e são scores de fontes externas cuja composição não é conhecida. Isso tem dois
custos de governança: o compartilhamento com bureaus precisa de base legal própria
(proteção do crédito, art. 7º, X), e a explicação da decisão ao titular (art. 20, §1º)
fica limitada — o modelo herda a opacidade do score de terceiro. A ablação da Etapa 1
mede quanto do desempenho depende deles.

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
| Necessidade (minimização) | ~20 de 122 colunas ingeridas; dados de contato descartados; gênero e estado civil fora do modelo; o contrato rejeita colunas fora do esquema |
| Finalidade | Dados de produção usados só para scoring e monitoramento; nenhum uso secundário |
| Qualidade dos dados | O contrato de dados **é** a implementação deste princípio |
| Segurança | Dados brutos fora do Git (`.gitignore`, e as regras da competição proíbem redistribuir); relatórios versionados não contêm linhas individuais |
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
> de gênero, faixa de idade, escolaridade, estado civil e nota da região; razão de impacto
> desigual (regra dos 4/5); e o resultado da ablação de idade, escolaridade, composição
> familiar e `EXT_SOURCE_*`.

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
