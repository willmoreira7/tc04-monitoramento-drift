# 🛡️ Contratos de Dados

> Regras que um lote precisa cumprir para chegar ao modelo. Implementação na Etapa 1, em
> `src/contracts/`, com **Pandera** (ver ADR 02 em [ARQUITETURA.md](ARQUITETURA.md)).

> 🟡 **Status: especificação.** Domínios e tetos numéricos a confirmar na EDA.

---

## 🎯 Princípio

O contrato existe para que **lixo não entre no modelo**. Um modelo de crédito não recusa
entrada inválida: ele devolve um score para uma pessoa de 15 anos, para uma renda nula ou
para alguém empregado há 1.000 anos. O contrato é a única barreira entre a origem dos
dados e uma decisão de crédito.

O enunciado exige pelo menos **3 regras rígidas**. Este contrato define 10, e quase todas
correspondem a uma anomalia que **existe de verdade** no Home Credit (ver
[DATASET.md](DATASET.md#-problemas-conhecidos-e-tratamento)).

O contrato valida o lote **bruto**, nas colunas originais — antes de qualquer feature
derivada.

---

## 📜 Regras

### Críticas — bloqueiam o lote

| # | Regra | Coluna(s) | Falha que intercepta |
|---|-------|-----------|----------------------|
| C1 | Esquema exato: colunas do recorte, tipos corretos, nenhuma coluna extra | todas | Mudança de layout na origem; coluna não prevista (ex.: `CPF`) vazando |
| C2 | Sem nulos nas colunas obrigatórias | `AMT_INCOME_TOTAL`, `AMT_CREDIT`, `AMT_ANNUITY`, `AMT_GOODS_PRICE`, `DAYS_BIRTH`, `DAYS_EMPLOYED`, `NAME_INCOME_TYPE`, `CODE_GENDER`… | Falha de extração; **renda não pode ser nula** |
| C3 | `SK_ID_CURR` único | `SK_ID_CURR` | Reprocessamento ou envio em dobro |
| C4 | Idade entre 18 e 100 anos | `DAYS_BIRTH` | Menor de idade não pode contratar crédito; erro de sinal |
| C5 | Renda > 0 e ≤ teto plausível | `AMT_INCOME_TOTAL` | Renda zerada; erro de escala (o outlier de ~117 milhões) |
| C6 | Crédito e parcela positivos, parcela ≤ crédito | `AMT_CREDIT`, `AMT_ANNUITY` | Parcela maior que a dívida inteira é impossível |
| C7 | Emprego coerente: `DAYS_EMPLOYED` ≤ 0, **ou** = 365243 apenas se `NAME_INCOME_TYPE` ∈ {Pensioner, Unemployed} | `DAYS_EMPLOYED`, `NAME_INCOME_TYPE` | O sentinela aparecendo para quem declara trabalhar |
| C8 | Categóricas no domínio conhecido | `CODE_GENDER` ∈ {M, F}; `NAME_INCOME_TYPE`, `NAME_EDUCATION_TYPE`, `NAME_FAMILY_STATUS`, `NAME_HOUSING_TYPE`, `NAME_CONTRACT_TYPE` nos valores da referência | `XNA`, `Unknown`, código novo não mapeado |
| C9 | Scores externos em [0, 1] (nulo permitido) | `EXT_SOURCE_2`, `EXT_SOURCE_3` | Bureau mudou a escala do score |
| C10 | Família coerente: `CNT_FAM_MEMBERS` ≥ `CNT_CHILDREN` + 1 | `CNT_FAM_MEMBERS`, `CNT_CHILDREN` | Contagens trocadas ou corrompidas |

> ℹ️ C6, C7 e C10 são **regras entre colunas**. São as que mais mostram o valor de um
> contrato: cada coluna isolada parece válida, a combinação é impossível.

### Avisos — registram, não bloqueiam

| # | Regra | Por que é só aviso |
|---|-------|--------------------|
| W1 | Fração de nulos em `OCCUPATION_TYPE` e `EXT_SOURCE_3` dentro de ±10 p.p. da referência | Nulo é permitido; mudança brusca na fração indica problema na origem, mas não invalida o lote |
| W2 | Volume do lote fora de ±30% do esperado | Pode ser sazonalidade; vira métrica na Etapa 3 |
| W3 | Renda acima do percentil 99,9 da referência | Renda alta existe; extremos merecem investigação |

> ℹ️ **Contrato ≠ detector de drift.** Um lote com clientes de renda menor ou mais
> comprometida é *válido* e deve passar pelo contrato; quem o sinaliza é a Etapa 2. O
> contrato só reprova o que é **impossível ou malformado**. Misturar os dois faria o
> contrato barrar exatamente os lotes que o monitoramento de drift precisa analisar.

---

## 🚧 Comportamento de bloqueio

```
lote ──► validação Pandera (lazy=True: coleta TODAS as violações, não só a primeira)
           │
           ├── sem violação crítica ──► segue para predição
           │                             avisos vão para o log
           │
           └── violação crítica ──► lote movido para data/quarantine/<batch_id>/
                                     relatório de falhas (regra, coluna, nº de casos)
                                     log status=blocked + alerta crítico
                                     exit code ≠ 0
                                     NENHUMA predição gerada
```

**Decisão: o lote inteiro é bloqueado**, não só as linhas inválidas. Filtrar linhas em
silêncio esconderia um problema de origem e mudaria a distribuição do lote — o que
contaminaria a detecção de drift logo depois (ADR 06).

> ⚠️ O relatório de falhas registra **regra, coluna e contagem** — nunca os valores das
> linhas reprovadas. Ele é versionado em `reports/validation/` e não pode carregar dado
> pessoal.

---

## 🧪 Demonstração exigida pelo enunciado

> *"Forçar a passagem de um lote de dados com erros para demonstrar o contrato falhando e
> bloqueando a ingestão."*

O lote corrompido parte de uma amostra **válida** do pool de produção. Os defeitos
injetados reproduzem as anomalias reais do dataset, para mostrar que o contrato pegaria o
que de fato aparece na origem:

| Defeito injetado | Espelha anomalia real? | Regra que deve disparar |
|------------------|-----------------------|------------------------|
| Nulos em `AMT_INCOME_TOTAL` | — | C2 |
| `SK_ID_CURR` duplicado | — | C3 |
| Idade de 15 anos (`DAYS_BIRTH` ≈ −5.479) | — | C4 |
| Renda de 117 milhões | ✅ outlier real | C5 |
| `AMT_ANNUITY` > `AMT_CREDIT` | — | C6 |
| `DAYS_EMPLOYED = 365243` com `NAME_INCOME_TYPE = Working` | ✅ sentinela real | C7 |
| `CODE_GENDER = 'XNA'` | ✅ valor real | C8 |
| `EXT_SOURCE_2 = 1.7` | — | C9 |
| Coluna extra `CPF` | — | C1 |

**Critério de aceite:** cada defeito aparece no relatório com a regra correta, o lote
termina em quarentena e nenhuma predição é gravada.

---

## 📂 Evidências

| Artefato | Onde |
|----------|------|
| Schemas | `src/contracts/` |
| Testes (lote válido passa, cada defeito bloqueia) | `tests/` |
| Relatório de validação por lote | `reports/validation/` (versionado, só agregados) |
| Log da execução | `logs/pipeline.jsonl` e artefato no MLflow |

---

**Última atualização:** 2026-11-07
