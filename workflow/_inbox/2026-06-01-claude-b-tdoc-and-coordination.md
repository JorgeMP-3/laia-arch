# Nota de coordinación — claude-b (Track T) → Minimax / Jorge

Fecha: 2026-06-01. Branch: `wip/claude-b/integrity-suite` (worktree
`/home/laia-arch/LAIA-wt-integrity-suite`).

## 1. T-DOC: gate de docstrings (coordinar con el gate de docs de Minimax)

He implementado **T-DOC** (Track T 4.7): un gate de docstrings en inglés para el
código de producción, dependency-free (stdlib `ast`), en
`tests/integration/lib/check_docstrings.py`, con patrón **baseline/ratchet**:

- Roots de producción: `services/agora-backend/app`, `services/laia-executor`,
  `infra/orchestrator`, `infra/pathd` (tests excluidos).
- Baseline: `tests/integration/docstrings-baseline.txt` (497 gaps pre-existentes).
  El gate **falla solo ante violaciones nuevas** no listadas → verde inmediato,
  deuda decreciente. Regenerar/encoger con `--write-baseline`.
- Detecta `missing` y `non-english` (heurística: caracteres/stopwords español).
- Corre en CI vía el job `integrity` (`run_integrity.sh --profile ci`).

**Si tu gate de docs (Minimax) hace algo equivalente**, propongo unificar sobre
este checker (interfaz estable: `--root`, `--baseline`, `--write-baseline`,
`--json`) para no tener dos gates que se pisen. Encaja con la migración
incremental de comentarios→inglés (C+Q del roadmap): cada vez que documentáis un
módulo, encoged el baseline.

Hallazgo suelto para tu cola: `services/agora-backend/tests/_laia_core.py` tiene
docstring en **español** (es código). Está fuera del scope del gate (es un test),
pero viola la política de docs-EN. Candidato a tu barrido.

## 2. Colisión de HEAD compartido en `~/LAIA` (acción para Jorge)

Varios agentes compartimos `~/LAIA` como working dir y **cambiáis de branch ahí**
(reflog lo confirma). Mientras yo trabajaba en `wip/claude-b/integrity-suite` en
ese dir, alguien hizo checkout a `wip/minimax/docs-and-qa`, y mi **primer commit
de T-DOC (`b232acb0`) aterrizó por error en la branch de minimax**; minimax
commiteó encima (`d7822e7c`).

- Lo **rehíce correctamente** en un worktree aislado (`wip/claude-b/integrity-suite`),
  vía cherry-pick. Mi branch está completa y verde.
- **No reescribí** la branch de minimax (estáis trabajando en ella). Resultado:
  `b232acb0` (mis 4 ficheros de T-DOC) sigue enterrado en `wip/minimax/docs-and-qa`.
  Al mergear ambos PRs habrá solape en `tests/integration/` (contenido idéntico →
  git lo resuelve trivial, o conflicto menor).

**Recomendación**: cada agente en **su propio worktree** (`git worktree add`), no
compartir el HEAD de `~/LAIA`. Y al revisar el PR de minimax, considerar dropear
`b232acb0` (o mergear mi PR primero y dejar que el de minimax sea no-op en esos
ficheros).
