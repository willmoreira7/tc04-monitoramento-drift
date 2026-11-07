# 📉 Simulação e Detecção de Drift

> Desenho dos lotes simulados, testes estatísticos, limiares e o método da análise causal.
> Implementação na Etapa 2, em `src/drift/`. Cenários declarados em
> `configs/drift_scenarios.yaml`.

> 🟡 **Status: especificação.** Intensidades a calibrar depois do baseline.

---

## 🎯 Três mecanismos, três consequências

Simular drift multiplicando uma coluna é fácil — e frequentemente errado, porque mistura
mecanismos com efeitos diferentes no modelo. Este projeto separa três:

| Mecanismo | O que muda | Como é simulado | O modelo deveria errar? | Quem detecta |
|-----------|-----------|-----------------|------------------------|--------------|
| **Covariate shift** (novos perfis, desemprego) | P(X) muda, P(y\|X) não | **Reamostragem ponderada** do pool: mais jovens, menos tempo de emprego, mais renda baixa | Pouco — ele já sabe pontuar esses perfis | Drift de features e de predição |
| **Drift nominal** (inflação) | Valores monetários mudam, risco real não | **Transformação**: preços e crédito sobem mais que a renda, rótulo mantido | Sim — vê comprometimento de renda maior do que o risco real | Drift de features **e** queda de performance |
| **Concept drift** (economia piora) | P(y\|X) muda, P(X) não | **Reetiquetagem**: probabilidade de default sobe para quem tem alto comprometimento de renda, features intactas | Sim — e **sem nenhum alerta de drift nas features** | Só performance, quando os rótulos chegam |

> 🔴 O terceiro mecanismo é a **degradação silenciosa** do enunciado: o painel de drift de
> features fica verde enquanto o modelo erra mais. É o argumento central do vídeo.

---

## 🗓️ Lotes

Seis lotes mensais de **10.000 linhas** (~800 inadimplentes cada), retirados do pool de
produção sem reposição.

| Lote | Narrativa | Perturbação | Esperado |
|------|----------|-------------|----------|
| **M01** | Mês normal | Nenhuma | **Sem drift.** Mede a taxa de falso positivo do detector |
| **M02** | Inflação começa | `AMT_GOODS_PRICE`, `AMT_CREDIT` × 1,10 · `AMT_ANNUITY` × 1,10 · renda × 1,03 | Drift leve nos valores e em `ANNUITY_INCOME_RATIO` (atenção) |
| **M03** | Inflação + novos perfis | Valores × 1,25 (renda × 1,05) · reamostragem: mais clientes < 30 anos | Drift moderado/crítico em valores e idade |
| **M04** | Desemprego sobe | M03 + reamostragem: menos `YEARS_EMPLOYED`, mais renda baixa e `EXT_SOURCE` baixo | Drift crítico em várias features e no score |
| **M05** | Concept drift puro | Features como M01; P(default) ↑ para `ANNUITY_INCOME_RATIO` alto | **Sem drift de features**, queda de AUC/recall |
| **M06** | Crise | M04 + reetiquetagem de M05 | Tudo dispara |

