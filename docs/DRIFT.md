# 📉 Simulação e Detecção de Drift

> Desenho dos lotes simulados, testes estatísticos, limiares e o método da análise causal.
> Implementação na Etapa 2, em `src/drift/`. Cenários declarados em
> `configs/drift_scenarios.yaml`.

> ✅ **Status: implementado (Etapa 2).** Intensidades calibradas no dado real e
> resultados em [Resultados](#-resultados). Decisões de desenho no
> [ADR 14](ARQUITETURA.md#-decisão-14--desenho-da-simulação-de-drift). A análise causal por
> intervenção isolada está implementada em `src/pipeline/causal.py`.
>
> ⚠️ **O drift é simulado.** Os lotes saem do pool de produção do próprio dataset, com
> perturbações declaradas. Os rótulos de cada lote são revelados no próprio lote, o que
> encurta o atraso real de meses entre a decisão de crédito e a inadimplência.

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

Seis lotes mensais de 2.400 linhas do pool de produção, sem reposição dentro do lote e com
o **mesmo sorteio** em todos (ADR 14): a diferença entre dois lotes vem só do que o
cenário declara. Cenários em
[`configs/drift_scenarios.yaml`](../configs/drift_scenarios.yaml), aplicados nesta ordem:
reamostragem → reetiquetagem → escala.

| Lote | Narrativa | Perturbação | Esperado |
|------|----------|-------------|----------|
| **M01** | Mês normal | Nenhuma | **Sem alerta nesta execução.** Controle sem perturbação |
| **M02** | Inflação começa | `BILL_AMT*` × 1,10 | Sem alerta: o KS acusa pelo n grande, o PSI não |
| **M03** | Novos perfis + inflação | Peso 3 para `AGE` < 30 · `BILL_AMT*` × 1,25 | Atenção em `AGE` |
| **M04** | Aperto de crédito | M03 + peso 4 para `PAY_0` ≥ 2 · `LIMIT_BAL` × 0,85 | Drift em `AGE`, `LIMIT_BAL` e `PAY_0`, **sem** alerta de performance |
| **M05** | Concept drift puro | Features como M01; bons pagadores em dia com utilização ≥ 0,5 inadimplem com chance de 30% | **Sem drift de features**, queda de AUC/recall |
| **M06** | Crise | M04 + reetiquetagem de M05 | Drift de features; **sem** alerta de performance — a hipótese do desenho era o alerta, ver [Resultados](#-resultados) |

Mais um **lote corrompido** (ver [DATA_CONTRACTS.md](DATA_CONTRACTS.md)), barrado antes
de chegar aqui.

> ℹ️ As features com drift são **importantes para o modelo** — exigência do enunciado.
> Pela importância por permutação na validação: `PAY_0` 0,094 de AUC (1º), `BILL_AMT1`
> 0,031 (2º), `LIMIT_BAL` 0,016 (6º). A idade saiu do modelo (ADR 13) e é monitorada como
> atributo de população, fora da fração de features com drift.

---

## 📐 Testes estatísticos

O enunciado pede PSI ou Kolmogorov-Smirnov. **Os dois são configurados explicitamente**
no Evidently, coluna a coluna.

> ⚠️ **Não usar o stattest padrão.** Para amostras com mais de 1.000 linhas, o Evidently
> escolhe Wasserstein (numéricas) e Jensen-Shannon (categóricas) por padrão. Um relatório
> gerado sem configurar `stattest` **não** mostra PSI nem KS.

| Teste | Uso | Por quê |
|-------|-----|---------|
| **PSI** | **Decisão** de alerta | Mede a *magnitude* da mudança; padrão de mercado em risco de crédito; mede efeito, mas sua estimativa também varia entre amostras |
| **KS** | Confirmação | Estatística D mostra a maior distância entre as CDFs |
| PSI do score | Drift de predição | Detecta mudança na saída do modelo antes dos rótulos chegarem |

### ⚠️ KS e amostras grandes

Com 2.400 linhas por lote contra 4.495 de referência, o p-valor do KS rejeita H₀ para
diferenças **sem relevância prática**. Usar só `p < 0,05` geraria alerta em M01. Por isso:

- a decisão usa **PSI**, que mede tamanho de efeito
- o KS é reportado com a **estatística D**, não só o p-valor. ⚠️ O `ValueDrift(method="ks")`
  do Evidently 0.7 devolve **apenas o p-valor** (verificado na Etapa 0); a estatística D é
  calculada pelo projeto com `scipy.stats.ks_2samp` e registrada junto
- M01 é um controle desta simulação, não uma estimativa da taxa de falso positivo;
  rejeições isoladas do KS também podem ocorrer por acaso sob ausência de drift

> ℹ️ **Como o Evidently calcula o PSI.** Faixas de largura igual (regra de Sturges) sobre
> referência e lote juntos, não decis da referência. Em colunas monetárias de cauda longa
> isso o deixa um pouco menos sensível. Ficou assim para haver uma única implementação de
> PSI no projeto; o motivo e a medida estão no
> [ADR 03](ARQUITETURA.md#-decisão-3--evidently-com-psi-e-ks-explícitos).

### Janela de referência

Validação + teste da referência (4.495 linhas), não o treino: o modelo já viu o treino e
dá a ele scores otimistas. AUC de base na janela: **0,7495**; recall de inadimplentes
0,581; taxa de aprovação 0,724.

### Limiares

| Sinal | Atenção | Crítico |
|-------|---------|---------|
| PSI por feature | ≥ 0,10 | ≥ 0,25 |
| Fração de features com drift (PSI ≥ 0,10) | ≥ 20% | ≥ 50% |
| PSI do score | ≥ 0,10 | ≥ 0,25 |
| Queda de AUC-ROC vs. validação + teste | ≥ 0,03 | ≥ 0,05 |
| Queda de recall de inadimplentes | ≥ 0,05 | ≥ 0,10 |

Faixas de PSI seguem a convenção de mercado (< 0,10 estável; 0,10–0,25 mudança moderada;
> 0,25 mudança significativa). Os limiares vivem em `configs/pipeline.yaml`
(`monitoring.thresholds`), o mesmo lugar que os alertas da Etapa 3 leem. A fração de
features conta só as 19 features do modelo.

---

## 📊 Resultados

Dataset real, gerado por `uv run python scripts/run_drift_simulation.py`. Fonte:
[`reports/drift/drift_summary.json`](../reports/drift/drift_summary.json) (relatório HTML do
Evidently de cada lote em [`reports/drift/`](../reports/drift/)).

| Lote | Colunas com PSI ≥ 0,10 | PSI do score | AUC | Recall | Aprovação | Alertas | Como esperado? |
|------|------------------------|--------------|-----|--------|-----------|---------|----------------|
| Referência | — | — | 0,7495 | 0,581 | 0,724 | — | — |
| **M01** | nenhuma (maior: 0,011) | 0,009 | 0,7496 | 0,585 | 0,733 | nenhum | ✅ |
| **M02** | nenhuma (maior: 0,016) | 0,006 | 0,7489 | 0,583 | 0,730 | nenhum | ✅ |
| **M03** | `AGE` 0,152 | 0,011 | 0,7654 | 0,622 | 0,714 | atenção: `AGE` | ✅ |
| **M04** | `LIMIT_BAL` 0,227 · `PAY_0` 0,213 · `AGE` 0,193 | 0,128 | 0,7930 | 0,742 | 0,576 | atenção: 3 colunas e score | ✅ |
| **M05** | nenhuma (maior: 0,011) | 0,009 | 0,6821 | 0,462 | 0,733 | **crítico: AUC e recall** | ✅ |
| **M06** | `LIMIT_BAL` 0,227 · `PAY_0` 0,213 · `AGE` 0,193 | 0,128 | 0,7286 | 0,638 | 0,576 | atenção: 3 colunas e score | ⚠️ hipótese do desenho (alerta de performance) não confirmada; expectativa revista |

**O que os números dizem:**

1. **Não houve falso alerta no controle desta execução.** No M01 o maior PSI é 0,011 e
   a AUC é próxima à referência (0,7496 × 0,7495). Um lote/seed não demonstra ausência de
   falsos positivos em novas amostras. Não há avaliação sistemática de taxa de falsos
   alertas nem intervalos de confiança; os testes de reprodução verificam determinismo,
   não substituem validação estatística externa.
2. **KS acusa, PSI pesa.** No M02 o KS rejeita H₀ em todas as `BILL_AMT*` (p < 0,02), com D
   entre 0,039 e 0,052 e PSI de no máximo 0,016. A inflação é real e o modelo quase não sente (AUC
   0,7489). Alertar aqui seria ruído.
3. **Drift não é degradação.** No M04 três colunas e o score mudam, a taxa de aprovação cai
   de 0,724 para 0,576 — e a AUC **sobe** para 0,793, porque a carteira tem mais atrasados,
   que o modelo ordena com facilidade. O alerta certo é de negócio (aprovação), não de
   retreino. O contrato também avisou: W3 (atrasos acima de 1,5× a referência) em 678 linhas.
4. **Degradação silenciosa.** No M05 nenhuma feature e nem o score mudam (PSI ≤ 0,011), e a
   AUC cai 0,067, o recall 0,119. Só a performance com rótulo enxerga — meses depois.
5. **A mudança de população esconde o concept drift.** No M06 o concept drift do M05
   acontece numa carteira como a do M04. Contra a referência, a AUC cai só 0,021 e o recall
   **sobe**: nenhum alerta de performance. Contra a mesma carteira sem o concept drift
   (M04), a perda é de 0,064 de AUC e 0,104 de recall. O desenho previa alerta de
   performance aqui; a medição mostrou que não há, e o cenário **não foi recalibrado** para
   forçá-lo. A expectativa no YAML foi revista para o comportamento medido, com a hipótese
   original registrada ao lado, e um teste exige que a evidência versionada cumpra todas as
   expectativas. Comparar a performance com a linha de base agregada falha justamente na
   crise; a correção — comparar com a performance esperada para a carteira atual — entra
   na análise causal.

> ℹ️ Com uma seed por lote, a primeira versão acusou queda de AUC no M02 por ruído de
> amostragem (desvio-padrão de 0,012 em 2.400 linhas). Daí o mesmo sorteio em todos os
> lotes — ver [ADR 14](ARQUITETURA.md#-decisão-14--desenho-da-simulação-de-drift).

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

### Método: intervenções isoladas e efeitos medidos

`uv run python scripts/run_causal_ablation.py` lê as intervenções declaradas em
`configs/drift_scenarios.yaml`, fixa o seed 42 e compara cada lote com o controle M01. A
reamostragem muda a população por definição; os demais mecanismos usam o mesmo pool, seed,
tamanho e modelo. O relatório completo, com PSI e KS D por coluna, fica em
[`reports/drift/causal_ablation.json`](../reports/drift/causal_ablation.json); a leitura
visual está em [`notebooks/03_drift_analysis.ipynb`](../notebooks/03_drift_analysis.ipynb).

| Intervenção isolada | PSI/features driftadas | Δ AUC vs. M01 | Δ recall | Δ aprovação | Interpretação |
|--------------------|------------------------|--------------:|---------:|------------:|----------------|
| Inflação `BILL_AMT*` +10% | Nenhuma; PSI máx. 0,016 | −0,0007 | −0,0020 | −0,0021 | KS D nas faturas até 0,052, mas PSI e performance quase estáveis. |
| Mais jovens (reamostragem) | `AGE` (0,152) | +0,0142 | +0,0240 | −0,0079 | Mudança de população sem piora de discriminação. |
| Mais clientes em atraso (`PAY_0` ≥ 2) | `PAY_0` (0,221) | +0,0588 | +0,1573 | −0,1404 | Inadimplência +10,33 p.p.; discriminação melhora nesta carteira, aprovação cai. |
| Limite de crédito × 0,85 | `LIMIT_BAL` (0,108) | −0,0076 | −0,0233 | 0,0000 | Efeito pequeno na performance; taxa de inadimplência permanece estável. |
| Concept drift isolado | Nenhuma; PSI do score 0,009 | −0,0675 | −0,1225 | 0,0000 | Só a reetiquetagem reduz performance; features e scores permanecem estáveis. |

A intervenção de concept drift altera rótulos de clientes elegíveis com uma probabilidade
de 30%; não representa uma taxa observada no mundo real. Os deltas são uma observação em
uma amostra simulada, sem intervalos de confiança; não devem ser generalizados como efeito
causal de produção.

#### Interação M06: quando a população mascara o concept drift

M06 combina aperto e reetiquetagem. Contra M04 (mesma carteira sob aperto sem concept
drift), a AUC cai 0,0644 e o recall cai 0,1036. Contra M01, a AUC cai apenas 0,021 e o
recall sobe 0,0538: a maior proporção de inadimplentes fáceis de ordenar mascara a queda
na comparação agregada. Por isso M06 não dispara alerta de degradação baseado apenas no
baseline geral. O resultado revela um limite real da regra de monitoramento — não foi
recalibrado para forçar um alerta. Ver a análise e prescrição no
[README](../README.md#-análise-causal-da-degradação).

---

## 📂 Evidências

| Artefato | Onde |
|----------|------|
| Cenários | [`configs/drift_scenarios.yaml`](../configs/drift_scenarios.yaml) |
| Simulação e detecção | [`src/drift/`](../src/drift/), orquestração em [`src/pipeline/drift.py`](../src/pipeline/drift.py) |
| Resumo de todos os lotes (conferido byte a byte pelo CI) | [`reports/drift/drift_summary.json`](../reports/drift/drift_summary.json) |
| Relatório Evidently por lote (~5 MB cada; muda a cada execução) | `reports/drift/M01.html` … `M06.html` (versionados) |
| Contrato de cada lote | `reports/validation/M01.json` … `M06.json` |
| Execução por lote, com o HTML anexado | MLflow (`tc04-credit-scoring-monitoring`) |
| Análise | `notebooks/03_drift_analysis.ipynb` — fechamento da etapa |

> ℹ️ O GitHub mostra o código do HTML, não o relatório: baixe o arquivo e abra no
> navegador, ou abra a execução do lote no MLflow (aba *Artifacts → drift_report*).

---

**Última atualização:** 2026-11-17
