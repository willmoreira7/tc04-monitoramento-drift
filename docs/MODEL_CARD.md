# 🏷️ Model Card — Score de Risco de Crédito (baseline)

> 🔴 **Este arquivo mora em `docs/` de propósito.** O diretório `models/` é ignorado pelo
> Git — um Model Card gerado ali existiria em disco sem nunca chegar ao repositório (foi o
> que custou nota no TC02). Critério de aceite: `git ls-files docs/MODEL_CARD.md`.

> 🟡 **Estado:** performance, comparação, ablação e auditoria de viés preenchidas na
> Etapa 1 com números medidos. Pendente: comportamento sob drift (Etapa 2).
>
> Fontes, todas versionadas:
> - [`reports/model/model_comparison.json`](../reports/model/model_comparison.json), gerado por `uv run python scripts/train_model.py`.
> - [`reports/model/ablation.json`](../reports/model/ablation.json) e [`reports/model/fairness_audit.json`](../reports/model/fairness_audit.json), gerados por `uv run python scripts/audit_model.py`.

---

## 📇 Informações Gerais

| Campo | Valor |
|-------|-------|
| Nome do modelo | `baseline-xgboost` |
| Tipo | Classificação binária — probabilidade de inadimplência no mês seguinte |
| Algoritmo | `StandardScaler` → `XGBClassifier` |
| Hiperparâmetros | Padrão da biblioteca (xgboost 3.4.1), `random_state=42` — sem busca, por decisão (ADR 04) |
| Limiar de decisão | **0,2556** (máximo KS na validação); score ≥ limiar → classificado como risco |
| Features | 19, **só financeiras**: `LIMIT_BAL`, `PAY_0`, `PAY_2`…`PAY_6`, `BILL_AMT1`…`6`, `PAY_AMT1`…`6` |
| Features excluídas | `ID`, `SEX`, `MARRIAGE` (ADR 08) · `AGE`, `EDUCATION` (removidas pela ablação, ADR 13) — ver [Governança no README](../README.md#%EF%B8%8F-governança-e-lgpd) |
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
| AUC-ROC | **0,7368** | Métrica de promoção (avaliada na validação; o teste só reporta) |
| KS (bons × maus) | 0,3779 | Padrão de mercado em crédito |
| Recall — inadimplente | 0,5582 | No limiar 0,2556 |
| Precision — inadimplente | 0,4557 | |
| Taxa de aprovação | 72,9% | Fração classificada abaixo do limiar |
| Acurácia | — | ⚠️ Não usada: ~78% é o piso de quem prevê "ninguém fica inadimplente" |

Estes são os valores de **referência** para os alertas de degradação da Etapa 2 (queda de
AUC e de recall em relação ao teste).

### Comparação entre candidatos (ADR 04 — comparação enxuta)

Critério declarado antes do treino: AUC ≥ 0,70 e acima do Dummy **na validação**; maior AUC
vence; empate técnico (Δ < 0,01) favorece a regressão logística.

| Modelo | AUC val. | AUC teste | KS teste | Recall teste | Precision teste | |
|--------|---------|-----------|----------|--------------|-----------------|---|
| **XGBoost** | **0,7622** | **0,7368** | 0,3779 | 0,5582 | 0,4557 | ✅ promovido |
| LogisticRegression | 0,7081 | 0,7183 | **0,3938** | 0,5582 | **0,4760** | elegível |
| Dummy (estratificado) | 0,4902 | 0,4910 | 0,0000 | 0,2129 | 0,2078 | piso |

**Três leituras honestas:**

- O XGBoost venceu na validação com folga (Δ 0,054, cinco vezes a tolerância de empate):
  pelo critério declarado, a promoção é inequívoca.
- **No teste, a vantagem cai para Δ 0,019 de AUC; o KS e a precision da regressão
  logística são maiores e o recall é igual.** Com um único split, parte da diferença de
  validação é ruído. O critério não foi alterado depois de ver o teste: mudar a regra
  agora seria escolher pelo resultado.
- O custo é de **explicabilidade**: a regressão logística teria coeficientes diretos para
  explicar uma recusa (LGPD art. 20). Com o XGBoost promovido, a explicação ao titular
  passa a depender de importância de variáveis / contribuições por cliente — 🟡 tratado na
  auditoria da Etapa 4.

---

## 🧪 Ablação de `AGE` e `EDUCATION` (ADR 13)

Critério declarado **antes** de rodar (commit separado, `configs/pipeline.yaml` seção
`ablation`): um atributo pessoal só fica se pagar por si. Remove-se o conjunto se a
variante sem ele perder menos de 0,01 de AUC na validação.

| Variante | AUC val. (XGBoost, promovido) | Perda vs. todos | AUC val. LogReg |
|----------|-------------------------------|-----------------|-----------------|
| Com `AGE` e `EDUCATION` | 0,7602 | — | 0,7057 |
| Sem `AGE` | 0,7577 | 0,0025 | 0,7065 |
| Sem `EDUCATION` | 0,7611 | −0,0009 | 0,7070 |
| **Sem os dois** | **0,7622** | **−0,0020** | 0,7081 |

**Decisão: os dois saem.** Sem eles a AUC de validação não cai, e o modelo passa a usar
só dados financeiros (minimização, LGPD art. 6º, III).

> ⚠️ **No teste, a AUC do XGBoost caiu de 0,7479 para 0,7368 (−0,011)** com a remoção.
> Pela regra, a decisão é tomada na validação e o teste só reporta. Na validação o efeito
> foi +0,002. A diferença entre os dois sentidos está dentro do ruído de um split único
> (n ≈ 2.250 em cada), e reverter a decisão olhando o teste seria escolher pelo resultado.

---

## ⚖️ Vieses e Equidade

Medido no **teste** (n = 2.248) com o modelo promovido, no limiar 0,2556. Fonte:
[`reports/model/fairness_audit.json`](../reports/model/fairness_audit.json).

Duas razões de impacto, porque os grupos têm inadimplência real diferente:

- **Razão de impacto:** aprovação do grupo dividida pela maior aprovação entre os grupos
  (regra dos 4/5). Mistura risco real com tratamento diferente.
- **Razão de bons pagadores:** a mesma conta, só entre quem **não** ficou inadimplente. É a
  leitura principal: um bom pagador tem a mesma chance de aprovação em qualquer grupo?

| Atributo | Grupo | n | Inadimplência real | Aprovação | Aprovação de bons pagadores | Recall inadimplentes | Razão de impacto | Razão bons pagadores |
|----------|-------|---|-------------------|-----------|-----------------------------|----------------------|------------------|----------------------|
| `SEX` | masculino | 909 | 24,3% | 70,1% | 80,2% | 61,5% | 0,937 | 0,984 |
| | feminino | 1.339 | 20,7% | 74,8% | 81,5% | 51,3% | 1,000 | 1,000 |
| `AGE` | 18–29 | 779 | 23,4% | 71,3% | 79,7% | 56,6% | 0,958 | 0,967 |
| | 30–39 | 805 | 20,6% | 74,4% | 82,5% | 56,6% | 1,000 | 1,000 |
| | 40–49 | 475 | 20,6% | 74,1% | 81,4% | 54,1% | 0,996 | 0,987 |
| | 50+ | 189 | 27,5% | 69,8% | 78,8% | 53,8% | 0,939 | 0,956 |
| `EDUCATION` | pós-graduação | 821 | 21,4% | 75,9% | 84,7% | 56,3% | 1,000 | 1,000 |
| | universidade | 1.040 | 23,7% | 72,3% | 80,5% | 54,1% | 0,953 | 0,951 |
| | ensino médio | 358 | 20,9% | 66,2% | **73,1%** | 60,0% | 0,872 | **0,864** |
| | outros ⚪ | 29 | 3,4% | 89,7% | 92,9% | — | — | — |
| `MARRIAGE` | casado | 1.009 | 22,2% | 71,2% | 79,2% | 57,1% | 0,961 | 0,963 |
| | solteiro | 1.213 | 22,1% | 74,0% | 82,3% | 55,2% | 1,000 | 1,000 |
| | outros ⚪ | 26 | 23,1% | 84,6% | 90,0% | — | — | — |

⚪ Grupos com menos de 100 pessoas: números reportados, sem conclusão. Também não servem de
referência para as razões.

**Leituras:**

- **Nenhum grupo conclusivo fica abaixo de 0,8** em nenhuma das duas razões.
- **O ponto mais próximo do limite é a escolaridade "ensino médio"** (0,864 entre bons
  pagadores):
  - Com a mesma inadimplência real da pós-graduação (cerca de 21%), um bom pagador desse
    grupo é aprovado em 73,1% dos casos, contra 84,7%.
  - Esse grupo tem metade do limite mediano (90 mil contra 180 mil) e mais atraso recente
    em `PAY_0` (26,5% contra 20,8%). São variáveis legítimas para o risco, mas
    correlacionadas com escolaridade.
- **Remover `EDUCATION` não removeu a diferença.** Na validação, a razão de impacto por
  escolaridade passou de 0,87 (com a feature) para 0,82 (sem ela). Tirar o atributo do
  modelo não basta, e por isso a auditoria mede o resultado e não a lista de features.
- **`SEX`:** o modelo identifica menos inadimplentes entre mulheres (recall 51% contra 62%).
  O efeito favorece a aprovação delas e não prejudica bons pagadores (razão 0,98).

**Mitigação adotada:**

- Atributos pessoais fora das features (ADR 08 e 13).
- Auditoria por grupo reexecutada a cada treino, com `scripts/audit_model.py`.
- Recusas sujeitas a revisão humana (LGPD art. 20).
- 🟡 Razões por grupo acompanhadas por lote na Etapa 3 (proposta).
- **Descartado:** limiar diferente por grupo. Exigiria usar o atributo protegido na própria
  decisão.

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

**Última atualização:** 2026-11-10
