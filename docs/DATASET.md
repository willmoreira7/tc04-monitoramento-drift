# 📦 Dataset

> Escolha do dataset, esquema, problemas conhecidos e a separação entre referência e
> produção.

> 🟡 **Status: proposta.** Confirmar na Etapa 0 antes de qualquer código.

---

## 🎯 Exigências do enunciado

- Classificação binária financeira (risco, crédito ou precificação)
- **Pelo menos 5.000 amostras**
- Público e tabular, onde a degradação econômica faça sentido prático

---

## ⚖️ Candidatos

| Dataset | Linhas | Download sem conta | Atributos para LGPD/viés | Renda | Problemas reais de qualidade | Veredito |
|---------|--------|-------------------|--------------------------|-------|-----------------------------|----------|
| German Credit (UCI/Kaggle) | 1.000 | ✅ | ✅ | ❌ | Poucos | ❌ **Abaixo do mínimo de 5.000** |
| **Default of Credit Card Clients (UCI 350)** | **30.000** | ✅ | ✅ `SEX`, `AGE`, `EDUCATION`, `MARRIAGE` | ❌ | ✅ Códigos fora do dicionário | ✅ **Proposto** |
| Credit Risk Dataset (Kaggle) | ~32.500 | ❌ Conta Kaggle | 🟡 Só idade | ✅ | ✅ Nulos, idade 144 | 🟡 Alternativa |
| Give Me Some Credit (Kaggle) | 150.000 | ❌ Conta + regras da competição | 🟡 Só idade | ✅ | ✅ Renda nula, idade 0 | 🟡 Alternativa |
| Home Credit Default Risk (Kaggle) | 307.000 | ❌ Conta + regras da competição | ✅ | ✅ | ✅ | ❌ Grande demais para o foco do projeto |
| Lending Club | > 1 milhão | ❌ | 🟡 | ✅ | ✅ | ❌ Grande demais |

### Por que o UCI Default of Credit Card Clients

1. **Reprodutibilidade sem atrito.** Download direto da UCI, sem conta nem aceite de
   regras. O avaliador e o CI conseguem baixar com um comando — a principal lição do TC01.
2. **Tamanho certo.** 30.000 linhas comportam um split 50/50 (15.000 de referência,
   15.000 de pool de produção) e seis lotes mensais de 2.500 linhas.
3. **Governança rica.** Traz `SEX`, `MARRIAGE`, `EDUCATION` e `AGE`, o que dá substância
   real à seção de vieses e minimização da LGPD.
4. **Problemas de qualidade reais.** `EDUCATION` e `MARRIAGE` têm códigos fora do
   dicionário oficial; o contrato de dados tem trabalho de verdade a fazer.

### O custo da escolha

- **Não há coluna de renda.** O enunciado cita *"limites de renda"* como **exemplo** de
  regra. O equivalente aqui é `LIMIT_BAL` (limite de crédito concedido) e as faturas.
- **Valores em dólar taiwanês (NT$) e dados de 2005.** Irrelevante para o objetivo, que é
  o ciclo de sustentação, mas declarado no Model Card.

---

## 📋 Esquema

Fonte: [UCI Machine Learning Repository — id 350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients).
Clientes de cartão de crédito em Taiwan, histórico de abril a setembro de 2005.

| Coluna | Tipo | Domínio documentado | Papel |
|--------|------|---------------------|-------|
| `ID` | int | Único | Identificador — **descartado** |
| `LIMIT_BAL` | float | > 0 (NT$) | Feature |
| `SEX` | cat | 1 = masculino, 2 = feminino | Auditoria de viés — **fora do modelo** |
| `EDUCATION` | cat | 1 pós, 2 universidade, 3 ensino médio, 4 outros | A decidir (ablação) |
| `MARRIAGE` | cat | 1 casado, 2 solteiro, 3 outros | Auditoria de viés — **fora do modelo** |
| `AGE` | int | anos | A decidir (ablação); contrato exige ≥ 18 |
| `PAY_0`, `PAY_2` … `PAY_6` | int | −1 pago em dia; 1…9 meses de atraso | Feature |
| `BILL_AMT1` … `BILL_AMT6` | float | Valor da fatura (pode ser negativo: crédito a favor) | Feature |
| `PAY_AMT1` … `PAY_AMT6` | float | ≥ 0, valor pago | Feature |
| `default payment next month` | binário | 1 = inadimplente | **Target** (renomear para `default`) |

> ℹ️ Não existe `PAY_1` — a sequência original pula de `PAY_0` para `PAY_2`. Manter os
> nomes originais evita confusão com a documentação da fonte.

### Problemas conhecidos (a confirmar na EDA)

| Problema | Observação | Tratamento proposto |
|----------|-----------|---------------------|
| `EDUCATION` com 0, 5, 6 | Fora do dicionário | Na referência: agrupar em 4 ("outros"). Em produção: o contrato rejeita |
| `MARRIAGE` com 0 | Fora do dicionário | Agrupar em 3 ("outros") na referência |
| `PAY_*` com −2 e 0 | Não documentados (interpretados como "sem consumo" e "crédito rotativo") | Aceitos no domínio `[-2, 9]` |
| `BILL_AMT*` negativos | Crédito a favor do cliente | Aceitos |
| Desbalanceamento | ~22% de inadimplentes | Split estratificado; métricas além de acurácia |

> 🔴 A limpeza é aplicada **antes** do split e registrada no código, nunca à mão. O
> contrato de produção é mais estrito que a limpeza: em produção, código fora do domínio
> é sinal de problema na origem, não algo a corrigir em silêncio.

---

## ✂️ Separação Referência × Produção

```
UCI (30.000 linhas, ~22% inadimplentes)
 │  split estratificado pelo target, seed 42, feito UMA vez
 ├── referência ........ 15.000 → treino 70% · validação 15% · teste 15%
 └── pool de produção .. 15.000 → 6 lotes mensais de 2.500 (M01…M06)
                                 + 1 lote corrompido (demonstração do contrato)
```

| Conjunto | Diretório | Quem usa | Pode sofrer perturbação? |
|----------|-----------|----------|--------------------------|
| Referência | `data/reference/` | Treino, validação, teste; base de comparação do Evidently | ❌ Nunca |
| Pool de produção | `data/production/` | Simulador de drift | ✅ Só via `configs/drift_scenarios.yaml` |
| Quarentena | `data/quarantine/` | Lotes reprovados | — |

**Garantias (testadas):**

- Nenhuma linha do pool de produção aparece na referência
- A taxa de inadimplência dos dois lados difere menos de 1 p.p. antes da simulação
- O lote M01 (controle, sem perturbação) não acusa drift

---

## 🔐 Proveniência

| Item | Valor |
|------|-------|
| Fonte | UCI ML Repository, id 350 |
| Licença | CC BY 4.0 |
| Citação | Yeh, I. C., & Lien, C. H. (2009). *The comparisons of data mining techniques for the predictive accuracy of probability of default of credit card clients.* Expert Systems with Applications, 36(2). |
| Hash do arquivo bruto | 🟡 Registrar após o primeiro download |

---

**Última atualização:** 2026-11-07
