# 🏗️ Decisões de Arquitetura

> Escolhas de ferramenta e de desenho, com alternativas descartadas e o motivo. Visão
> resumida no [README.md](../README.md#%EF%B8%8F-arquitetura).

---

## 🎯 Objetivo

Construir a camada de **sustentação** de um modelo de crédito: o que impede dados ruins
de entrar, o que percebe quando o mundo muda e o que deixa tudo isso visível e auditável.
O modelo em si é deliberadamente simples.

---

## ⚖️ Decisão 1 — Execução em lote, não serviço online

| Critério | Pipeline em lote | API online |
|----------|-----------------|------------|
| Aderência ao enunciado | ✅ Lotes de produção × referência | ⚠️ Exigiria acumular janelas |
| Detecção de drift | ✅ Natural: compara distribuições de um lote | ⚠️ Precisa de janela deslizante |
| Reprodutibilidade para o avaliador | ✅ Um comando, sem serviço rodando | ⚠️ Subir API + gerar carga |
| Realismo em crédito | ✅ Monitoramento de carteira é tipicamente mensal | ✅ Decisão é online |

**Decisão: pipeline em lote, um lote por "mês".** A decisão de crédito pode ser online, mas
o **monitoramento** de carteira acontece em janelas. A API já foi entregue na Fase 3; o que
esta fase avalia é a camada em volta dela.

---

## 🛡️ Decisão 2 — Pandera para contratos de dados

| Critério | Pandera | Great Expectations |
|----------|---------|--------------------|
| Forma do contrato | Schema em Python, versionado com o código | Suítes + contexto + checkpoints em arquivos de configuração |
| Testabilidade | ✅ Schema é objeto Python; teste com pytest direto | ⚠️ Exige montar o contexto |
| Peso da dependência | ✅ Leve | ⚠️ Pesada |
| Coleta de todas as falhas | ✅ `lazy=True` | ✅ |
| Relatório HTML nativo | ❌ Gerado por nós | ✅ Data Docs |
| Estabilidade da API | 🟡 Mudou o import recomendado em versões recentes | 🔴 Reescrita grande na 1.0 |

**Decisão: Pandera.** O contrato é código: revisado em PR, testado com pytest e chamado
pelas mesmas funções no notebook, no script e no CI. O que se perde é o Data Docs; o
relatório de validação em HTML é gerado pelo projeto a partir das falhas coletadas. 🟡
Proposta.

---

## 📉 Decisão 3 — Evidently com PSI e KS explícitos

**Decisão: Evidently AI, com `stattest` configurado por coluna.** É a biblioteca indicada
no enunciado e gera o HTML exigido. O padrão dela para amostras > 1.000 é
Wasserstein/Jensen-Shannon; o enunciado pede PSI/KS, então a configuração é explícita. PSI
decide o alerta, KS confirma (ver [DRIFT.md](DRIFT.md#-testes-estatísticos)). 🟡 Proposta.

> ⚠️ A API do Evidently mudou de forma incompatível entre versões recentes (presets,
> imports, formato do snapshot). A versão fica travada no `uv.lock` e anotada no
> [CLAUDE.md](../CLAUDE.md); exemplos da internet para outra versão não servem.

---

## 🤖 Decisão 4 — Modelo simples, escolhido por comparação

O enunciado pede *"um modelo de classificação simples"*. Mesmo assim, a escolha segue o
padrão dos TCs anteriores: candidatos no **mesmo split**, critério declarado antes do
treino.

| Candidato | Papel |
|-----------|-------|
| `DummyClassifier` | Piso |
| `LogisticRegression` | Linear, interpretável — útil para o art. 20 da LGPD |
| `XGBClassifier` | Árvores; lida nativamente com nulos de `EXT_SOURCE_3` e com não linearidades de idade e emprego |

**Critério proposto:** maior AUC-ROC no teste entre os modelos com AUC ≥ 0,72 e acima do
Dummy. Empate técnico (Δ < 0,01) desempata pela interpretabilidade. 🟡 Revisar após EDA —
na tabela principal do Home Credit, sem as tabelas relacionais, AUCs na faixa de 0,72–0,76
são o esperado. Acurácia não entra: o Dummy acerta ~92%.

---

## 📈 Decisão 5 — MLflow + dashboard estático para a Etapa 3

| Opção | Visual | Custo de subir | O avaliador vê sem rodar? |
|-------|--------|----------------|---------------------------|
| **MLflow local (SQLite)** | ✅ Séries por execução | ✅ `uv run mlflow ui` | ❌ |
| **Dashboard HTML estático** | ✅ | ✅ Nenhum | ✅ |
| Prometheus + Grafana | ✅ | ⚠️ Docker Compose | ❌ |
| Datadog / cloud nativo | ✅ | 🔴 Conta e credenciais | ❌ |

**Decisão: MLflow como rastreamento + dashboard HTML consolidado e versionado.** O MLflow
atende literalmente à Etapa 3 sem infraestrutura. O dashboard estático é o seguro contra
a falha do TC01: se nada rodar na máquina do avaliador, a evidência está no repositório.
Prometheus/Grafana ficam como opcional, reaproveitando a Fase 3. 🟡 Proposta.

---

## 🔒 Decisão 6 — Bloquear o lote inteiro

Lote com violação crítica vai inteiro para quarentena; não há filtragem de linhas. Filtrar
esconderia o problema de origem e alteraria a distribuição do lote, contaminando a
detecção de drift seguinte. Ver [DATA_CONTRACTS.md](DATA_CONTRACTS.md#-comportamento-de-bloqueio).
🟡 Proposta.

---

## 📌 Registro de Decisões (ADR resumido)

| # | Decisão | Status | Motivo principal |
|---|---------|--------|------------------|
| 01 | Pipeline em lote mensal | 🟡 Proposta | Monitoramento de carteira é por janela; reproduzível com um comando |
| 02 | Pandera para contratos | 🟡 Proposta | Contrato como código, testável com pytest, dependência leve |
| 03 | Evidently com PSI (decisão) + KS (confirmação) explícitos | 🟡 Proposta | Exigência do enunciado; padrão do Evidently não é PSI/KS |
| 04 | Dummy · LogReg · XGBoost no mesmo split | 🟡 Proposta | Escolha por evidência, não por preferência |
| 05 | MLflow + dashboard HTML versionado | 🟡 Proposta | Etapa 3 sem infraestrutura; evidência visível sem rodar |
| 06 | Lote inválido bloqueado por inteiro | 🟡 Proposta | Não mascarar falha de origem nem distorcer o drift |
| 07 | Split referência × produção único, 50/50, estratificado | 🟡 Proposta | Separação exigida; M01 de controle mede falso positivo |
| 08 | `CODE_GENDER` e `NAME_FAMILY_STATUS` fora das features; dados de contato descartados | 🟡 Proposta | LGPD art. 6º, III (necessidade) e IX (não discriminação) |
| 09 | Dataset Home Credit Default Risk, só `application_train.csv`, ~20 colunas | ✅ Aceita | Cenário de concessão; renda e emprego; anomalias reais para o contrato; atributos para auditoria. Custo: login no Kaggle, mitigado com fallback sintético. Comparativo em [DATASET.md](DATASET.md#%EF%B8%8F-candidatos-avaliados) |
| 10 | `uv run` como único runner documentado | ✅ Aceita | Lição do TC01: comandos que dependem de ferramenta não versionada falham |
| 11 | Contrato valida colunas brutas; features derivadas depois | 🟡 Proposta | Regras de origem (sentinela, `XNA`) só são visíveis no dado bruto |

---

**Última atualização:** 2026-11-07
