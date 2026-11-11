# 🛡️ Contratos de Dados

> Regras que um lote precisa cumprir para chegar ao modelo. Implementadas em
> [`src/contracts/`](../src/contracts/) com **Pandera** (ADR 02 em [ARQUITETURA.md](ARQUITETURA.md)).
> Todos os limites ficam em `configs/pipeline.yaml`, seção `contract`.

> ✅ **Status: implementado (Etapa 1).** Domínios conferidos na referência real: `AGE`
> 21–75, `LIMIT_BAL` 10 mil–1 milhão, `PAY_*` −2 a 8. A referência e o pool de produção
> passam no contrato antes de serem gravados.

---

## 🎯 Princípio

O contrato existe para que **lixo não entre no modelo**. Um modelo de crédito não recusa
entrada inválida: ele devolve um score para uma pessoa de 15 anos, para uma renda nula ou
para o mesmo cliente duplicado três vezes. O contrato é a única barreira entre a origem
dos dados e uma decisão de crédito.

O enunciado exige pelo menos **3 regras rígidas**. Este contrato define 8, porque cada uma
corresponde a uma falha plausível de origem.

---

## 📜 Regras

### Críticas — bloqueiam o lote

| # | Regra | Coluna(s) | Falha que intercepta |
|---|-------|-----------|----------------------|
| C1 | Esquema exato: colunas esperadas, tipos corretos, nenhuma coluna extra | todas | Mudança de layout na origem; coluna não prevista (ex.: `CPF`) vazando para o pipeline |
| C2 | Sem nulos | todas | Falha de extração, join quebrado |
| C3 | Sem duplicatas pela chave do cliente | chave técnica | Reprocessamento ou envio em dobro |
| C4 | `AGE` entre 18 e 100 | `AGE` | Menor de idade não pode contratar crédito; erro de digitação |
| C5 | `LIMIT_BAL` > 0 e ≤ 1.000.000 (máximo observado; só 1 cliente acima de 800 mil) | `LIMIT_BAL` | Limite zerado/negativo ou erro de escala (centavos × reais) |
| C6 | Códigos categóricos dentro do dicionário | `EDUCATION` ∈ {1,2,3,4}, `SEX` ∈ {1,2}, `MARRIAGE` ∈ {1,2,3} | Código novo não mapeado na origem |
| C7 | Status de pagamento no domínio | `PAY_*` ∈ [−2, 9] | Codificação trocada |
| C8 | Valores pagos não negativos | `PAY_AMT*` ≥ 0 | Sinal invertido no ETL |

### Avisos — registram, não bloqueiam

| # | Regra | Por que é só aviso |
|---|-------|--------------------|
| W1 | Alguma `BILL_AMT*` abaixo de −100.000 | Crédito a favor existe; valores extremos merecem investigação, não bloqueio. Dispara em 2 linhas da referência e 5 do pool |
| W2 | Lote com volume fora de ±30% de `batches.rows` (2.400) | Pode ser sazonalidade; vira métrica na Etapa 3 |
| W3 | Fração de `PAY_0 ≥ 2` acima de 1,5× a da referência (10,6%) | É sinal de drift, não de dado inválido; quem mede é a Etapa 2 |
| W4 | Linhas com conteúdo idêntico sob IDs diferentes | Existem 35 no dataset original; não dá para distinguir cadastro duplicado de perfil coincidente. Na referência são removidas na limpeza ([DATASET.md](DATASET.md)); num lote de produção viram aviso |

> ℹ️ **Contrato ≠ detector de drift.** Um lote com clientes mais endividados é *válido* e
> deve passar pelo contrato; quem o sinaliza é a Etapa 2. O contrato só reprova o que é
> **impossível ou malformado**. Misturar os dois faria o contrato barrar exatamente os
> lotes que o monitoramento de drift precisa analisar.

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
contaminaria a detecção de drift logo depois. ✅ ADR 06.

**Exit codes** de `scripts/validate_batch.py` e `scripts/prepare_data.py`: `0` aprovado ·
`1` dados ausentes · `2` bloqueado pelo contrato.

**Rótulo opcional:** a coluna `default` pode faltar (em produção o rótulo chega com
atraso). Se vier, precisa estar em {0, 1}.

---

## 🧪 Demonstração exigida pelo enunciado

> *"Forçar a passagem de um lote de dados com erros para demonstrar o contrato falhando e
> bloqueando a ingestão."*

O lote corrompido é gerado a partir de uma amostra **válida** do pool de produção, com
defeitos injetados de forma declarada:

Amostra de 500 linhas do pool (seed 42), 5 linhas por defeito, parâmetros em
`batches.corrupted` ([`src/contracts/corruption.py`](../src/contracts/corruption.py)):

| Defeito injetado | Regra esperada | Resultado medido |
|------------------|----------------|------------------|
| Nulos em `LIMIT_BAL` | C2 | ✅ C2, 5 casos (e C1: a coluna deixa de ser inteira) |
| `ID` repetido | C3 | ✅ C3, 10 casos (as 5 cópias e os 5 originais) |
| `AGE` = 15 e `AGE` = 130 | C4 | ✅ C4, 5 casos |
| `EDUCATION` = 7 | C6 | ✅ C6, 5 casos |
| `PAY_AMT1` negativo | C8 | ✅ C8, 5 casos |
| Coluna extra `CPF` (valor fictício fixo) | C1 | ✅ C1, `column_in_schema` |

Fonte: [`reports/validation/demo_corrupted.json`](../reports/validation/demo_corrupted.json).

```bash
uv run python scripts/validate_batch.py --demo valid       # 2.400 linhas do pool → aprovado, exit 0
uv run python scripts/validate_batch.py --demo corrupted   # bloqueado, exit 2, lote em data/quarantine/
```

**Critério de aceite:** cada defeito aparece no relatório de falhas com a regra correta,
o lote termina em quarentena e nenhuma predição é gravada. ✅ A quarentena e o relatório
estão cobertos por teste (`tests/test_contracts.py`); a garantia de que o lote bloqueado
não gera predição é verificada de novo na Etapa 2, quando a predição entrar no pipeline.

---

## 📂 Evidências

| Artefato | Onde |
|----------|------|
| Schema e mapeamento falha → regra | [`src/contracts/schema.py`](../src/contracts/schema.py) |
| Avisos W1–W4 | [`src/contracts/soft_checks.py`](../src/contracts/soft_checks.py) |
| Estágio (relatório, quarentena, log, bloqueio) | [`src/pipeline/validate.py`](../src/pipeline/validate.py) |
| Testes: lote válido passa e cada regra C1–C8 tem ao menos um caso que bloqueia | [`tests/test_contracts.py`](../tests/test_contracts.py) |
| Relatórios versionados | `reports/validation/`: `reference.json`, `production_pool.json`, `demo_valid.json`, `demo_corrupted.json` |
| Log da execução | stdout (structlog) hoje; `logs/pipeline.jsonl` e MLflow na Etapa 3 |

---

**Última atualização:** 2026-11-10
