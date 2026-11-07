# 🎥 Roteiro do Vídeo STAR

> Duração máxima: **5 minutos** (critério de 15%). Cronometrar o ensaio antes de gravar.
> 🟡 Esqueleto — números entram depois das Etapas 2 e 3.

| Bloco | Tempo | Conteúdo exigido pelo enunciado |
|-------|-------|--------------------------------|
| **S**ituation | ~40 s | Risco da degradação silenciosa de modelos de crédito |
| **T**ask | ~40 s | Interceptar dados ruins, detectar drift, garantir compliance |
| **A**ction | ~2 min | Ferramentas de validação e observabilidade, simulação do drift, governança |
| **R**esult | ~1 min 30 s | Relatório apontando o drift, alertas gerados, lições aprendidas |

---

## S — Situation (~40 s)

Um modelo de crédito não quebra: ele continua respondendo enquanto erra. Inflação e novos
perfis de clientes mudam os dados; a inadimplência só aparece meses depois.

> 🎙️ **Dizer explicitamente:** o drift foi **simulado** sobre um dataset público. É isso
> que permite saber a causa verdadeira e verificar se os detectores acertam.

## T — Task (~40 s)

Três requisitos: barrar dados inválidos antes do modelo, detectar a mudança de
distribuição com teste estatístico, e documentar o tratamento de dados pessoais sob a LGPD.

## A — Action (~2 min)

- Contrato Pandera: mostrar o lote corrompido sendo **bloqueado** (quarentena, exit code)
- Simulação: os três mecanismos (perfil, inflação nominal, concept drift) e o lote de controle
- Evidently com PSI e KS: abrir o relatório de um lote com drift
- MLflow e dashboard: a série dos lotes M01…M06
- Governança: atributos excluídos, base legal (art. 7º, X), direito de revisão (art. 20)

## R — Result (~1 min 30 s)

- 🟡 Features com drift detectado e PSI de cada uma
- 🟡 M01 sem alarme falso
- 🟡 M05: painel de features verde, AUC caindo — a degradação silenciosa capturada
- 🟡 Resultado da análise causal: qual drift realmente degradou o modelo
- Lição: drift detectado não é sinônimo de retreinar
- Lição de governança: o Home Credit, sugerido pelo enunciado, foi descartado porque os
  termos limitam o uso aos fins da competição e proíbem manipular os dados — "público" não
  é "de uso livre" (~15 s, cabe também em Action)

## ✅ Checklist antes de gravar

- [ ] README aberto no roadmap das etapas
- [ ] Terminal pronto para rodar o lote corrompido ao vivo
- [ ] `reports/drift/` aberto no lote mais expressivo
- [ ] `reports/monitoring/dashboard.html` aberto
- [ ] Seção de Governança do README visível
- [ ] Ensaio cronometrado ≤ 4 min 45 s
- [ ] Fechar com a ressalva: projeto acadêmico, drift simulado

---

**Última atualização:** 2026-11-07
