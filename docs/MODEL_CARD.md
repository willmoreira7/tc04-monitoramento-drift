# 🏷️ Model Card — Score de Risco de Crédito (baseline)

> 🔴 **Este arquivo mora em `docs/` de propósito.** O diretório `models/` é ignorado pelo
> Git — um Model Card gerado ali existiria em disco sem nunca chegar ao repositório (foi o
> que custou nota no TC02). Critério de aceite: `git ls-files docs/MODEL_CARD.md`.

> 🟡 **Estado:** template. Preenchido na Etapa 1 com números medidos e revisado na Etapa 4.

---

## 📇 Informações Gerais

| Campo | Valor |
|-------|-------|
| Nome do modelo | 🟡 |
| Tipo | Classificação binária — probabilidade de inadimplência no mês seguinte |
| Algoritmo | 🟡 Vencedor entre Dummy · LogisticRegression · XGBoost |
| Hiperparâmetros | 🟡 |
| Features | 🟡 Lista final após ablação de `AGE`/`EDUCATION` |
| Features excluídas | `ID`, `SEX`, `MARRIAGE` — ver [Governança no README](../README.md#%EF%B8%8F-governança-e-lgpd) |
| Artefato | `models/` (não versionado) |
| Seed | 42 |
| Dataset | UCI Default of Credit Card Clients — ver [DATASET.md](DATASET.md) |
| Dados de treino | Apenas o conjunto de **referência** |
| Hash do dataset | SHA256 `45bcf4df…3dd0` (completo em [DATASET.md](DATASET.md#-proveniência)) |

---

## 🎯 Uso Pretendido

### Para que serve

Estimar a probabilidade de inadimplência de um cliente de cartão de crédito para **apoiar**
a decisão de concessão, e servir de objeto de estudo para a camada de monitoramento.

### Para que **não** serve

| Uso indevido | Por quê |
|--------------|---------|
| Decisão de crédito totalmente automática | LGPD art. 20: o titular tem direito à revisão; o score é apoio |
| Aplicação a outro país, produto ou período | Dados de Taiwan, 2005, cartão de crédito — distribuição muito diferente |
| Uso sem monitoramento de drift | É exatamente o risco que este projeto demonstra |

> 🔴 **Exercício acadêmico.** O modelo foi treinado em dado público de 2005 e o drift
> avaliado é simulado. Não está apto a decisões de crédito reais.

---

## 📊 Performance (teste da referência)

| Métrica | Valor | Observação |
|---------|-------|------------|
| AUC-ROC | 🟡 | Métrica de promoção |
| KS (bons × maus) | 🟡 | Padrão de mercado em crédito |
| Recall — inadimplente | 🟡 | |
| Precision — inadimplente | 🟡 | |
| Acurácia | 🟡 | ⚠️ Referência apenas — ~78% é o piso do Dummy |

### Comparação entre candidatos

| Modelo | AUC-ROC | KS | Recall | |
|--------|---------|----|--------|---|
| 🟡 | | | | |

---

## ⚖️ Vieses e Equidade

| Grupo | Taxa de aprovação | Recall | Razão de impacto (4/5) |
|-------|------------------|--------|------------------------|
| `SEX` | 🟡 | 🟡 | 🟡 |
| Faixas de `AGE` | 🟡 | 🟡 | 🟡 |
| `EDUCATION` | 🟡 | 🟡 | 🟡 |

> ℹ️ Excluir `SEX` das features não garante ausência de viés: outras variáveis podem
> funcionar como proxy. Por isso a auditoria mede o resultado por grupo.

---

## 📉 Comportamento sob Drift

> 🟡 Preenchido na Etapa 2 — performance por lote (M01…M06) e leitura causal.

| Lote | AUC-ROC | Recall | PSI do score | Alertas |
|------|---------|--------|--------------|---------|
| 🟡 | | | | |

---

## ⚠️ Limitações

- Dados de 2005, Taiwan, um único produto (cartão de crédito)
- Sem renda declarada; capacidade de pagamento é inferida por fatura e pagamentos
- Rótulos chegam com atraso em produção real; na simulação são revelados por lote
- Drift simulado: mecanismos plausíveis, intensidades escolhidas

---

**Última atualização:** 2026-11-07
