# 🗺️ Roadmap

> Detalhamento das etapas do projeto, com tarefas, entregáveis e critérios de aceite.
> Visão resumida no [README.md](../README.md).

---

## 📊 Panorama

| Etapa | Disciplina | Peso relacionado | Status |
|-------|-----------|------------------|--------|
| [0 — Fundação](#-etapa-0--fundação-do-repositório) | — | — | ✅ Concluída |
| [1 — Validação de Dados](#-etapa-1--validação-de-dados-e-contratos) | Validação de Dados e Bibliotecas de Qualidade | 25% | ✅ Concluída |
| [2 — Drift](#-etapa-2--simulação-e-detecção-de-drift) | Data Drift | 25% | ✅ Concluída |
| [3 — Observabilidade](#-etapa-3--observabilidade-de-pipelines-e-modelos) | Monitoramento de Pipelines e Infraestrutura | 20% | ✅ Concluída |
| [4 — Governança e Entrega](#%EF%B8%8F-etapa-4--governança-causalidade-e-entrega) | Privacy by Design e by Default | 15% + 15% (vídeo) | 🟡 Em andamento |

**Legenda:** ⬜ não iniciada · 🟡 em andamento · ✅ concluída · 🔴 bloqueada

---

## ✅ Conformidade com o Enunciado

Conferência item a item do que o enunciado exige. **Atualizar ao fechar cada etapa.**

### Requisitos obrigatórios — repositório

| Requisito | Status | Onde |
|-----------|--------|------|
| Pipeline de validação de dados (data contracts) configurado | ✅ | Etapa 1 — [`src/contracts/`](../src/contracts/), relatórios em [`reports/validation/`](../reports/validation/) |
| Scripts para simulação e detecção estatística de drift | ✅ | [`src/drift/`](../src/drift/) e [`scripts/run_drift_simulation.py`](../scripts/run_drift_simulation.py) |
| Dashboards ou relatórios HTML comprovando o monitoramento | ✅ | HTML do Evidently por lote em [`reports/drift/`](../reports/drift/) e [`reports/monitoring/dashboard.html`](../reports/monitoring/dashboard.html) com o contrato e os lotes M01…M06 |
| Documentação consolidada de Governança no README.md | ✅ | [README — Governança](../README.md#%EF%B8%8F-governança-e-lgpd): plano, bases legais, retenção proposta e limites de implementação explícitos |
| Histórico de commits semântico e organizado | ✅ | [COMMITLINT.md](COMMITLINT.md) — commitlint no CI em todo PR; merge por squash com mensagem semântica |

### Bibliotecas requeridas

| Biblioteca | Uso exigido | Status |
|-----------|-------------|--------|
| Scikit-Learn / XGBoost | Modelo base de risco de crédito | ✅ Dummy · LogReg · XGBoost (promovido) |
| Great Expectations **ou** Pandera | Data contracts | ✅ Pandera — [`src/contracts/`](../src/contracts/) |
| Evidently AI (ou Alibi Detect) | Data/Concept Drift + relatórios | ✅ `ValueDrift` com PSI e KS por coluna — [`src/drift/detect.py`](../src/drift/detect.py) |
| Prometheus-client | Opcional (integração com a Fase 3) | ✅ Pushgateway + Grafana da Fase 3 — [MONITORING.md](MONITORING.md#-grafana-e-prometheus-opcional) |

### Boas práticas obrigatórias

| Prática | Exigência | Status |
|---------|-----------|--------|
| Separação referência × produção | Dataset de treino distinto do de análise | ✅ Split 50/50 + testes anti-vazamento por `ID` e por conteúdo |
| Regras rígidas de qualidade | ≥ 3 regras | ✅ 8 regras críticas (C1–C8) + 4 avisos; lote corrompido bloqueado — [DATA_CONTRACTS.md](DATA_CONTRACTS.md) |
| Relatório estatístico de mudança de distribuição | PSI ou KS | ✅ PSI + KS configurados explicitamente — [DRIFT.md](DRIFT.md#-resultados) |
| Documentação de compliance | Plano de privacidade LGPD | ✅ Plano no README; não equivale a certificação de conformidade ou operação real |

### Dataset

| Exigência | Situação |
|-----------|----------|
| Classificação binária financeira | ✅ Inadimplência no mês seguinte |
| Mínimo de 5.000 amostras | ✅ 30.000 (UCI Default of Credit Card Clients) |
| Público, tabular, risco de crédito | ✅ UCI, sem necessidade de conta; licença CC BY 4.0 verificada |

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
- [x] **Escolher o dataset** ([DATASET.md](DATASET.md)) — UCI 350, após descartar o Home Credit pelos termos de uso
- [x] Verificar a licença e registrar o SHA256 do arquivo bruto
- [x] Regra: cada decisão 🟡 **Proposta** de [ARQUITETURA.md](ARQUITETURA.md) é confirmada na etapa que a implementa
- [x] Criar `pyproject.toml` com `uv`, ruff e grupos de dependência; commitar `uv.lock`
- [x] Criar `scripts/verify_setup.py`
- [x] Criar `scripts/download_data.py` (UCI `data.csv`, sem credencial, com conferência do SHA256) e o fallback sintético
- [x] Criar a estrutura de diretórios descrita no README
- [x] Criar o workflow de CI (lint, testes, dataset real, commitlint)
- [x] Executar o "Como Executar" do README num clone limpo

### 🧰 Arquivos de tooling

| Item | Papel | Status |
|------|-------|--------|
| `commitlint.config.js`, `package.json`, `.husky/commit-msg` | Validação das mensagens de commit | ✅ |
| `.gitignore` | Dados e modelos fora do Git; `reports/` dentro | ✅ |
| `pyproject.toml` + `uv.lock` | Dependências travadas, ruff, pytest | ✅ |
| `.gitattributes` | Finais de linha LF no repositório | ✅ |
| `scripts/download_data.py` | Dataset real (SHA256) ou sintético | ✅ |
| `scripts/verify_setup.py` | Checagem de ambiente | ✅ |
| `.github/workflows/ci.yml` | lint → testes · dataset real · commitlint (pipeline fim a fim nas próximas etapas) | ✅ |

### ✅ Critério de aceite

- Qualquer integrante clona, entende o escopo e sabe onde colocar o próprio código
- ✅ `uv sync --group dev && uv run python scripts/verify_setup.py` passa num clone limpo (verificado em 2026-11-07, Windows; Linux pelo CI)

---

## 🛡️ Etapa 1 — Validação de Dados e Contratos

**Disciplina:** Validação de Dados e Bibliotecas de Qualidade
**Foco:** garantir que lixo não entre no modelo.

### Tarefas

- [x] Investigar as 35 linhas idênticas com IDs diferentes (duplicata ou coincidência)
- [x] EDA (`notebooks/01_eda.ipynb`): domínios reais, valores fora do dicionário, desbalanceamento
- [x] Split único e estratificado referência × pool de produção (seed 42)
- [x] Limpeza da referência: `EDUCATION` 0/5/6 → 4, `MARRIAGE` 0 → 3, 35 perfis duplicados removidos — ver [01_eda.ipynb](../notebooks/01_eda.ipynb)
- [x] Escrever o contrato Pandera com as regras de [DATA_CONTRACTS.md](DATA_CONTRACTS.md)
- [x] Validar a referência e o pool contra o contrato **antes** de gravá-los (sem eles o treino não roda)
- [x] Treinar Dummy, LogisticRegression e XGBoost no mesmo split; promover pelo critério declarado (XGBoost — ver [MODEL_CARD.md](MODEL_CARD.md))
- [x] Auditoria de viés e ablação de `AGE` / `EDUCATION` → ambos removidos (ADR 13); nenhum grupo abaixo de 4/5
- [x] Gerar lote corrompido e demonstrar o **bloqueio** (quarentena + exit code 2 + log `status=blocked` + alerta crítico)
- [x] Relatório de validação em `reports/validation/` (JSON agregado, versionado — ADR 02)
- [x] Preencher o [MODEL_CARD.md](MODEL_CARD.md): performance, comparação, ablação e viés (drift fica na Etapa 2)

### 📦 Entregável

Script de validação de dados operante + modelo baseline treinado.

### ✅ Critério de aceite

- [x] Lote corrompido é rejeitado e vai para quarentena · "nenhuma predição" provado por teste na Etapa 2 (`test_blocked_batch_never_reaches_the_model`)
- [x] Cada regra crítica tem teste com caso válido e inválido (incluindo tipos malformados e lote vazio, cobrindo C1–C8)
- [x] Teste automatizado prova que nenhuma linha do pool de produção está no treino (por `ID` e por conteúdo)
- [x] Modelo promovido supera o Dummy e atende ao gate declarado (AUC val. 0,7622 ≥ 0,70)
- [x] Seção "Como Executar" do README atualizada e executada num clone limpo

---

## 📉 Etapa 2 — Simulação e Detecção de Drift

**Disciplina:** Data Drift
**Foco:** diagnosticar a degradação do modelo ao longo do tempo.

### Tarefas

- [x] Declarar os cenários em `configs/drift_scenarios.yaml` (ver [DRIFT.md](DRIFT.md)), calibrados no dado real (ADR 14)
- [x] Gerar os lotes M01…M06 a partir do pool de produção
- [x] Passar cada lote pelo contrato e gerar predições
- [x] Relatório Evidently por lote com **PSI e KS explícitos** por coluna
- [x] Monitorar drift de predição (distribuição do score)
- [x] Monitorar performance com rótulos (AUC, recall de inadimplentes) para captar concept drift
- [x] Confirmar que M01 (controle) **não** acusa drift (maior PSI: 0,011)
- [x] Ablação causal: cada perturbação isolada, impacto medido; interações M04/M06 explicitadas
- [x] Notebook `notebooks/03_drift_analysis.ipynb` com a leitura dos resultados versionados

### 📦 Entregável

Relatório de drift (HTML do Evidently) apontando claramente as variáveis degradadas.

### ✅ Critério de aceite

- [x] ≥ 2 variáveis importantes com drift detectado nos lotes perturbados (`LIMIT_BAL` e `PAY_0` no M04 e no M06)
- [x] M01 sem alerta nesta execução; não estima taxa de falso positivo em novas amostras
- [x] Concept drift (M05) detectado pela performance mesmo sem drift nas features (AUC −0,067)
- [x] HTML de cada lote em `reports/drift/`, versionado
- ⚠️ M06 não disparou o alerta de performance que o desenho previa: a mudança de população esconde o concept drift. Expectativa revista para o medido, hipótese original registrada, cenário não recalibrado ([DRIFT.md](DRIFT.md#-resultados))
- [x] Teste exige que a evidência real versionada cumpra a expectativa de cada lote

> ✅ **Etapa 2 concluída.** Ablação, notebook, relatório agregado e análise causal estão
> versionados; os resultados são reproduzidos no CI com dataset real.

---

## 📈 Etapa 3 — Observabilidade de Pipelines e Modelos

**Disciplina:** Monitoramento de Pipelines e Infraestrutura
**Foco:** visibilidade operacional dos pipelines, da infraestrutura e do modelo.

### Tarefas

- [x] Logs estruturados (JSON) centralizados em `logs/pipeline.jsonl`: todo evento de todo script, pelo próprio structlog
- [x] Eventos de cada lote anexados à execução do MLflow (`logs/pipeline.jsonl` nos artefatos)
- [x] Uma execução MLflow por lote — aprovado, bloqueado ou com falha — com as métricas de pipeline e infraestrutura de [MONITORING.md](MONITORING.md)
- [x] Regras de alerta (atenção / crítico) avaliadas a cada lote: bloqueio, falha de estágio, volume, PSI, PSI do score, queda de AUC
- [x] Gerador do dashboard consolidado (`reports/monitoring/dashboard.html`): status e latência por estágio, volume, memória, alertas
- [x] Documentar as métricas de saúde escolhidas e o playbook de resposta
- [x] Estágios de predição, drift e performance no fluxo monitorado (lotes M01…M06)
- [x] Dashboard versionado com os lotes de demonstração do contrato (dataset real)
- [x] Regenerar o dashboard com os lotes M01…M06
- [x] ⚪ Opcional: métricas do lote enviadas ao Pushgateway (`TC04_PUSHGATEWAY_URL`) e dashboard do Grafana versionado em `monitoring/grafana/`

### 📦 Entregável

Dashboard de monitoramento ou ambiente de rastreamento evidenciando a saúde do pipeline,
a estabilidade da infraestrutura e os alertas de degradação do modelo.

### ✅ Critério de aceite

- [x] Dashboard versionado mostra, por lote: status de cada estágio, volume, latência, alertas de drift e performance
- [x] O lote corrompido aparece no dashboard como bloqueado na validação (exit 2), não como sucesso
- [x] MLflow compartilhado serve como ambiente de rastreamento opcional; link publicado no README. Nenhum print é exigido pelo enunciado

---

## ⚖️ Etapa 4 — Governança, Causalidade e Entrega

**Disciplina:** Privacy by Design e by Default
**Foco:** documentação arquitetural, compliance e prescrição.

### Tarefas

- [x] Completar a seção de Governança no README com os números da auditoria de viés (Etapa 1, ADR 13)
- [x] Escrever a Análise Causal no README com os resultados da ablação
- [x] Revisar o Model Card final com resultados de drift e limitações
- [x] Atualizar a tabela de conformidade deste documento
- [x] Revisão de confiabilidade: tipos malformados e lote vazio bloqueados; relatórios sem
  exemplos individuais; identidade do modelo por lote; logs uniformes; governança e
  documentação alinhadas ao escopo entregue
- [ ] Responsáveis pelo laboratório confirmarem revogação/rotação das credenciais
  históricas (ação externa, não comprovada pelo repositório)
- [x] Executar comandos documentados em clone limpo Linux/CI; compatibilidade Windows não declarada
- [ ] Roteirizar, ensaiar (≤ 5 min cronometrados) e gravar o vídeo STAR
- [ ] Publicar o link do vídeo no README

### 📦 Entregável

Documentação completa de Governança e Causalidade no README + link do vídeo.

### ✅ Critério de aceite

- [x] Documentação distingue implementação, limitações e salvaguardas propostas; vídeo permanece pendente
- [x] `git ls-files docs/MODEL_CARD.md reports/` lista os entregáveis
- [ ] Vídeo ≤ 5:00

---

## 🚩 Riscos e Pontos de Atenção

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Avaliador não consegue rodar o projeto (TC01) | 🔴 Alto | Só `uv run`; README executado em clone limpo a cada etapa; evidências versionadas |
| Model Card ausente do repositório (TC02) | 🟡 Médio | Mora em `docs/`; checado com `git ls-files` |
| KS com n grande acusa drift em diferenças irrelevantes | 🟡 Médio | PSI como decisão, KS e estatística D informativos; M01 é controle de uma execução |
| Stattest padrão do Evidently não é PSI/KS | 🟡 Médio | Configurar `stattest` por coluna explicitamente |
| API do Evidently/Pandera mudou entre versões | 🟡 Médio | Versão travada no `uv.lock` e anotada no CLAUDE.md |
| Fonte do dataset (UCI) fora do ar no CI | 🟡 Médio | Cache no CI + fallback sintético documentado |
| Relatórios HTML vazarem linhas individuais | 🟡 Médio | Só agregados; revisão antes de commitar `reports/` |
| Drift simulado parecer arbitrário | 🟡 Médio | Cada cenário tem narrativa econômica e mecanismo declarado em [DRIFT.md](DRIFT.md) |
| Vídeo estourar 5 minutos | 🟡 Médio | Roteiro com tempos + ensaio cronometrado |

---

**Última atualização:** 2026-11-17
