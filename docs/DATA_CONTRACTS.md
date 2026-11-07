# 🛡️ Contratos de Dados

> Regras que um lote precisa cumprir para chegar ao modelo. Implementação na Etapa 1, em
> `src/contracts/`, com **Pandera** (ver ADR 02 em [ARQUITETURA.md](ARQUITETURA.md)).

> 🟡 **Status: especificação.** Domínios numéricos a confirmar na EDA.

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
| W1 | `BILL_AMT*` negativo acima de um teto | Crédito a favor existe; valores extremos merecem investigação, não bloqueio |
| W2 | Lote com volume fora de ±30% do esperado | Pode ser sazonalidade; vira métrica na Etapa 3 |
| W3 | Fração de `PAY_0 ≥ 2` muito acima da referência | É sinal de drift, não de dado inválido — deixa para a Etapa 2 |
| W4 | Linhas com conteúdo idêntico sob IDs diferentes | Existem 35 no dataset original; podem ser perfis coincidentes (ex.: cartões sem uso, tudo zerado). Viram aviso até a EDA concluir |

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
contaminaria a detecção de drift logo depois. 🟡 Proposta — registrar como ADR.

---

## 🧪 Demonstração exigida pelo enunciado

> *"Forçar a passagem de um lote de dados com erros para demonstrar o contrato falhando e
> bloqueando a ingestão."*

O lote corrompido é gerado a partir de uma amostra **válida** do pool de produção, com
defeitos injetados de forma declarada:

| Defeito injetado | Regra que deve disparar |
|------------------|------------------------|
| Nulos em `LIMIT_BAL` | C2 |
| Clientes duplicados | C3 |
| `AGE` = 15 e `AGE` = 130 | C4 |
| `EDUCATION` = 7 | C6 |
| `PAY_AMT1` negativo | C8 |
| Coluna extra `CPF` | C1 |

**Critério de aceite:** cada defeito aparece no relatório de falhas com a regra correta,
o lote termina em quarentena e nenhuma predição é gravada.

---

## 📂 Evidências

| Artefato | Onde |
|----------|------|
| Schemas | `src/contracts/` |
| Testes (lote válido passa, cada defeito bloqueia) | `tests/` |
| Relatório de validação por lote | `reports/validation/` (versionado) |
| Log da execução | `logs/pipeline.jsonl` e artefato no MLflow |

---

**Última atualização:** 2026-11-07
