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
pelas mesmas funções no notebook, no script e no CI. ✅ Aceita (Etapa 1).

**Como ficou na implementação:**

- O schema é montado a partir de `configs/pipeline.yaml` ([`src/contracts/schema.py`](../src/contracts/schema.py)).
  Cada coluna carrega o identificador da regra (C4…C8), e as falhas estruturais do Pandera
  (`column_in_schema`, `not_nullable`, `field_uniqueness`, `dtype`) são mapeadas para C1–C3.
  Assim cada falha chega ao relatório com a regra de [DATA_CONTRACTS.md](DATA_CONTRACTS.md).
- **O que se perdeu:** o Data Docs. Em troca, o relatório é um **JSON agregado** por lote
  em `reports/validation/` (regra, coluna, nº de casos e até 3 valores de exemplo, nunca
  linhas inteiras). A proposta original previa HTML; o JSON foi escolhido porque é
  determinístico (diff limpo no Git) e é a entrada natural do dashboard da Etapa 3, que
  fará a visualização.
- O parâmetro `name=` das checks do Pandera **não** aparece em `failure_cases`. Por isso o
  mapeamento falha → regra vive no próprio contrato, não no nome da check.

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

## 🤖 Decisão 4 — Comparação enxuta de modelos

O enunciado pede *"um modelo de classificação simples"* e **nenhum critério de avaliação
premia o desempenho do modelo**: 70% da nota está em validação de dados, drift e
observabilidade, e o modelo é o **objeto monitorado**, não o entregável. Nos TCs
anteriores a modelagem era critério, e por isso a comparação ampla valia nota. Aqui não.

**Decisão: comparação enxuta, deliberadamente.** Três candidatos, parâmetros padrão, um
script, uma tabela no Model Card.

| Candidato | Papel |
|-----------|-------|
| `DummyClassifier` (estratificado) | Piso: sem ele, um AUC isolado não diz nada |
| `LogisticRegression` | Linear e interpretável: coeficientes explicáveis ao titular (LGPD art. 20) |
| `XGBClassifier` (padrão) | Biblioteca citada no enunciado; mede quanto se ganha abrindo mão de explicabilidade |

**Descartado de propósito** (não é falta de tempo, é foco):

| Item | Por que não |
|------|-------------|
| Busca de hiperparâmetros | Ganho de AUC não pontua; custo de tempo sai das etapas que pontuam |
| Um notebook por modelo | O registro da escolha cabe numa tabela versionada |
| Validação cruzada extensa | O split único estratificado basta para comparar 3 candidatos |
| Mais candidatos (RF, MLP…) | Não mudam a conclusão de governança nem a de drift |

**Critério de promoção** (declarado antes do treino, avaliado na **validação** — o teste
fica intocado para reportar o resultado):

1. AUC-ROC ≥ 0,70 e acima do Dummy
2. Maior AUC-ROC entre os elegíveis
3. Empate técnico (Δ AUC < 0,01) → o mais interpretável (`LogisticRegression`)

O limiar de decisão é escolhido na validação pelo **máximo KS** (ponto de maior separação
entre bons e maus, padrão em crédito) e fica fixo: é ele que define recall e taxa de
aprovação nos lotes de produção.

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
✅ Aceita (Etapa 1): implementado em [`src/pipeline/validate.py`](../src/pipeline/validate.py);
o script sai com exit code 2 e o lote fica em `data/quarantine/<batch_id>/`.

---

## 📌 Registro de Decisões (ADR resumido)

| # | Decisão | Status | Motivo principal |
|---|---------|--------|------------------|
| 01 | Pipeline em lote mensal | 🟡 Proposta | Monitoramento de carteira é por janela; reproduzível com um comando |
| 02 | Pandera para contratos; relatório JSON agregado | ✅ Aceita | Contrato como código, testável com pytest, dependência leve; JSON determinístico alimenta o dashboard |
| 03 | Evidently com PSI (decisão) + KS (confirmação) explícitos | 🟡 Proposta | Exigência do enunciado; padrão do Evidently não é PSI/KS |
| 04 | Comparação enxuta: Dummy · LogReg · XGBoost padrão, sem busca de hiperparâmetros | ✅ Aceita | Modelo é o objeto monitorado, não critério de nota; escolha por evidência mínima e argumento de explicabilidade (LGPD art. 20) |
| 05 | MLflow + dashboard HTML versionado | 🟡 Proposta | Etapa 3 sem infraestrutura; evidência visível sem rodar |
| 06 | Lote inválido bloqueado por inteiro | ✅ Aceita | Não mascarar falha de origem nem distorcer o drift |
| 07 | Split referência × produção único, 50/50, estratificado | 🟡 Proposta | Separação exigida; M01 de controle mede falso positivo |
| 08 | `SEX` e `MARRIAGE` fora das features | 🟡 Proposta | LGPD art. 6º, III (necessidade) e IX (não discriminação) |
| 09 | Dataset UCI Default of Credit Card Clients | ✅ Aceita | Licença CC BY 4.0 compatível com uso acadêmico e com a simulação de drift; ≥ 5.000 linhas; download sem conta; atributos para auditoria de viés. Home Credit descartado pelos termos de uso (ADR 12) |
| 10 | `uv run` como único runner documentado | ✅ Aceita | Lição do TC01: comandos que dependem de ferramenta não versionada falham |
| 11 | Contrato valida colunas brutas; features derivadas depois | ✅ Aceita | Regras de origem (códigos fora do dicionário) só são visíveis no dado bruto |
| 12 | Termos de uso verificados antes de adotar qualquer dataset; Home Credit descartado | ✅ Aceita | As regras da competição limitam o uso "only for the purposes of the Competition" e proíbem manipular os dados. Ver [README — Origem dos dados](../README.md#1-origem-dos-dados-e-termos-de-uso) e [DATASET.md](DATASET.md#-por-que-não-o-home-credit) |

---

**Última atualização:** 2026-11-10
