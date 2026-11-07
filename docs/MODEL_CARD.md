# 🏷️ Model Card — Score de Risco de Crédito (baseline)

> 🔴 **Este arquivo mora em `docs/` de propósito.** O diretório `models/` é ignorado pelo
> Git — um Model Card gerado ali existiria em disco sem nunca chegar ao repositório (foi o
> que custou nota no TC02). Critério de aceite: `git ls-files docs/MODEL_CARD.md`.

> 🟡 **Estado:** performance e comparação preenchidas na Etapa 1 com números medidos.
> Pendentes: auditoria de viés, ablação de `AGE`/`EDUCATION` e comportamento sob drift.
>
> Fonte de todos os números: [`reports/model/model_comparison.json`](../reports/model/model_comparison.json),
> gerado por `uv run python scripts/train_model.py`.

---

## 📇 Informações Gerais

| Campo | Valor |
|-------|-------|
| Nome do modelo | `baseline-xgboost` |
| Tipo | Classificação binária — probabilidade de inadimplência no mês seguinte |
| Algoritmo | `StandardScaler` + `OneHotEncoder(EDUCATION)` → `XGBClassifier` |
| Hiperparâmetros | Padrão da biblioteca (xgboost 3.4.1), `random_state=42` — sem busca, por decisão (ADR 04) |
| Limiar de decisão | **0,2533** (máximo KS na validação); score ≥ limiar → classificado como risco |
| Features | 21: `LIMIT_BAL`, `EDUCATION`, `AGE`, `PAY_0`, `PAY_2`…`PAY_6`, `BILL_AMT1`…`6`, `PAY_AMT1`…`6` — 🟡 `AGE`/`EDUCATION` sujeitos à ablação |
| Features excluídas | `ID`, `SEX`, `MARRIAGE` — ver [Governança no README](../README.md#%EF%B8%8F-governança-e-lgpd) |
| Artefato | `models/baseline/model.joblib` + `metadata.json` (não versionados) |
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

## 📊 Performance (teste da referência, n = 2.248)

| Métrica | Valor | Observação |
|---------|-------|------------|
| AUC-ROC | **0,7479** | Métrica de promoção (avaliada na validação; o teste só reporta) |
| KS (bons × maus) | 0,3726 | Padrão de mercado em crédito |
| Recall — inadimplente | 0,5522 | No limiar 0,2533 |
| Precision — inadimplente | 0,4464 | |
| Taxa de aprovação | 72,6% | Fração classificada abaixo do limiar |
| Acurácia | — | ⚠️ Não usada: ~78% é o piso de quem prevê "ninguém fica inadimplente" |

Estes são os valores de **referência** para os alertas de degradação da Etapa 2 (queda de
AUC e de recall em relação ao teste).

### Comparação entre candidatos (ADR 04 — comparação enxuta)

Critério declarado antes do treino: AUC ≥ 0,70 e acima do Dummy **na validação**; maior AUC
vence; empate técnico (Δ < 0,01) favorece a regressão logística.

| Modelo | AUC val. | AUC teste | KS teste | Recall teste | Precision teste | |
|--------|---------|-----------|----------|--------------|-----------------|---|
| **XGBoost** | **0,7602** | **0,7479** | 0,3726 | 0,5522 | 0,4464 | ✅ promovido |
| LogisticRegression | 0,7057 | 0,7206 | **0,3862** | 0,5442 | 0,4892 | elegível |
| Dummy (estratificado) | 0,4902 | 0,4910 | 0,0000 | 0,2129 | 0,2078 | piso |

**Três leituras honestas:**

- O XGBoost venceu na validação com folga (Δ 0,055, cinco vezes a tolerância de empate):
  pelo critério declarado, a promoção é inequívoca.
- **No teste, a vantagem cai para Δ 0,027 de AUC, e o KS da regressão logística é até
  maior.** Com um único split, parte da diferença de validação é ruído. O critério não foi
  alterado depois de ver o teste — mudar a regra agora seria escolher pelo resultado.
- O custo é de **explicabilidade**: a regressão logística teria coeficientes diretos para
  explicar uma recusa (LGPD art. 20). Com o XGBoost promovido, a explicação ao titular
  passa a depender de importância de variáveis / contribuições por cliente — 🟡 tratado na
  auditoria da Etapa 4.

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
- **Ruído de rótulo:** 21 grupos de clientes com as 23 features idênticas e rótulos opostos ([01_eda.ipynb](../notebooks/01_eda.ipynb), seção 3) — um piso de erro que nenhum modelo elimina
- Rótulos chegam com atraso em produção real; na simulação são revelados por lote
- Drift simulado: mecanismos plausíveis, intensidades escolhidas

---

**Última atualização:** 2026-11-07
