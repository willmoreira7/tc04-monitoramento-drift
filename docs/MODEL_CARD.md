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
| Tipo | Classificação binária — probabilidade de dificuldade de pagamento (`TARGET`) |
| Algoritmo | 🟡 Vencedor entre Dummy · LogisticRegression · XGBoost |
| Hiperparâmetros | 🟡 |
| Features | 🟡 Lista final após ablação (idade, escolaridade, composição familiar, `EXT_SOURCE_*`) |
| Features excluídas | `SK_ID_CURR`, `CODE_GENDER`, `NAME_FAMILY_STATUS`, dados de contato — ver [Governança no README](../README.md#%EF%B8%8F-governança-e-lgpd) |
| Artefato | `models/` (não versionado) |
| Seed | 42 |
| Dataset | Home Credit Default Risk (`application_train.csv`, recortado) — ver [DATASET.md](DATASET.md) |
| Dados de treino | Apenas o conjunto de **referência** |
| Hash do dataset | 🟡 |

---

## 🎯 Uso Pretendido

### Para que serve

Estimar a probabilidade de um proponente ter dificuldade de pagamento para **apoiar** a
decisão de concessão de crédito, e servir de objeto de estudo para a camada de
monitoramento.

### Para que **não** serve

| Uso indevido | Por quê |
|--------------|---------|
| Decisão de crédito totalmente automática | LGPD art. 20: o titular tem direito à revisão; o score é apoio |
| Aplicação a outra população ou período | País, moeda e período não declarados pelo provedor; distribuição desconhecida fora da amostra |
| Uso sem monitoramento de drift | É exatamente o risco que este projeto demonstra |

> 🔴 **Exercício acadêmico.** O modelo foi treinado em dado público de competição e o
> drift avaliado é simulado. Não está apto a decisões de crédito reais.

---

## 📊 Performance (teste da referência)

| Métrica | Valor | Observação |
|---------|-------|------------|
| AUC-ROC | 🟡 | Métrica de promoção |
| KS (bons × maus) | 🟡 | Padrão de mercado em crédito |
| Recall — inadimplente | 🟡 | |
| Precision — inadimplente | 🟡 | |
| Acurácia | 🟡 | ⚠️ Referência apenas — o Dummy acerta ~92% classificando todos como bons pagadores |

### Comparação entre candidatos

| Modelo | AUC-ROC | KS | Recall | |
|--------|---------|----|--------|---|
| 🟡 | | | | |

---

## ⚖️ Vieses e Equidade

| Grupo | Taxa de aprovação | Recall | Razão de impacto (4/5) |
|-------|------------------|--------|------------------------|
| `CODE_GENDER` | 🟡 | 🟡 | 🟡 |
| Faixas de idade | 🟡 | 🟡 | 🟡 |
| `NAME_EDUCATION_TYPE` | 🟡 | 🟡 | 🟡 |
| `NAME_FAMILY_STATUS` | 🟡 | 🟡 | 🟡 |
| `REGION_RATING_CLIENT` | 🟡 | 🟡 | 🟡 |

> ℹ️ Excluir gênero das features não garante ausência de viés: ocupação, renda,
> composição familiar e os próprios `EXT_SOURCE_*` podem funcionar como proxy. Por isso a
> auditoria mede o resultado por grupo.

---

## 📉 Comportamento sob Drift

> 🟡 Preenchido na Etapa 2 — performance por lote (M01…M06) e leitura causal.

| Lote | AUC-ROC | Recall | PSI do score | Alertas |
|------|---------|--------|--------------|---------|
| 🟡 | | | | |

---

## ⚠️ Limitações

- País, moeda e período dos dados não são declarados pelo provedor
- Só a tabela principal: sem histórico de bureau nem pedidos anteriores (tabelas relacionais fora do escopo)
- Dependência de `EXT_SOURCE_*`, scores de terceiros de composição desconhecida
- Renda é declarada pelo proponente, não comprovada
- Rótulos chegam com atraso em produção real; na simulação são revelados por lote
- Drift simulado: mecanismos plausíveis, intensidades escolhidas

---

**Última atualização:** 2026-11-07
