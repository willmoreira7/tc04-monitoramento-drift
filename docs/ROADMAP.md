# 🗺️ Roadmap

> Detalhamento das etapas do projeto, com tarefas, entregáveis e critérios de aceite.
> Visão resumida no [README.md](../README.md).

---

## 📊 Panorama

| Etapa | Disciplina | Peso relacionado | Status |
|-------|-----------|------------------|--------|
| [0 — Fundação](#-etapa-0--fundação-do-repositório) | — | — | 🟡 Em andamento |
| [1 — Validação de Dados](#-etapa-1--validação-de-dados-e-contratos) | Validação de Dados e Bibliotecas de Qualidade | 25% | ⬜ Não iniciada |
| [2 — Drift](#-etapa-2--simulação-e-detecção-de-drift) | Data Drift | 25% | ⬜ Não iniciada |
| [3 — Observabilidade](#-etapa-3--observabilidade-de-pipelines-e-modelos) | Monitoramento de Pipelines e Infraestrutura | 20% | ⬜ Não iniciada |
| [4 — Governança e Entrega](#%EF%B8%8F-etapa-4--governança-causalidade-e-entrega) | Privacy by Design e by Default | 15% + 15% (vídeo) | ⬜ Não iniciada |

**Legenda:** ⬜ não iniciada · 🟡 em andamento · ✅ concluída · 🔴 bloqueada

---

## ✅ Conformidade com o Enunciado

Conferência item a item do que o enunciado exige. **Atualizar ao fechar cada etapa.**

### Requisitos obrigatórios — repositório

| Requisito | Status | Onde |
|-----------|--------|------|
| Pipeline de validação de dados (data contracts) configurado | ⬜ | Etapa 1 — `src/contracts/` |
| Scripts para simulação e detecção estatística de drift | ⬜ | Etapa 2 — `src/drift/` |
| Dashboards ou relatórios HTML comprovando o monitoramento | ⬜ | Etapas 2 e 3 — `reports/` (versionado) |
| Documentação consolidada de Governança no README.md | 🟡 | [README — Governança](../README.md#%EF%B8%8F-governança-e-lgpd) (estrutura pronta, vieses pendentes) |
| Histórico de commits semântico e organizado | 🟡 | [COMMITLINT.md](COMMITLINT.md) — configurado na Etapa 0 |

### Bibliotecas requeridas

| Biblioteca | Uso exigido | Status |
|-----------|-------------|--------|
| Scikit-Learn / XGBoost | Modelo base de risco de crédito | ⬜ Etapa 1 |
| Great Expectations **ou** Pandera | Data contracts | ⬜ Pandera — Etapa 1 |
| Evidently AI (ou Alibi Detect) | Data/Concept Drift + relatórios | ⬜ Etapa 2 |
| Prometheus-client | Opcional (integração com a Fase 3) | ⚪ Avaliar na Etapa 3 |

### Boas práticas obrigatórias

| Prática | Exigência | Status |
|---------|-----------|--------|
| Separação referência × produção | Dataset de treino distinto do de análise | ⬜ Split 50/50 + teste anti-vazamento |
| Regras rígidas de qualidade | ≥ 3 regras | ⬜ 8 regras críticas previstas em [DATA_CONTRACTS.md](DATA_CONTRACTS.md) |
| Relatório estatístico de mudança de distribuição | PSI ou KS | ⬜ PSI + KS configurados explicitamente |
| Documentação de compliance | Plano de privacidade LGPD | 🟡 No README |

### Dataset

| Exigência | Situação |
|-----------|----------|
| Classificação binária financeira | ✅ Inadimplência no mês seguinte |
| Mínimo de 5.000 amostras | ✅ 30.000 (UCI Default of Credit Card Clients) |
| Público, tabular, risco de crédito | ✅ UCI, sem necessidade de conta |

### Vídeo (≤ 5 min, STAR)

| Bloco | Conteúdo exigido | Status |
|-------|-----------------|--------|
| Situation | Risco da degradação silenciosa em crédito | ⬜ |
| Task | Interceptar dados ruins, detectar drift, garantir compliance | ⬜ |
| Action | Ferramentas de validação e observabilidade, simulação, governança | ⬜ |
| Result | Relatório apontando o drift, alertas gerados, lições aprendidas | ⬜ |

---

## 🧱 Etapa 0 — Fundação do Repositório

**Foco:** deixar o repositório pronto para codar sem retrabalho, com as regras que evitam
os problemas dos Tech Challenges anteriores.

### Tarefas

- [x] Inicializar repositório e conectar ao remoto
- [x] Analisar o enunciado e as avaliações dos TCs anteriores ([.claude/rules/entrega.md](../.claude/rules/entrega.md))
- [x] Escrever regras do projeto ([CLAUDE.md](../CLAUDE.md), [.claude/rules/](../.claude/rules/))
- [x] Documentar contexto, arquitetura, roadmap, dataset, contrato, drift e monitoramento
- [x] Estruturar a seção de Governança LGPD no README
- [x] Definir padrão de commits ([COMMITLINT.md](COMMITLINT.md))
- [ ] **Confirmar o dataset** ([DATASET.md](DATASET.md)) — hoje 🟡 proposta
- [ ] Confirmar as decisões 🟡 **Proposta** de [ARQUITETURA.md](ARQUITETURA.md)
- [ ] Criar `pyproject.toml` com `uv`, ruff e grupos de dependência; commitar `uv.lock`
- [ ] Criar `scripts/verify_setup.py`
- [ ] Criar `scripts/download_data.py` (UCI, sem credencial) e o fallback sintético
- [ ] Criar a estrutura de diretórios descrita no README
- [ ] Criar o workflow de CI com lint e testes

### 🧰 Arquivos de tooling

| Item | Papel | Status |
|------|-------|--------|
| `commitlint.config.js`, `package.json`, `.husky/commit-msg` | Validação das mensagens de commit | ✅ |
| `.gitignore` | Dados e modelos fora do Git; `reports/` dentro | ✅ |
| `pyproject.toml` + `uv.lock` | Dependências travadas, ruff, pytest | ⬜ |
| `scripts/verify_setup.py` | Checagem de ambiente | ⬜ |
| `.github/workflows/ci.yml` | lint → testes → pipeline fim a fim | ⬜ |

### ✅ Critério de aceite

- Qualquer integrante clona, entende o escopo e sabe onde colocar o próprio código
- `uv sync --group dev && uv run python scripts/verify_setup.py` passa num clone limpo

---

## 🛡️ Etapa 1 — Validação de Dados e Contratos

**Disciplina:** Validação de Dados e Bibliotecas de Qualidade
**Foco:** garantir que lixo não entre no modelo.

### Tarefas

- [ ] Baixar o dataset e registrar o SHA256 do arquivo bruto
- [ ] EDA (`notebooks/01_eda.ipynb`): domínios reais, valores fora do dicionário, desbalanceamento
- [ ] Split único e estratificado referência × pool de produção (seed 42)
- [ ] Limpeza da referência (ex.: `EDUCATION` 0/5/6 → 4 "outros") — ver [DATASET.md](DATASET.md)
- [ ] Escrever o contrato Pandera com as regras de [DATA_CONTRACTS.md](DATA_CONTRACTS.md)
- [ ] Validar a referência contra o contrato **antes** do treino
- [ ] Treinar Dummy, LogisticRegression e XGBoost no mesmo split; promover pelo critério declarado
- [ ] Auditoria de viés e ablação de `AGE` / `EDUCATION` → decisão registrada em ADR
- [ ] Gerar lote corrompido e demonstrar o **bloqueio** (quarentena + exit code ≠ 0 + log)
- [ ] Relatório de validação em `reports/validation/`
- [ ] Preencher a primeira versão do [MODEL_CARD.md](MODEL_CARD.md)

### 📦 Entregável

Script de validação de dados operante + modelo baseline treinado.

### ✅ Critério de aceite

- [ ] Lote corrompido é rejeitado e **nenhuma predição** é gerada para ele
- [ ] Cada regra crítica tem teste com caso válido e inválido
- [ ] Teste automatizado prova que nenhuma linha do pool de produção está no treino
- [ ] Modelo promovido supera o Dummy e atende ao gate declarado
- [ ] Seção "Como Executar" do README atualizada e executada num clone limpo

---

## 📉 Etapa 2 — Simulação e Detecção de Drift

**Disciplina:** Data Drift
**Foco:** diagnosticar a degradação do modelo ao longo do tempo.

### Tarefas

- [ ] Declarar os cenários em `configs/drift_scenarios.yaml` (ver [DRIFT.md](DRIFT.md))
- [ ] Gerar os lotes M01…M06 a partir do pool de produção
- [ ] Passar cada lote pelo contrato e gerar predições
- [ ] Relatório Evidently por lote com **PSI e KS explícitos** por coluna
- [ ] Monitorar drift de predição (distribuição do score)
- [ ] Monitorar performance com rótulos (AUC, recall de inadimplentes) para captar concept drift
- [ ] Confirmar que M01 (controle) **não** acusa drift
- [ ] Ablação causal: cada perturbação isolada, impacto medido
- [ ] Notebook `notebooks/03_drift_analysis.ipynb` com a leitura dos resultados

### 📦 Entregável

Relatório de drift (HTML do Evidently) apontando claramente as variáveis degradadas.

### ✅ Critério de aceite

- [ ] ≥ 2 variáveis importantes com drift detectado nos lotes perturbados
- [ ] M01 sem drift (falso positivo = 0)
- [ ] Concept drift (M05) detectado pela performance mesmo sem drift nas features
- [ ] HTML de cada lote em `reports/drift/`, versionado

---

## 📈 Etapa 3 — Observabilidade de Pipelines e Modelos

**Disciplina:** Monitoramento de Pipelines e Infraestrutura
**Foco:** visibilidade operacional dos pipelines, da infraestrutura e do modelo.

### Tarefas

- [ ] Logs estruturados (JSON) de cada estágio: ingestão, validação, predição, drift
- [ ] Centralizar logs em `logs/pipeline.jsonl` e anexá-los às execuções do MLflow
- [ ] Registrar uma execução MLflow por lote com as métricas de [MONITORING.md](MONITORING.md)
- [ ] Regras de alerta (atenção / crítico) avaliadas a cada lote
- [ ] Dashboard consolidado em `reports/monitoring/dashboard.html`
- [ ] Documentar as métricas de saúde escolhidas e o playbook de resposta
- [ ] ⚪ Opcional: expor métricas com `prometheus-client` e reaproveitar o Grafana da Fase 3

### 📦 Entregável

Dashboard de monitoramento ou ambiente de rastreamento evidenciando a saúde do pipeline,
a estabilidade da infraestrutura e os alertas de degradação do modelo.

### ✅ Critério de aceite

- [ ] Dashboard mostra, por lote: status de cada estágio, volume, latência, alertas de drift e performance
- [ ] O lote corrompido aparece como falha de ingestão no dashboard
- [ ] `uv run mlflow ui` lista as execuções com métricas e artefatos

---

## ⚖️ Etapa 4 — Governança, Causalidade e Entrega

**Disciplina:** Privacy by Design e by Default
**Foco:** documentação arquitetural, compliance e prescrição.

### Tarefas

- [ ] Completar a seção de Governança no README com os números da auditoria de viés
- [ ] Escrever a Análise Causal no README com os resultados da ablação
- [ ] Revisar o Model Card final
- [ ] Atualizar a tabela de conformidade deste documento
- [ ] Executar o README completo num clone limpo (Windows **e** Linux/CI)
- [ ] Roteirizar, ensaiar (≤ 5 min cronometrados) e gravar o vídeo STAR
- [ ] Publicar o link do vídeo no README

### 📦 Entregável

Documentação completa de Governança e Causalidade no README + link do vídeo.

### ✅ Critério de aceite

- [ ] Nenhum placeholder 🟡 restante no README e no Model Card
- [ ] `git ls-files docs/MODEL_CARD.md reports/` lista os entregáveis
- [ ] Vídeo ≤ 5:00

---

## 🚩 Riscos e Pontos de Atenção

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Avaliador não consegue rodar o projeto (TC01) | 🔴 Alto | Só `uv run`; README executado em clone limpo a cada etapa; evidências versionadas |
| Model Card ausente do repositório (TC02) | 🟡 Médio | Mora em `docs/`; checado com `git ls-files` |
| KS com n grande acusa drift em diferenças irrelevantes | 🟡 Médio | PSI como decisão, KS como confirmação + estatística D; M01 de controle mede falso positivo |
| Stattest padrão do Evidently não é PSI/KS | 🟡 Médio | Configurar `stattest` por coluna explicitamente |
| API do Evidently/Pandera mudou entre versões | 🟡 Médio | Versão travada no `uv.lock` e anotada no CLAUDE.md |
| Fonte do dataset (UCI) fora do ar no CI | 🟡 Médio | Cache no CI + fallback sintético documentado |
| Relatórios HTML vazarem linhas individuais | 🟡 Médio | Só agregados; revisão antes de commitar `reports/` |
| Drift simulado parecer arbitrário | 🟡 Médio | Cada cenário tem narrativa econômica e mecanismo declarado em [DRIFT.md](DRIFT.md) |
| Vídeo estourar 5 minutos | 🟡 Médio | Roteiro com tempos + ensaio cronometrado |

---

**Última atualização:** 2026-11-07
