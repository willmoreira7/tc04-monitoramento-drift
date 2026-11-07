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
| **Covariate shift** (novos perfis) | P(X) muda, P(y\|X) não | **Reamostragem ponderada** do pool: mais clientes jovens, mais endividados | Pouco — ele já sabe pontuar esses perfis | Drift de features e de predição |
| **Drift nominal** (inflação) | Valores das features mudam, risco real não | **Transformação**: `BILL_AMT*` e `LIMIT_BAL` × fator de inflação, rótulo mantido | Sim — vê clientes "mais endividados" do que realmente são | Drift de features **e** queda de performance |
| **Concept drift** (economia piora) | P(y\|X) muda, P(X) não | **Reetiquetagem**: probabilidade de default sobe para perfis de alta utilização, features intactas | Sim — e **sem nenhum alerta de drift nas features** | Só performance, quando os rótulos chegam |

> 🔴 O terceiro mecanismo é a **degradação silenciosa** do enunciado: o painel de drift de
> features fica verde enquanto o modelo erra mais. É o argumento central do vídeo.

---

## 🗓️ Lotes

Seis lotes mensais de 2.400 linhas, retirados do pool de produção sem reposição.

| Lote | Narrativa | Perturbação | Esperado |
|------|----------|-------------|----------|
| **M01** | Mês normal | Nenhuma | **Sem drift.** Mede a taxa de falso positivo do detector |
| **M02** | Inflação começa | `BILL_AMT*` × 1,10 | Drift leve em `BILL_AMT*` (atenção) |
| **M03** | Novos perfis + inflação | Reamostragem: mais `AGE` < 30 · `BILL_AMT*` × 1,25 | Drift moderado/crítico em `AGE` e `BILL_AMT*` |
| **M04** | Aperto de crédito | M03 + mais `PAY_0` ≥ 2 · `LIMIT_BAL` × 0,85 | Drift crítico em várias features e no score |
| **M05** | Concept drift puro | Features como M01; P(default) ↑ para alta utilização | **Sem drift de features**, queda de AUC/recall |
| **M06** | Crise | M04 + reetiquetagem de M05 | Tudo dispara |

Mais um **lote corrompido** (ver [DATA_CONTRACTS.md](DATA_CONTRACTS.md)), que deve ser
barrado antes de chegar aqui.

> ℹ️ As features escolhidas são **importantes para o modelo** — exigência do enunciado. A
> lista final sai do ranking de importância do baseline (Etapa 1). Se `AGE` ficar fora
> das features por decisão de viés, o drift de perfil é deslocado para outra feature
> relevante.

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

Com 2.400 linhas por lote contra ~15.000 de referência, o p-valor do KS rejeita H₀ para
diferenças **sem relevância prática**. Usar só `p < 0,05` geraria alerta em M01. Por isso:

- a decisão usa **PSI**, que mede tamanho de efeito
- o KS é reportado com a **estatística D**, não só o p-valor. ⚠️ O `ValueDrift(method="ks")`
  do Evidently 0.7 devolve **apenas o p-valor** (verificado na Etapa 0); a estatística D é
  calculada pelo projeto com `scipy.stats.ks_2samp` e registrada junto
- o lote M01 serve de calibração: se o KS dispara em M01, o limiar está errado

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
  Inflação ─────────► BILL_AMT* ↑ (nominal) ──┐
      │                                       ├──► score do modelo ──► decisão
      └──► capacidade de pagamento ↓ ──► PAY_* ↑ ──┘
                       │
                       └────────────────► inadimplência real ↑

  Novos perfis ─────► AGE ↓, LIMIT_BAL ↓ ──► score do modelo
```

### Método: intervenção, não correlação

Como a simulação é controlada, a causa verdadeira de cada degradação é **conhecida**. A
análise aplica cada perturbação **isoladamente** sobre o mesmo lote base e mede o efeito:

| Intervenção isolada | Δ PSI da feature | Δ AUC | Δ recall | Δ taxa de aprovação |
|--------------------|-----------------|-------|----------|---------------------|
| Só inflação nominal | 🟡 | 🟡 | 🟡 | 🟡 |
| Só novos perfis (reamostragem) | 🟡 | 🟡 | 🟡 | 🟡 |
| Só aperto (`PAY_0`, `LIMIT_BAL`) | 🟡 | 🟡 | 🟡 | 🟡 |
| Só concept drift | 🟡 | 🟡 | 🟡 | 🟡 |

**Perguntas que a tabela responde:**

1. Qual drift **causa** degradação e qual é inofensivo? (drift ≠ degradação)
2. O detector aponta para a causa verdadeira, ou para uma feature correlacionada?
3. Quanto da degradação é invisível ao monitoramento de features? (concept drift)

O resultado final — com a prescrição (retreinar, recalibrar, corrigir valores pela
inflação ou revisar a política) — vai para a seção de Análise Causal do README.

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