Mais um **lote corrompido** (ver [DATA_CONTRACTS.md](DATA_CONTRACTS.md#-demonstração-exigida-pelo-enunciado)),
que deve ser barrado antes de chegar aqui.

### Regras da simulação

- **A perturbação acontece nas colunas brutas**, antes das features derivadas. Assim a
  inflação aparece naturalmente em `CREDIT_INCOME_RATIO` e `ANNUITY_INCOME_RATIO`, como
  aconteceria de verdade
- **Todo lote perturbado continua válido no contrato.** Drift não é dado inválido; se a
  simulação gerar um valor impossível (ex.: parcela > crédito), o simulador está errado
- As features perturbadas são **importantes para o modelo** — exigência do enunciado. A
  lista final sai do ranking de importância do baseline (Etapa 1). Se uma variável sair do
  modelo por decisão de viés (ex.: idade), o drift de perfil é deslocado para outra feature
  relevante

---

## 📐 Testes estatísticos

O enunciado pede PSI ou Kolmogorov-Smirnov. **Os dois são configurados explicitamente**
no Evidently, coluna a coluna.

> ⚠️ **Não usar o stattest padrão.** Para amostras com mais de 1.000 linhas, o Evidently
> escolhe Wasserstein (numéricas) e Jensen-Shannon (categóricas) por padrão. Um relatório
> gerado sem configurar `stattest` **não** mostra PSI nem KS.

| Teste | Uso | Por quê |
|-------|-----|---------|
| **PSI** | **Decisão** de alerta | Mede a *magnitude* da mudança; padrão de mercado em risco de crédito; independe do tamanho da amostra |
| **KS** | Confirmação | Estatística D mostra a maior distância entre as CDFs |
| PSI do score | Drift de predição | Detecta mudança na saída do modelo antes dos rótulos chegarem |

### ⚠️ KS e amostras grandes

Com 10.000 linhas por lote contra ~150.000 de referência, o p-valor do KS rejeita H₀ para
diferenças **sem relevância prática**. Usar só `p < 0,05` geraria alerta em M01. Por isso:

- a decisão usa **PSI**, que mede tamanho de efeito
- o KS é reportado com a **estatística D**, não só o p-valor
- o lote M01 serve de calibração: se o KS dispara em M01, o limiar está errado

### ⚠️ Nulos e sentinelas

- `EXT_SOURCE_3` e `OCCUPATION_TYPE` têm nulos legítimos: a **fração de nulos** é
  monitorada como métrica própria, além do PSI dos valores presentes
- O sentinela `DAYS_EMPLOYED = 365243` distorce qualquer teste numérico: o drift é medido
  sobre `YEARS_EMPLOYED` (sentinela → nulo) e sobre a fração de `EMPLOYED_ANOMALY`

### Limiares propostos

| Sinal | Atenção | Crítico |
|-------|---------|---------|
| PSI por feature | ≥ 0,10 | ≥ 0,25 |
| Fração de features com drift (PSI ≥ 0,10) | ≥ 20% | ≥ 50% |
| PSI do score | ≥ 0,10 | ≥ 0,25 |
| Queda de AUC-ROC vs. teste da referência | ≥ 0,03 | ≥ 0,05 |
| Queda de recall de inadimplentes | ≥ 0,05 | ≥ 0,10 |

Faixas de PSI seguem a convenção de mercado (< 0,10 estável; 0,10–0,25 mudança moderada;
> 0,25 mudança significativa). Os limiares vivem em `configs/pipeline.yaml`.

---

## 🔬 Análise causal

Detectar drift responde *"o que mudou?"*. A diretoria pergunta outra coisa: *"por que o
modelo piorou?"*. As duas respostas podem não coincidir.

### Hipótese causal (DAG)

```
  Inflação ──► AMT_GOODS_PRICE, AMT_CREDIT, AMT_ANNUITY ↑ (nominal)
      │                       │
      │                       ▼
      │        ANNUITY_INCOME_RATIO ↑ ◄── renda nominal sobe menos
      │                       │
      │                       ▼
      │               score do modelo ──► decisão de crédito
      │                       ▲
  Desemprego ──► YEARS_EMPLOYED ↓, renda ↓, EXT_SOURCE ↓
      │
      └──────────► capacidade real de pagamento ↓ ──► inadimplência real ↑

  Novos perfis ──► idade ↓, menos histórico ──► score do modelo
```

### Método: intervenção, não correlação

Como a simulação é controlada, a causa verdadeira de cada degradação é **conhecida**. A
análise aplica cada perturbação **isoladamente** sobre o mesmo lote base e mede o efeito:

| Intervenção isolada | Features com drift | Δ AUC | Δ recall | Δ taxa de aprovação |
|--------------------|-------------------|-------|----------|---------------------|
| Só inflação nominal | 🟡 | 🟡 | 🟡 | 🟡 |
| Só novos perfis (idade) | 🟡 | 🟡 | 🟡 | 🟡 |
| Só desemprego | 🟡 | 🟡 | 🟡 | 🟡 |
| Só concept drift | 🟡 | 🟡 | 🟡 | 🟡 |

**Perguntas que a tabela responde:**

1. Qual drift **causa** degradação e qual é inofensivo? (drift ≠ degradação)
2. O detector aponta para a causa verdadeira, ou para uma feature correlacionada?
   (ex.: a inflação dispara alerta em `AMT_CREDIT`, mas o dano vem de `ANNUITY_INCOME_RATIO`)
3. Quanto da degradação é invisível ao monitoramento de features? (concept drift)

O resultado final — com a prescrição (retreinar, recalibrar, deflacionar os valores
monetários ou revisar a política de crédito) — vai para a seção de Análise Causal do
README.

---

## 📂 Evidências

| Artefato | Onde |
|----------|------|
| Cenários | `configs/drift_scenarios.yaml` |
| Simulação e detecção | `src/drift/` |
| Relatório Evidently por lote | `reports/drift/<batch_id>.html` (versionado) |
| Análise | `notebooks/03_drift_analysis.ipynb` |

---

**Última atualização:** 2026-11-07
