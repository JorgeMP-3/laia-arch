# Control Center TUI v2 — Textual Modular

## Metadata

- ID: `221`
- Slug: `agora-ctl-tui`
- Kind: `doc`
- Status: `active`
- Filename: `agora-ctl-tui.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:36:18.051338+00:00`
- Updated at: `2026-05-19T08:36:18.051338+00:00`
- Aliases: `agora-ctl-tui`

## Summary

TUI modular con Textual. 14 pestañas. Arquitectura cliente/screen/cache. Login modal, token JWT persistido en ~/.laia/admin-session.json.

## Body

# Control Center TUI v2 — Textual Modular

> &#x1F4C5; 2026-05-18 | 342 tests backend

## Proposito

Interfaz de terminal para administrar AGORA. Reemplaza la version curses con Textual,
un framework Python moderno para TUIs.

## Archivos

| Archivo | Rol |
|---------|-----|
| `ctl/app.py` | App principal: login, tabs, navegacion |
| `ctl/client.py` | Cliente HTTP async a AGORA Backend |
| `ctl/cache.py` | Cache de respuestas API |
| `ctl/screens/base.py` | Mixin base para pantallas con poll |
| `ctl/tests/test_cache.py` | Tests unitarios del cache |

## 14 pestañas

| # | Pestana | Contenido |
|---|---------|-----------|
| 1 | Dashboard | Resumen general |
| 2 | Users | Lista de usuarios + agentes |
| 3 | Containers | Estado LXD |
| 4 | Jobs | Jobs async (provision, rebuild) |
| 5 | Logs | journalctl |
| 6 | Audit | Tool calls auditados |
| 7 | Errors | Errores recientes |
| 8 | System | OAuth refresh, restart, fixes |
| 9 | Marketplace | Plugins/skills pending + catalog |
| 10 | Areas | Agent areas (soul/instrucciones) |
| 11 | Cost | Usage ledger + presupuesto |
| 12 | LAIA | Chat con LAIA coordinator |
| 13 | Scheduled | Tareas programadas |
| 14 | Childruns | Ejecuciones hijas |

## Login

- Modal (`LoginModal`) con username/password
- Token JWT persistido en `~/.laia/admin-session.json`
- Compatible con el TUI curses legacy (mismo archivo de sesion)

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Control Center TUI v2 — Textual Modular

# Control Center TUI v2 — Textual Modular

> &#x1F4C5; 2026-05-18 | 342 tests backend

## Proposito

Interfaz de terminal para administrar AGORA. Reemplaza la version curses con Textual,
un framework Python moderno para TUIs.

## Archivos

| Archivo | Rol |
|---------|-----|
| `ctl/app.py` | App principal: login, tabs, navegacion |
| `ctl/client.py` | Cliente HTTP async a AGORA Backend |
| `ctl/cache.py` | Cache de respuestas API |
| `ctl/screens/base.py` | Mixin base para pantallas con poll |
| `ctl/tests/test_cache.py` | Tests unitarios del cache |

## 14 pestañas

| # | Pestana | Contenido |
|---|---------|-----------|
| 1 | Dashboard | Resumen general |
| 2 | Users | Lista de usuarios + agentes |
| 3 | Containers | Estado LXD |
| 4 | Jobs | Jobs async (provision, rebuild) |
| 5 | Logs | journalctl |
| 6 | Audit | Tool calls auditados |
| 7 | Errors | Errores recientes |
| 8 | System | OAuth refresh, restart, fixes |
| 9 | Marketplace | Plugins/skills pending + catalog |
| 10 | Areas | Agent areas (soul/instrucciones) |
| 11 | Cost | Usage ledger + presupuesto |
| 12 | LAIA | Chat con LAIA coordinator |
| 13 | Scheduled | Tareas programadas |
| 14 | Childruns | Ejecuciones hijas |

## Login

- Modal (`LoginModal`) con username/password
- Token JWT persistido en `~/.laia/admin-session.json`
- Compatible con el TUI curses legacy (mismo archivo de sesion)
