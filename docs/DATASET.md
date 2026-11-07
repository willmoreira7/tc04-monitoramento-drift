# 📦 Dataset

> Escolha do dataset, recorte de colunas, problemas conhecidos e a separação entre
> referência e produção.

> ✅ **Decisão:** Home Credit Default Risk — apenas a tabela principal
> (`application_train.csv`), recortada. Números marcados com "~" vêm da literatura da
> competição e são **confirmados na EDA** (Etapa 1).

---

## 🎯 Exigências do enunciado

- Classificação binária financeira (risco, crédito ou precificação)
- **Pelo menos 5.000 amostras**
- Público e tabular, onde a degradação econômica faça sentido prático

---

## ⚖️ Candidatos avaliados

| Dataset | Linhas | Prós | Contras | Veredito |
|---------|--------|------|---------|----------|
| German Credit | 1.000 | Clássico, atributos para viés | **Abaixo do mínimo de 5.000** | ❌ Desqualificado |
| Default of Credit Card Clients (UCI, Taiwan) | 30.000 | Download sem conta; `SEX`/`AGE`/`MARRIAGE` | Sem renda nem emprego; scoring de comportamento, não de concessão; `BILL_AMT*` redundantes; pouca sujeira real | 🟡 Plano B |
| Credit Risk Dataset (Kaggle) | ~32.500 | Renda, juros, nulos e outliers reais | **Procedência desconhecida**; `loan_grade` quase vaza o target; só idade para viés | ❌ |
| Give Me Some Credit (Kaggle) | 150.000 | Renda, muita sujeira real | ~6,7% de positivos: métricas por lote ruidosas; ~20% de renda nula | ❌ |
| **Home Credit Default Risk (Kaggle)** | **~307.500** | Concessão real; renda, emprego, idade, gênero, família; anomalias famosas | 122 colunas; arquivo pesado; login + aceite de regras | ✅ **Escolhido** |
| Lending Club | ~2,2 milhões | Drift temporal real | Enorme; dezenas de colunas com vazamento pós-concessão | ❌ |

### Por que Home Credit

1. **É o problema do enunciado.** Concessão de crédito a pessoas com pouco histórico
   bancário — o cenário de uma fintech. O Taiwan é scoring de comportamento de quem já é
   cliente de cartão.
2. **Renda e emprego existem.** `AMT_INCOME_TOTAL`, `DAYS_EMPLOYED` e `NAME_INCOME_TYPE`
   tornam literais os exemplos do enunciado ("limites de renda", "taxa de desemprego",
   "inflação").
3. **Anomalias reais para o contrato.** `DAYS_EMPLOYED = 365243` (~1.000 anos de emprego),
   `CODE_GENDER = 'XNA'`, renda de ~117 milhões, nulos em `AMT_ANNUITY`. O contrato não
   precisa de defeitos inventados para mostrar serviço.
4. **Governança substancial.** Gênero, estado civil, idade, filhos, ocupação, região e
   **scores de bureaus externos** (`EXT_SOURCE_*`) — material real para minimização,
   não discriminação e explicabilidade (LGPD art. 20).
5. **Volume para lotes grandes.** Com ~8% de positivos, lotes de 10.000 linhas trazem ~800
   inadimplentes — o suficiente para medir AUC por lote sem ruído de amostragem.

### O custo da escolha (e como é mitigado)

| Custo | Mitigação |
|-------|-----------|
| Download exige conta no Kaggle **e** aceite das regras da competição | Passo a passo no README; `scripts/download_data.py` com mensagem clara se faltar credencial; **fallback sintético** com o mesmo esquema (modelo do TC03, que tirou 90 com dataset do Kaggle) |
| Regras da competição proíbem redistribuir os dados | Dados nunca versionados; `reports/` só com agregados |
| 122 colunas | Recorte para ~20 colunas da tabela principal (abaixo); tabelas relacionais (`bureau`, `previous_application` etc.) **fora do escopo** |
| ~8% de positivos | Split estratificado; métricas AUC/KS/recall, nunca acurácia (o Dummy acerta ~92%) |
| Moeda e país não declarados pelo provedor | Valores tratados como unidade monetária genérica; declarado no Model Card |

