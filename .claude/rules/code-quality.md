# Regras de Qualidade de Código

Aplicar SEMPRE — ao escrever código novo e ao revisar código existente.

## Sem duplicação

- Extraia lógica repetida para funções antes de copiar código.
- Um único carregador de config, um único schema Pandera por conjunto, uma única função de
  cálculo de PSI. Notebook, script e CI chamam as **mesmas** funções de `src/`.
- Notebooks são registro de análise, nunca passo de build. A automação vive em `src/`.

## Separação de responsabilidades

- `src/contracts/` não importa de `src/models/`: o contrato valida dados, não conhece o modelo.
- `src/drift/` não treina modelo; recebe predições prontas.
- `scripts/` são finos: parseiam argumentos e chamam `src/`. Nenhuma regra de negócio em script.
- Seed global é definida no entrypoint, não dentro de funções de biblioteca.

## Configuração, não constante

- Limiares (PSI, KS, AUC mínimo, share de features com drift), splits e cenários de drift
  ficam em `configs/*.yaml`. Nunca hardcoded em dois lugares.
- Caminhos: sempre `Path(__file__).resolve().parent...` a partir de `src/config.py`.
  Nunca `Path.cwd()` nem caminho relativo solto.

## Logging e observabilidade

- structlog com saída JSON em `src/` e `scripts/`. Proibido `print()`.
- Todo estágio do pipeline loga: `stage`, `status` (`success`/`failed`/`blocked`),
  `rows_in`, `rows_out`, `duration_s`, `batch_id`. Esses campos alimentam a Etapa 3.
- Falha esperada (contrato reprovado) é `status=blocked` com exit code ≠ 0, não exceção
  engolida.

## Tipagem e documentação

- Type hints em toda função pública. Docstring Google style em funções públicas.
- Funções curtas e de uma responsabilidade; se passou de ~30 linhas, quebre.

## Testes

- `pytest` em `tests/`, espelhando `src/`.
- Todo contrato tem teste com lote válido (passa) **e** lote inválido (bloqueia).
- Todo cenário de drift tem teste: o lote de controle não acusa drift; o lote perturbado
  acusa nas features esperadas.
- Testes não dependem de rede: usam fixture pequena ou dados sintéticos.

## Simplicidade

- Sem classes ou funções sem uso — delete código morto.
- `zip(strict=True)` por padrão.
- Pydantic v2 (se usado): `model_config = ConfigDict(...)`, nunca `class Config:`.

## Antes de qualquer commit

- `uv run ruff check .` e `uv run ruff format --check .` sem erros.
- `uv run pytest` passando.
- Nenhum import sem uso, nenhum arquivo morto, nenhum dado ou `.env` versionado.
