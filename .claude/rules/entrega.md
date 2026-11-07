# Regras de Entrega, Reprodutibilidade e Avaliação

Derivadas das avaliações dos três Tech Challenges anteriores. Cada regra diz de onde veio.

## 1. O avaliador precisa conseguir rodar — e ver sem rodar

> **TC01 — nota 63.** *"Não consegui testar localmente seguindo o que está no Readme (...)
> O comando `task` teria como premissa um arquivo Taskfile, que não estava no
> repositório."* O código estava bom; a nota caiu porque nada pôde ser validado.

- Nenhum comando no README sem existir no repo e ter sido executado **num clone limpo**.
- Um único runner: `uv run`. Sem Makefile, Taskfile, `task`, aliases ou scripts locais
  não versionados. O professor pode estar no Windows, sem `make`.
- Ao fechar cada etapa: clonar o repo em diretório temporário e executar a seção "Como
  Executar" do README do início ao fim, sem nenhum passo extra.
- O CI executa os mesmos comandos do README (pipeline fim a fim), não uma versão paralela.
- Dataset baixado por script. O Home Credit exige conta no Kaggle **e** aceite das regras
  da competição: o README explica isso antes do primeiro comando, o script falha com
  mensagem clara (não com stack trace) se faltar credencial ou aceite, e existe fallback
  sintético com o mesmo esquema — que prova que o pipeline roda, não as métricas. O TC03
  usou dataset do Kaggle com esse mesmo arranjo e tirou 90.
- Evidências (`reports/*.html`, `docs/MODEL_CARD.md`) **versionadas**: se mesmo assim o
  avaliador não conseguir rodar, ele consegue ver o resultado.
- `scripts/verify_setup.py`: um comando que diz se o ambiente está pronto e o que falta.

## 2. Model Card versionado e preenchido

> **TC02 — nota 85.** *"Não achei Model Card no repo, o que puxou um pouco a nota de
> documentação pra baixo."*

- Model Card mora em `docs/MODEL_CARD.md` (nunca em `models/`, que é ignorado pelo Git).
- Critério de aceite: `git ls-files docs/MODEL_CARD.md` retorna o arquivo e ele não tem
  placeholders.

## 3. O que manter do que funcionou

> **TC02 — 85:** checklist de etapas no README e script de validação de ambiente;
> comparação de modelos além do óbvio; código fácil de estender.
> **TC03 — 90:** auditoria contra vazamento de dados, decisões fundamentadas em números
> reais (reprovou o modelo sugerido pelo enunciado com benchmark), validação no CI,
> ambiente publicado opcional.

- Tabela de **conformidade item a item com o enunciado** em `docs/ROADMAP.md`, atualizada
  a cada etapa.
- Decisões registradas como ADR em `docs/ARQUITETURA.md`, com alternativas descartadas e
  o motivo honesto (não racionalizar).
- Números no README e no Model Card vêm de execução real, com o arquivo de origem citado.
  Nunca estimados.
- Ressalvas metodológicas declaradas onde o leitor as encontra: README, Model Card e
  roteiro do vídeo. Aqui a principal é: **o drift é simulado**.
- Baseline de comparação honesto: Dummy + modelo linear + modelo de árvore, no mesmo split.
- Checagem de vazamento: o pool de produção nunca toca o treino (teste automatizado).

## 4. Requisitos do enunciado que viram regra

- Mínimo de **5.000 amostras** no dataset. German Credit (1.000) **não serve**; o
  escolhido é o Home Credit (~307.500).
- Pelo menos **3 regras rígidas** no contrato; o lote ruim precisa ser **bloqueado**, não
  só reportado.
- Pelo menos **2 variáveis importantes** com drift intencional.
- Teste estatístico **PSI ou KS** explícito no relatório.
- Governança LGPD (PII, base legal, retenção, vieses) e Causalidade **no README.md**.
- Vídeo STAR com **≤ 5 minutos**: cronometrar o ensaio antes de gravar.
- Histórico de commits semântico: commitlint desde o primeiro commit.

## 5. Fluxo de trabalho

- `main` protegida: toda mudança via branch `<tipo>/<descricao>` + Pull Request.
- Um PR por entrega de etapa (ou por bloco coeso), com squash e mensagem semântica.
- Ao fechar uma etapa: atualizar README (status + Como Executar), ROADMAP (checklist +
  conformidade) e `Última atualização`.