---

## 📋 Recorte de colunas

Fonte: [Kaggle — Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk/data),
arquivo `application_train.csv` (~307.511 linhas × 122 colunas; `TARGET` = 1 indica
dificuldade de pagamento, ~8%).

### Chave e target

| Coluna | Papel |
|--------|-------|
| `SK_ID_CURR` | Chave do pedido (pseudônimo). Usada só para unicidade e rastreio; **nunca** é feature |
| `TARGET` | 1 = cliente com dificuldade de pagamento |

### Features candidatas

| Coluna | Tipo | Significado | Observação |
|--------|------|-------------|------------|
| `NAME_CONTRACT_TYPE` | cat | Cash loans / Revolving loans | |
| `AMT_INCOME_TOTAL` | float | Renda declarada | Outlier extremo conhecido |
| `AMT_CREDIT` | float | Valor do crédito | |
| `AMT_ANNUITY` | float | Valor da parcela | Poucos nulos |
| `AMT_GOODS_PRICE` | float | Preço do bem financiado | Poucos nulos |
| `NAME_INCOME_TYPE` | cat | Working, Pensioner, Unemployed… | Base da narrativa de desemprego |
| `DAYS_EMPLOYED` | int | Dias de emprego (negativo) | **Sentinela 365243** |
| `DAYS_BIRTH` | int | Idade em dias (negativo) | 🟡 Uso decidido por ablação (viés) |
| `NAME_EDUCATION_TYPE` | cat | Escolaridade | 🟡 Uso decidido por ablação (viés) |
| `NAME_HOUSING_TYPE` | cat | Situação de moradia | |
| `FLAG_OWN_CAR`, `FLAG_OWN_REALTY` | Y/N | Possui carro / imóvel | |
| `CNT_CHILDREN`, `CNT_FAM_MEMBERS` | int | Filhos / membros da família | 🟡 Proxy de estado civil — ablação |
| `OCCUPATION_TYPE` | cat | Ocupação | ~31% nulo (nulo é informativo) |
| `REGION_RATING_CLIENT` | ord | Nota da região (1–3) | 🟡 Proxy socioeconômico — auditar |
| `EXT_SOURCE_2`, `EXT_SOURCE_3` | float [0,1] | Scores de fontes externas | Preditores mais fortes; `EXT_SOURCE_3` ~20% nulo |

### Features derivadas (no pipeline, não no contrato)

| Feature | Fórmula | Por quê |
|---------|---------|---------|
| `AGE_YEARS` | `-DAYS_BIRTH / 365.25` | Legibilidade e regra de idade |
| `YEARS_EMPLOYED` | `-DAYS_EMPLOYED / 365.25`; sentinela → nulo | Remove o 365243 sem perder a informação |
| `EMPLOYED_ANOMALY` | `DAYS_EMPLOYED == 365243` | O sentinela carrega sinal (aposentados) |
| `CREDIT_INCOME_RATIO` | `AMT_CREDIT / AMT_INCOME_TOTAL` | Alavancagem |
| `ANNUITY_INCOME_RATIO` | `AMT_ANNUITY / AMT_INCOME_TOTAL` | **Comprometimento de renda** — onde a inflação aparece |

### Apenas para auditoria de viés (nunca features)

| Coluna | Motivo |
|--------|--------|
| `CODE_GENDER` | Não discriminação (LGPD art. 6º, IX) |
| `NAME_FAMILY_STATUS` | Idem |

### Descartadas na ingestão

| Grupo | Motivo |
|-------|--------|
| `FLAG_MOBIL`, `FLAG_EMAIL`, `FLAG_PHONE`, `FLAG_WORK_PHONE`… | Dados de contato: sem necessidade para a finalidade (art. 6º, III) |
| ~47 colunas de características do imóvel (`*_AVG`, `*_MODE`, `*_MEDI`) | Maioria nula; fora do foco |
| `FLAG_DOCUMENT_*` | Baixo sinal; fora do foco |
| `EXT_SOURCE_1` | ~56% nulo |
| `AMT_REQ_CREDIT_BUREAU_*`, `OBS_*`, `DEF_*` | Fora do recorte |

