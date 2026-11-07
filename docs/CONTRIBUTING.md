# 🤝 Guia de Contribuição

> Como trabalhar neste repositório. Complementa o [COMMITLINT.md](COMMITLINT.md), que
> cobre o formato das mensagens de commit, e o [CLAUDE.md](../CLAUDE.md), que concentra as
> regras do projeto.

---

## 🌿 Fluxo de Branches

**Regra central:** `main` é protegida. Nenhuma alteração entra por commit direto — toda
mudança chega via **branch nova + Pull Request**.

```
main
 ├── docs/documentacao-inicial
 ├── feat/data-contracts
 ├── feat/drift-simulation
 ├── feat/monitoring-mlflow
 └── ci/workflow-lint-test
```

### Nomenclatura

```
<tipo>/<descricao-curta-em-kebab-case>
```

| Prefixo | Quando usar |
|---------|-------------|
| `feat/` | Nova funcionalidade |
| `fix/` | Correção de bug |
| `docs/` | Apenas documentação |
| `ci/` | Pipelines e automações |
| `refactor/` | Reorganização sem mudança de comportamento |
| `test/` | Testes |
| `chore/` | Dependências, configuração, build |

---

## 🔄 Ciclo de Trabalho

```bash
git checkout main
git pull origin main
git checkout -b feat/nome-da-tarefa

# trabalhar e commitar seguindo o Conventional Commits
git commit -m "feat(contracts): add pandera schema for credit batches"

git push -u origin feat/nome-da-tarefa
# abrir Pull Request para a main
```

---

## 📥 Pull Requests

### Checklist antes de abrir

- [ ] A branch parte da `main` atualizada
- [ ] Commits seguem o [COMMITLINT.md](COMMITLINT.md)
- [ ] `uv run ruff check .` e `uv run ruff format --check .` passam
- [ ] `uv run pytest` passa
- [ ] **Todo comando novo no README foi executado num clone limpo**
- [ ] README, ROADMAP (checklist + conformidade) e docs afetados atualizados
- [ ] Nenhum dado bruto, credencial ou `.env` versionado
- [ ] Relatórios em `reports/` não contêm linhas individuais de clientes

### Descrição sugerida

```markdown
## O que muda
Descrição objetiva da alteração.

## Etapa relacionada
Etapa X — <nome> (ver docs/ROADMAP.md)

## Como testar
Comandos `uv run ...` para validar localmente.

## Notas
Decisões tomadas, limitações conhecidas ou pendências.
```

### Regras de merge

| Regra | Detalhe |
|-------|---------|
| Revisão | Ao menos 1 aprovação de outro integrante |
| CI | Workflow do GitHub Actions verde |
| Estratégia | `Squash and merge`, mantendo mensagem no padrão semântico |
| Limpeza | Deletar a branch após o merge |

---

## 🔐 Acesso ao Dataset (cada integrante)

O dataset **não** está no repositório e **não** pode ser repassado entre integrantes —
nem por Drive, S3 ou mensagem. Os termos de uso da competição condicionam o acesso a uma
conta com as regras aceitas. Motivo completo em
[README — Origem dos dados](../README.md#1-origem-dos-dados-e-termos-de-uso) e ADR 12.

| Passo | O que fazer |
|-------|-------------|
| 1 | Criar conta no Kaggle (o Kaggle pode pedir verificação de telefone para competições) |
| 2 | Aceitar as regras em [Home Credit Default Risk → Rules](https://www.kaggle.com/competitions/home-credit-default-risk/rules) |
| 3 | Gerar o **próprio** token em *Settings → API* |
| 4 | Definir a variável de ambiente `KAGGLE_API_TOKEN` (Windows: `setx KAGGLE_API_TOKEN "<token>"` e abrir um terminal novo) |
| 5 | Rodar o script de download (⬜ Etapa 0), que confere o SHA256 |

| ✅ Faça | ❌ Nunca |
|---------|----------|
| Usar o seu token, só em variável de ambiente | Compartilhar token, colar em chat, issue ou PR |
| Enquanto não tiver acesso, trabalhar com os dados sintéticos | Enviar o CSV ou lotes derivados para outro integrante |
| Publicar só agregados em `reports/` | Versionar qualquer arquivo de `data/` |

> ⚠️ Os lotes simulados e a quarentena também **derivam** do dataset original: valem as
> mesmas restrições do arquivo bruto.

---

## 🧰 Ambiente Local

| Ferramenta | Uso |
|-----------|-----|
| uv | Ambiente Python e dependências travadas |
| Git | Controle de versão |
| Node.js | Opcional — apenas Husky + commitlint |

> 🚧 Comandos de ambiente entram aqui quando `pyproject.toml` existir (Etapa 0).

> ⚠️ Não use `pip install -e ".[dev]"`: as dependências de desenvolvimento ficarão em
> `[dependency-groups]` (PEP 735), que o pip ignora silenciosamente.

---

## 🧾 Convenções de Código

| Item | Convenção |
|------|-----------|
| Idioma do código | Inglês (variáveis, funções, docstrings) |
| Idioma da documentação | Português |
| Formatação e lint | `ruff format` + `ruff check` |
| Testes | `pytest`, em `tests/` espelhando `src/` |
| Logs | structlog JSON; `print()` proibido em `src/` e `scripts/` |
| Seeds | 42 |
| Limiares e cenários | `configs/*.yaml`, nunca hardcoded |
| Segredos | `.env` — nunca no código |

Regras completas em [.claude/rules/code-quality.md](../.claude/rules/code-quality.md).

---

## 🚫 Nunca Versionar / ✅ Sempre Versionar

| Nunca | Sempre |
|-------|--------|
| `.env` | `uv.lock` |
| `data/` (bruto, referência, produção, quarentena) | `reports/` (evidências HTML) |
| `models/` (artefatos) | `docs/MODEL_CARD.md` |
| `mlflow.db`, `mlruns/`, `logs/` | `configs/*.yaml` |

---

**Última atualização:** 2026-11-07
