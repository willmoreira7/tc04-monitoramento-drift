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
decide o alerta, KS confirma (ver [DRIFT.md](DRIFT.md#-testes-estatísticos)). ✅ Aceita
na Etapa 2: cada coluna recebe `ValueDrift(method="psi")` e `ValueDrift(method="ks")`
([`src/drift/detect.py`](../src/drift/detect.py)).

**Como ficou, com o que foi medido:**

- **Uma só implementação de PSI: a do Evidently.** Ela divide os dados em faixas de largura
  igual (regra de Sturges) sobre referência e lote juntos, e não em decis da referência,
  que é o padrão de mercado. Em colunas monetárias de cauda longa isso a deixa um pouco
  menos sensível: no lote com aperto de crédito, o PSI de `LIMIT_BAL` deu 0,18 contra 0,27
  pelos decis (sondagem antes da implementação). Manter uma segunda implementação só para
  ganhar sensibilidade violaria a regra de uma função de PSI no projeto, e o M01 mostrou
  que a do Evidently não gera falso positivo (maior PSI no controle: 0,011).
- **KS: o Evidently devolve só o p-valor.** A estatística D é calculada com
  `scipy.stats.ks_2samp` e registrada junto. No M02 (inflação de 10%), o KS rejeita H₀ em
  todas as `BILL_AMT*` (p < 0,02) com D entre 0,039 e 0,052 e PSI de no máximo 0,016:
  diferença real, irrelevante na prática. É por isso que o KS confirma e não decide.

**Descartado:** `DriftedColumnsCount` e os presets. A contagem de colunas com drift vem do
adaptador da Etapa 3 (`build_model_metrics`), com o limiar de `configs/pipeline.yaml`; ter
o Evidently contando de novo seria um segundo critério.

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

## 🧪 Decisão 13 — `AGE` e `EDUCATION` fora do modelo, por ablação

**Contexto.** `SEX` e `MARRIAGE` saíram por princípio (ADR 08). `AGE` e `EDUCATION` ficaram
em aberto: a idade é exigida pelo contrato (C4) e a escolaridade é proxy socioeconômico,
mas ambos podiam carregar sinal de risco.

**Critério, declarado antes de rodar** (commit `chore(config)` separado, anterior ao código
da ablação; `configs/pipeline.yaml`, seção `ablation`):

- Minimização (LGPD art. 6º, III): um atributo pessoal só fica se pagar por si.
- Remove-se o conjunto se a variante sem ele perder menos de 0,01 de AUC na validação,
  com o modelo promovido pelo próprio critério do ADR 04 em cada variante.
- Senão, cada atributo é avaliado sozinho com o mesmo limiar.

**Resultado** ([`reports/model/ablation.json`](../reports/model/ablation.json)):

| Variante | AUC val. (promovido: XGBoost em todas) | Perda |
|----------|----------------------------------------|-------|
| Com os dois | 0,7602 | — |
| Sem `AGE` | 0,7577 | 0,0025 |
| Sem `EDUCATION` | 0,7611 | −0,0009 |
| Sem os dois | 0,7622 | −0,0020 |

**Decisão: os dois saem.** ✅ Aceita. O modelo passa a usar só as 19 variáveis financeiras.
Os atributos continuam no lote: `AGE` para o contrato e ambos para a auditoria de viés.

**O que pesa contra, dito com franqueza:**

- **No teste, a remoção custou 0,011 de AUC** (0,7479 para 0,7368), no sentido oposto ao da
  validação. A regra decide na validação. A diferença está dentro do ruído de um split
  único, e reverter olhando o teste seria escolher pelo resultado.
- **Tirar `EDUCATION` não tirou a diferença por escolaridade.** Na validação, a razão de
  impacto por escolaridade foi de 0,87 para 0,82: limite de crédito e atraso recente
  carregam parte da informação. Por isso a auditoria mede o **resultado** por grupo, e a
  remoção de feature não é tratada como garantia de equidade (ver
  [Model Card](MODEL_CARD.md#️-vieses-e-equidade)).

**Descartado:** limiar de decisão diferente por grupo. Exigiria usar o atributo protegido
na própria decisão, e nenhum grupo ficou abaixo da regra dos 4/5.

---

## 🎲 Decisão 14 — Desenho da simulação de drift

**Contexto.** A especificação da Etapa 0 ([DRIFT.md](DRIFT.md)) previa seis lotes mensais
retirados do pool sem reposição, intensidades "a calibrar depois do baseline" e drift de
perfil por `AGE`. Três coisas mudaram com a medição no dado real.

**1. Mesmo sorteio em todos os lotes (números aleatórios comuns).** Cada lote é uma
amostra de 2.400 linhas do pool com a **mesma seed**; só os pesos e as perturbações do
cenário mudam. A primeira versão usava uma seed por lote e o M02 (só inflação) acusou
queda de AUC de 0,04, alerta de atenção sem nenhuma causa. Medido em 100 lotes uniformes
de 2.400 linhas: a AUC varia com desvio-padrão de 0,012, e 1% dos lotes passa do limiar de
atenção (0,03) por puro acaso. A amostra do M02 era desse 1%. Trocar a seed até o resultado
agradar seria escolher pelo resultado; com o mesmo sorteio, a diferença entre dois lotes
é causada **só** pelo que o cenário declara, que é o que a análise causal precisa. O M01
continua medindo o ruído que resta.

- **Custo:** M01, M02 e M05 contêm os mesmos clientes, o que não é realista como série
  mensal. Fica declarado; o objetivo é atribuir causa, não imitar uma carteira real.
- **Sem reposição dentro do lote; com sobreposição entre lotes.** O pool tem 14.983
  linhas e seis lotes somam 14.400: amostrar sem reposição entre lotes esgotaria os perfis
  favorecidos pela reamostragem antes do M06. O pool continua sem nunca tocar o treino.

**2. Janela de referência = validação + teste (4.495 linhas), não o treino.** O XGBoost
vê o treino e dá a ele scores otimistas: o PSI do score e a AUC de base só valem fora da
amostra. As features usam a mesma janela, para tudo ser comparado contra a mesma população.
AUC de base na janela: 0,7495.

**3. Drift nas features que o modelo usa.** Pela importância por permutação na validação,
`PAY_0` domina (0,094 de AUC), seguido de `BILL_AMT1`, `PAY_AMT1` e `LIMIT_BAL`. A idade
saiu do modelo (ADR 13), então o drift exigido pelo enunciado ("variáveis importantes") é
em `LIMIT_BAL` e `PAY_0`. A idade continua monitorada como atributo de população: mostra a
mudança de perfil, mas não entra na fração de features com drift.

**Calibração (antes de fixar os cenários, com o mesmo método de medição):**

- Peso 3 para `PAY_0 ≥ 2` deixa o PSI de `PAY_0` entre 0,09 e 0,14 em 40 sorteios, na
  fronteira da atenção; peso 4 dá entre 0,15 e 0,22. Ficou 4.
- Inflação de 10–25% nas faturas não chega a PSI 0,10. **Mantida**, em vez de exagerada
  até disparar: inflação plausível produz drift que o PSI corretamente considera pequeno, e
  o modelo quase não sente (AUC 0,7489 contra 0,7496 no controle).

**Resultado** ([`reports/drift/drift_summary.json`](../reports/drift/drift_summary.json)):
cinco dos seis lotes fizeram o que o desenho previa. O M06 (crise: aperto de crédito e
concept drift juntos) **não** disparou o alerta de performance previsto: a AUC agregada caiu
só 0,021. Não foi recalibrado para forçar o alerta; a expectativa do YAML foi revista para o
comportamento medido, com a hipótese original registrada no comentário, e o teste
`test_versioned_evidence_meets_every_declared_expectation` exige que a evidência versionada
cumpra todas as expectativas. A carteira da crise tem o dobro de atrasados, que o modelo ordena com
facilidade, e isso esconde a degradação causada pelo concept drift. Contra a mesma carteira
sem o concept drift (M04, AUC 0,793), a perda é de 0,064. É a principal lição da Etapa 2:
comparar a performance contra a linha de base agregada falha quando a população muda (ver
[DRIFT.md](DRIFT.md#-resultados)). ✅ Aceita.

---

## 📌 Registro de Decisões (ADR resumido)

| # | Decisão | Status | Motivo principal |
|---|---------|--------|------------------|
| 01 | Pipeline em lote mensal | 🟡 Proposta | Monitoramento de carteira é por janela; reproduzível com um comando |
| 02 | Pandera para contratos; relatório JSON agregado | ✅ Aceita | Contrato como código, testável com pytest, dependência leve; JSON determinístico alimenta o dashboard |
| 03 | Evidently com PSI (decisão) + KS (confirmação) explícitos | ✅ Aceita | Exigência do enunciado; padrão do Evidently não é PSI/KS. PSI só do Evidently (faixas de largura igual, documentado); D do KS pelo scipy |
| 04 | Comparação enxuta: Dummy · LogReg · XGBoost padrão, sem busca de hiperparâmetros | ✅ Aceita | Modelo é o objeto monitorado, não critério de nota; escolha por evidência mínima e argumento de explicabilidade (LGPD art. 20) |
| 05 | MLflow + dashboard HTML versionado | 🟡 Proposta | Etapa 3 sem infraestrutura; evidência visível sem rodar |
| 06 | Lote inválido bloqueado por inteiro | ✅ Aceita | Não mascarar falha de origem nem distorcer o drift |
| 07 | Split referência × produção único, 50/50, estratificado | 🟡 Proposta | Separação exigida; M01 de controle mede falso positivo |
| 08 | `SEX` e `MARRIAGE` fora das features | ✅ Aceita | LGPD art. 6º, III (necessidade) e IX (não discriminação) |
| 09 | Dataset UCI Default of Credit Card Clients | ✅ Aceita | Licença CC BY 4.0 compatível com uso acadêmico e com a simulação de drift; ≥ 5.000 linhas; download sem conta; atributos para auditoria de viés. Home Credit descartado pelos termos de uso (ADR 12) |
| 10 | `uv run` como único runner documentado | ✅ Aceita | Lição do TC01: comandos que dependem de ferramenta não versionada falham |
| 11 | Contrato valida colunas brutas; features derivadas depois | ✅ Aceita | Regras de origem (códigos fora do dicionário) só são visíveis no dado bruto |
| 12 | Termos de uso verificados antes de adotar qualquer dataset; Home Credit descartado | ✅ Aceita | As regras da competição limitam o uso "only for the purposes of the Competition" e proíbem manipular os dados. Ver [README — Origem dos dados](../README.md#1-origem-dos-dados-e-termos-de-uso) e [DATASET.md](DATASET.md#-por-que-não-o-home-credit) |
| 13 | `AGE` e `EDUCATION` fora das features, por ablação | ✅ Aceita | Sem eles a AUC val. não cai (0,7602 → 0,7622); minimização (art. 6º, III). No teste caiu 0,011, documentado. A remoção não eliminou a diferença por escolaridade, então a auditoria mede o resultado |
| 14 | Simulação com mesmo sorteio em todos os lotes; referência = validação + teste; drift em `LIMIT_BAL` e `PAY_0` | ✅ Aceita | Com seeds independentes, o ruído (sd 0,012 na AUC) gerou alerta sem causa no M02. Score do treino é otimista. Idade saiu do modelo. M06 não atendeu à expectativa e não foi recalibrado: a mudança de população mascara o concept drift |

---

**Última atualização:** 2026-11-10
