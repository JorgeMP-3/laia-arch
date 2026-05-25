# docs/

Documentación de LAIA. Después del rediseño de 2026-05-25, este directorio contiene
**sólo material auto-generado o de referencia visual**. Toda la prosa hand-written que
vivía aquí se movió a `archived/old-handwritten/`.

## Qué hay aquí

| Item | Qué es |
|---|---|
| `db-export/` | Export markdown **auto-generado** desde `~/.laia/workspaces/laia-ecosystem/workspace.db`. Detalle técnico exhaustivo por nodo. **No editar** — se regenera con `scripts/sync-workspace-markdown.py` (la unidad systemd `laia-docs-sync.service` lo hace en watch). |
| `map.drawio`, `map.svg` | Mapa visual de la arquitectura. |
| `archived/` | Documentación archivada. Conservada para referencia histórica. NO consultar como fuente vigente. |

## Para entender LAIA

No leas `docs/` para entender el proyecto. Lee, en este orden:

1. **`~/LAIA/AGENTS.md`** — entry point operativo.
2. **`~/LAIA/LAIA_ECOSYSTEM.md`** — documento canónico (qué es LAIA).
3. **`~/LAIA/workflow/`** — cómo trabajar en el repo.
4. **`docs/db-export/`** — para detalle técnico específico de un subsistema.
