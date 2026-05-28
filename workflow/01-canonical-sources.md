# Fuentes canónicas

## Orden de autoridad

1. **`~/LAIA/LAIA_ECOSYSTEM.md`** — documento canónico. Define qué es LAIA, su
   arquitectura, las reglas duras, el layout en disco, el contrato `laia-clone`, el
   roadmap. **Si cualquier otra fuente contradice este archivo, gana este archivo.**
2. **`~/.laia/workspaces/laia-ecosystem/workspace.db`** — base de conocimiento técnico
   exhaustivo. Cada nodo describe un subsistema con campos, endpoints, modelos Pydantic,
   tests. Útil para consulta profunda, no para definir qué es LAIA.
3. **`~/LAIA/docs/db-export/`** — export markdown de `workspace.db` (auto-regenerable).
   Mismo nivel canónico que la DB. Regenerar:
   `python3 scripts/sync-workspace-markdown.py --workspace laia-ecosystem --output-dir ~/LAIA/docs/db-export`.
4. **Código real** en `~/LAIA/` — verdad de implementación. Cuando hay duda sobre
   "cómo se hace X", leer el código gana sobre cualquier doc.
5. **`~/LAIA/docs/*.md` sueltos** (`ARCHITECTURE.md`, `API.md`, `INTEGRATIONS.md`, etc.)
   pueden estar desactualizados. **Verifica contra `LAIA_ECOSYSTEM.md` antes de creer.**

## Tabla "para X, lee Y"

| Necesito saber... | Lee... |
|---|---|
| Qué es LAIA, las entidades, las reglas | `LAIA_ECOSYSTEM.md` §1-§5 |
| Layout en disco (`/opt/laia`, `/srv/laia`, etc.) | `LAIA_ECOSYSTEM.md` §8 |
| Contrato `laia-clone` | `LAIA_ECOSYSTEM.md` §8.5-§8.7 |
| Detalle de Agent Areas, Soul, AgentPool, Forwarder, etc. | `docs/db-export/agora-*.md` |
| Endpoints concretos de la API admin | `docs/db-export/agora-control-center.md` |
| Cómo arrancar dev local | `Makefile` (autoritativo) + `workflow/02-how-to-work.md` |
| Cómo ejecutar el protocolo de ingeniería (FASE 1-4) | skills en `.claude/skills/` — ver `AGENTS.md` §Agent skills |
| Cómo usar git+GitHub en este repo (modelo, comandos, errores) | `workflow/git-github-guide.md` + `AGENTS.md` §Git workflow |
| Estado actual (qué se trabajó hoy) | `workflow/changelog.md` |
| Problemas conocidos sin resolver | `workflow/problems.md` |
| Planes en marcha | `workflow/plans/` |

## Anti-patterns

- **No** confíes en `README.md`, `ARCHITECTURE.md` ni cualquier `.md` viejo sin verificar.
- **No** confíes en docstrings sin contrastar con el código.
- **No** asumas que `git log` describe la INTENCIÓN — describe el cambio. La intención
  está en `workflow/plans/` y `LAIA_ECOSYSTEM.md`.
