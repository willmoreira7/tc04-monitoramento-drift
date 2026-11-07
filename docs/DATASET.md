# 📦 Dataset

> Escolha do dataset, esquema, problemas conhecidos e a separação entre referência e
> produção.

> ✅ **Decisão:** UCI *Default of Credit Card Clients* (id 350), licença **CC BY 4.0**.
> Números conferidos no arquivo baixado em 2026-11-07 (SHA256 em
> [Proveniência](#-proveniência)).

---

## 🎯 Exigências do enunciado

- Classificação binária financeira (risco, crédito ou precificação)
- **Pelo menos 5.000 amostras**
- Público e tabular, onde a degradação econômica faça sentido prático

E uma exigência que o enunciado não escreve, mas o tema impõe: **o grupo precisa ter o
direito de usar os dados para esta finalidade**. Um projeto avaliado em governança não
pode começar violando os termos de uso do próprio dataset.

---

## ⚖️ Candidatos avaliados

| Dataset | Linhas | Termos de uso permitem este projeto? | Outros prós e contras | Veredito |
|---------|--------|-------------------------------------|----------------------|----------|
| German Credit | 1.000 | ✅ | **Abaixo do mínimo de 5.000** | ❌ Desqualificado |
| **Default of Credit Card Clients (UCI 350)** | **30.000** | ✅ **CC BY 4.0**: uso, adaptação e redistribuição com atribuição | Sem renda; scoring de comportamento de cartão | ✅ **Escolhido** |
| Home Credit Default Risk (Kaggle) | 307.511 | ❌ **Só para os fins da competição; proibido manipular os dados** | Mais rico (renda, emprego), mas inviável pelos termos | ❌ [Ver abaixo](#-por-que-não-o-home-credit) |
| Give Me Some Credit (Kaggle) | 150.000 | ⚠️ Regras de competição do Kaggle — mesmo risco do Home Credit | ~6,7% de positivos | ❌ |
| Credit Risk Dataset (Kaggle) | ~32.500 | ⚠️ Procedência e licença desconhecidas | `loan_grade` quase vaza o target | ❌ |
| Lending Club | ~2,2 milhões | ⚠️ Cópias não oficiais; a Lending Club não distribui mais | Enorme; vazamento pós-concessão | ❌ |

---

## 🚫 Por que não o Home Credit

O Home Credit Default Risk foi a primeira escolha do grupo e é um dos datasets sugeridos
no próprio enunciado. Chegamos a baixá-lo e conferir as anomalias. Ao ler as regras da
competição — que todo usuário aceita antes do download — encontramos duas cláusulas
incompatíveis com este projeto:

> **Regras específicas da competição** (substituem a regra geral 7.A):
> *"After your acceptance of these Rules, you may access and use the Competition Data
> **only for the purposes of the Competition**."*

> **Regra geral 7.B — Data Security:**
> *"You agree **not to manipulate the data** and not to use it for any other purpose other
> than to participate in the Competition."*
> *"You agree not to transmit, duplicate, publish, redistribute or otherwise provide or
> make available the Competition Data to any party not participating in the Competition."*

| Cláusula | Conflito com o projeto |
|----------|------------------------|
| Uso só para os fins da competição | O projeto é um trabalho acadêmico. A permissão genérica para *"academic research and education"* (regra 7.A) foi **substituída** pela regra específica |
| Proibido manipular os dados | O núcleo da Etapa 2 é **alterar a distribuição** dos dados para simular drift |
| Proibido disponibilizar a não participantes | O professor e parte do grupo não aceitaram as regras; nenhum lote derivado poderia ser mostrado |

**Decisão:** trocar de dataset e **eliminar a cópia local** do Home Credit. Mantê-la sem
finalidade permitida contrariaria os mesmos termos.

> 💡 **Lição de governança.** Ser "público" não é o mesmo que ser de uso livre. O dataset
> estava a um clique de distância, era sugerido pelo enunciado e é amplamente usado em
> cursos — e mesmo assim os termos não cobriam este uso. A verificação da licença passou a
> ser um passo obrigatório da escolha de dados (ADR 12 em [ARQUITETURA.md](ARQUITETURA.md)).

---

## ✅ Por que o UCI Default of Credit Card Clients

1. **Licença limpa.** CC BY 4.0 permite usar, **adaptar** (simular drift) e
   **redistribuir**, com uma única obrigação: atribuição. Não há conflito com nenhuma
   etapa do projeto.
2. **Reprodutibilidade sem atrito.** Download direto da UCI, sem conta e sem token. O
   avaliador e o CI baixam com um comando — a principal lição do TC01.
3. **Tamanho adequado.** 30.000 linhas comportam um split 50/50 e seis lotes mensais de
   2.500 linhas.
4. **Governança rica.** Traz sexo, escolaridade, estado civil e idade — a própria UCI os
   marca como atributos demográficos. Há diferença real de inadimplência entre sexos
   (24,2% × 20,8%), o que dá substância à auditoria de viés.
5. **Problemas de qualidade reais.** Códigos fora do dicionário em `EDUCATION` e
   `MARRIAGE`, e 35 linhas com conteúdo idêntico sob IDs diferentes.

### O custo da escolha

| Custo | Como lidamos |
|-------|--------------|
| **Não há renda nem emprego.** O enunciado cita "limites de renda" e "desemprego" como **exemplos** | Os equivalentes são `LIMIT_BAL` (limite concedido), faturas e pagamentos. A capacidade de pagamento é inferida, e isso é declarado no Model Card |
| É scoring de **comportamento** (cliente de cartão), não de concessão a novos proponentes | O monitoramento de carteira é exatamente o caso de uso de drift em crédito; a narrativa do README trata a revisão de limites e a manutenção do crédito |
| Dados de 2005, em dólar taiwanês (NT$) | Irrelevante para o objetivo (ciclo de sustentação); declarado no Model Card |
| `BILL_AMT1…6` muito correlacionadas (0,95 entre meses vizinhos) | Drift numa delas aparece em todas: o relatório agrupa as séries e a análise causal considera isso |

---

## 📋 Esquema

Fonte: [UCI Machine Learning Repository — id 350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients).
Clientes de cartão de crédito em Taiwan, histórico de abril a setembro de 2005.

O arquivo oficial `data.csv` usa nomes genéricos (`X1`…`X23`, `Y`). O loader renomeia
para os nomes do dicionário da UCI:

| Coluna original | Nome no projeto | Tipo | Domínio documentado | Papel |
|-----------------|-----------------|------|---------------------|-------|
| `ID` | `ID` | int | Único | Chave — **nunca** é feature |
| `X1` | `LIMIT_BAL` | int | > 0 (NT$) | Feature |
| `X2` | `SEX` | cat | 1 = masculino, 2 = feminino | Auditoria de viés — **fora do modelo** |
| `X3` | `EDUCATION` | cat | 1 pós, 2 universidade, 3 ensino médio, 4 outros | A decidir (ablação) |
| `X4` | `MARRIAGE` | cat | 1 casado, 2 solteiro, 3 outros | Auditoria de viés — **fora do modelo** |
| `X5` | `AGE` | int | anos | A decidir (ablação); contrato exige ≥ 18 |
| `X6`–`X11` | `PAY_0`, `PAY_2` … `PAY_6` | int | −1 pago em dia; 1…9 meses de atraso | Feature |
| `X12`–`X17` | `BILL_AMT1` … `BILL_AMT6` | int | Valor da fatura (pode ser negativo: crédito a favor) | Feature |
| `X18`–`X23` | `PAY_AMT1` … `PAY_AMT6` | int | ≥ 0, valor pago | Feature |
| `Y` | `default` | binário | 1 = inadimplente no mês seguinte | **Target** |

> ℹ️ Não existe `PAY_1` — a sequência original pula de `PAY_0` para `PAY_2`. Manter os
> nomes do dicionário evita confusão com a documentação da fonte.

### Perfil conferido

| Item | Valor |
|------|-------|
| Linhas × colunas | 30.000 × 25 |
| Inadimplência | 22,12% |
| Nulos | 0 |
| `AGE` | 21 a 79 anos |
| `LIMIT_BAL` | 10.000 a 1.000.000 |
| `PAY_*` | −2 a 8 |
| `BILL_AMT*` | −339.603 a 1.664.089 (1.930 clientes com alguma fatura negativa) |
| `PAY_AMT*` | 0 a 1.684.259 |

### Problemas conhecidos

| Problema | Ocorrência | Na referência (limpeza) | Em produção (contrato) |
|----------|-----------|-------------------------|------------------------|
| `EDUCATION` = 0, 5, 6 | 14 + 280 + 51 = 345 | Agrupar em 4 ("outros") | Bloqueia |
| `MARRIAGE` = 0 | 54 | Agrupar em 3 ("outros") | Bloqueia |
| Linhas idênticas com IDs diferentes | 35 | 🟡 Investigar na EDA (cadastro duplicado ou coincidência de perfis com valores zerados) | Aviso |
| `PAY_*` = −2 e 0 | Frequentes | Não documentados na fonte; interpretados como "sem consumo" e "crédito rotativo" | Aceitos no domínio [−2, 9] |
| `BILL_AMT*` negativos | 1.930 clientes | Crédito a favor; aceitos | Aceitos |
| Desbalanceamento | 22,12% | Split estratificado | — |

> 🔴 A limpeza da referência é código, aplicada **antes** do split, e cada alteração é
> contada e logada. O contrato de produção é mais estrito que a limpeza: lá, código fora do
> domínio é sinal de problema na origem, não algo a corrigir em silêncio.

---

## ✂️ Separação Referência × Produção

```
UCI (30.000 linhas, 22,12% inadimplentes)
 │  limpeza declarada
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

- Nenhum `ID` do pool de produção aparece na referência
- A taxa de inadimplência dos dois lados difere menos de 1 p.p. antes da simulação
- O lote M01 (controle, sem perturbação) não acusa drift

---

## 📥 Obtenção

| Passo | Detalhe |
|-------|---------|
| Download | `scripts/download_data.py` (⬜ Etapa 0) baixa `data.csv` da UCI — **sem conta, sem token** |
| Integridade | O script confere o SHA256 abaixo; se não bater, falha com mensagem clara |
| Fonte fora do ar | Gerador sintético com o mesmo esquema: valida o pipeline, não reproduz as métricas |

> ℹ️ A licença permitiria versionar o arquivo (2,9 MB) no repositório. Optamos por não
> versionar para manter uma única fonte oficial e o hash como contrato de integridade;
> se a UCI ficar instável, versionar passa a ser uma contingência permitida.

---

## 🔐 Proveniência

| Item | Valor |
|------|-------|
| Fonte | [UCI ML Repository, id 350](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) |
| Arquivo | `https://archive.ics.uci.edu/static/public/350/data.csv` |
| Licença | **CC BY 4.0** — uso, adaptação e redistribuição permitidos, com atribuição |
| Atribuição exigida | Yeh, I. (2009). *Default of Credit Card Clients* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C55S3H |
| Artigo de origem | Yeh, I. C., & Lien, C. H. (2009). *The comparisons of data mining techniques for the predictive accuracy of probability of default of credit card clients.* Expert Systems with Applications, 36(2). |
| Anonimização | Feita na fonte: sem nome, documento ou contato; `ID` é sequencial |
| SHA256 de `data.csv` | `45bcf4df62ff2e237a74eb155cabfb4bbbc171219a0637daef44fdad07503dd0` |
| Baixado em | 2026-11-07 |

---

**Última atualização:** 2026-11-07