> ℹ️ O recorte final pode mudar na EDA. Toda mudança é registrada aqui e em
> `configs/pipeline.yaml`, nunca só no código.

---

## 🧹 Problemas conhecidos e tratamento

| Problema | Ocorrência (~) | Na referência (limpeza) | Em produção (contrato) |
|----------|---------------|-------------------------|------------------------|
| `DAYS_EMPLOYED = 365243` | ~18% (aposentados e desempregados) | Vira `YEARS_EMPLOYED` nulo + `EMPLOYED_ANOMALY = 1` | Aceito **só** com `NAME_INCOME_TYPE` ∈ {Pensioner, Unemployed}; positivo em outro caso bloqueia |
| `CODE_GENDER = 'XNA'` | 4 linhas | Removidas | Bloqueia |
| `NAME_FAMILY_STATUS = 'Unknown'` | ~2 linhas | Removidas | Bloqueia |
| Renda extrema (~117 milhões) | 1 linha | Removida | Acima do teto bloqueia |
| `AMT_ANNUITY` nulo | ~12 linhas | Removidas | Bloqueia |
| `AMT_GOODS_PRICE` nulo | ~278 linhas | Removidas | Bloqueia |
| `OCCUPATION_TYPE` nulo | ~31% | Mantido como categoria "Unknown" | Permitido; fração monitorada (aviso) |
| `EXT_SOURCE_3` nulo | ~20% | Imputado no pipeline do modelo | Permitido; fração monitorada (aviso) |

> 🔴 A limpeza da referência é código, aplicada **antes** do split, e cada remoção é
> contada e logada. O contrato de produção é mais estrito que a limpeza: lá, um valor
> impossível é sinal de problema na origem, não algo a corrigir em silêncio.

---

## ✂️ Separação Referência × Produção

```
application_train.csv (~307.500 linhas, ~8% positivos)
 │  limpeza (remoções declaradas acima)
 │  split estratificado pelo TARGET, seed 42, feito UMA vez
 ├── referência ........ 50% → treino 70% · validação 15% · teste 15%
 └── pool de produção .. 50% → 6 lotes mensais de 10.000 (M01…M06)
                               + 1 lote corrompido (demonstração do contrato)
```

| Conjunto | Diretório | Quem usa | Pode sofrer perturbação? |
|----------|-----------|----------|--------------------------|
| Referência | `data/reference/` | Treino, validação, teste; base de comparação do Evidently | ❌ Nunca |
| Pool de produção | `data/production/` | Simulador de drift | ✅ Só via `configs/drift_scenarios.yaml` |
| Quarentena | `data/quarantine/` | Lotes reprovados | — |

**Garantias (testadas):**

- Nenhum `SK_ID_CURR` do pool de produção aparece na referência
- A taxa de positivos dos dois lados difere menos de 0,5 p.p. antes da simulação
- O lote M01 (controle, sem perturbação) não acusa drift

> ℹ️ `application_test.csv` **não é usado**: não tem `TARGET`, então não serve nem para
> treino nem para medir concept drift.

---

## 📥 Obtenção

| Passo | Detalhe |
|-------|---------|
| 1. Conta | Criar conta no Kaggle |
| 2. Regras | Aceitar as regras em *Home Credit Default Risk → Rules* (sem isso o download retorna 403) |
| 3. Credencial | Token da API em `~/.kaggle/kaggle.json` ou variáveis `KAGGLE_USERNAME` / `KAGGLE_KEY` |
| 4. Download | `scripts/download_data.py` (⬜ Etapa 0) baixa só `application_train.csv` |
| Sem conta | Gerador sintético com o mesmo esquema: valida o pipeline, **não** reproduz as métricas |

---

## 🔐 Proveniência

| Item | Valor |
|------|-------|
| Fonte | Kaggle — competição *Home Credit Default Risk* (Home Credit Group, 2018) |
| Arquivo | `application_train.csv` |
| Licença | Regras da competição — uso não comercial, **sem redistribuição** |
| Anonimização | Feita pelo provedor; `SK_ID_CURR` é pseudônimo |
| Hash do arquivo bruto | 🟡 Registrar após o primeiro download |

---

**Última atualização:** 2026-11-07
