# AGORA Marketplace v0.1 — Plugins, Skills y MCP

## Metadata

- ID: `209`
- Slug: `agora-marketplace`
- Kind: `doc`
- Status: `active`
- Filename: `agora-marketplace.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T12:01:07.558593+00:00`
- Updated at: `2026-05-19T11:13:52.677190`
- Aliases: `agora-marketplace`

## Summary

Marketplace para plugins, skills y configuraciones MCP. Backend en marketplace.py + marketplace_storage.py. CLI host-side. 26 tests nuevos (224 total). TUI pestaña 9.

## Body

# AGORA Marketplace v0.1

## Proposito

Sistema de publicacion, aprobacion, instalacion y materializacion de plugins, skills y configuraciones MCP para PA-AGORA.

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│ AGORA Backend (laia-agora)                          │
│                                                     │
│ marketplace.py          marketplace_storage.py      │
│ ┌─────────────────┐    ┌────────────────────────┐   │
│ │ /api/plugins/    │    │ CRUD plugins/skills/MCP │   │
│ │   catalog        │◄───│ publish/approve/reject  │   │
│ │ /api/me/plugins/ │    │ install/uninstall       │   │
│ │ /api/me/skills/  │    │ tarball validation      │   │
│ │ /api/admin/      │    │ per-user materialize    │   │
│ │   marketplace/   │    │                         │   │
│ └─────────────────┘    └────────────────────────┘   │
│                                                     │
│ agent_pool.py                                       │
│ _materialize_marketplace_for(user)                  │
│   -> extrae plugins/skills a dir del usuario        │
│   -> setea LAIA_EXTRA_PLUGIN_DIRS                   │
│   -> invalida sesion -> next request re-crea AIAgent│
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Host                                                │
│                                                     │
│ infra/dev/laia-marketplace.py (CLI)                 │
│   plugin publish <dir> --publish                    │
│   plugin install <slug>                             │
│   plugin uninstall <slug>                           │
│   skill publish <dir> --publish                     │
│   mcp publish <json-file>                           │
│                                                     │
│ TUI: agora-control-center-tui.py                    │
│   Pestana 9: Marketplace (a=approve, x=reject, v=view)│
└─────────────────────────────────────────────────────┘
```

## Endpoints

| Metodo | Ruta | Auth | Descripcion |
|--------|------|------|-------------|
| GET | /api/plugins/catalog | JWT | Catalogo publico de plugins aprobados |
| GET | /api/me/plugins | JWT | Plugins instalados por el usuario |
| POST | /api/me/plugins/install | JWT | Instalar plugin |
| DELETE | /api/me/plugins/{slug} | JWT | Desinstalar plugin |
| GET | /api/me/skills | JWT | Skills instalados por el usuario |
| POST | /api/me/skills/install | JWT | Instalar skill |
| DELETE | /api/me/skills/{slug} | JWT | Desinstalar skill |
| GET | /api/admin/marketplace/pending | Admin | Plugins/skills pendientes de aprobacion |
| POST | /api/admin/marketplace/{id}/approve | Admin | Aprobar plugin/skill |
| POST | /api/admin/marketplace/{id}/reject | Admin | Rechazar plugin/skill |

## Flujo de publicacion

1. Desarrollador crea plugin con plugin.yaml + __init__.py
2. CLI: laia-marketplace.py plugin publish hello-mp --publish
3. Backend valida tarball (plugin.yaml schema, __init__.py existe, sin path-traversal)
4. Plugin queda en estado "pending"
5. Admin abre TUI -> pestana 9 -> selecciona -> "a" para aprobar
6. Plugin queda en estado "approved" y aparece en /api/plugins/catalog
7. Usuario: laia-marketplace.py plugin install hello-mp
8. AgentPool._materialize_marketplace_for() extrae plugin a dir del usuario
9. LAIA_EXTRA_PLUGIN_DIRS apunta al dir -> AIAgent lo carga en la proxima request

## DB Schema (4 tablas nuevas)

plugins: id, slug, version, kind, manifest_json, tarball_b64, author_id, status (pending|approved|rejected), created_at
skills: id, slug, version, kind, manifest_json, tarball_b64, author_id, status, created_at
user_plugins: user_id, plugin_id, installed_at
user_skills: user_id, skill_id, installed_at
+ mcp_servers_json en users (config JSON para MCP)

## CLI host-side

infra/dev/laia-marketplace.py --slug jorge-dev <comando>:
- plugin publish <dir> --publish
- plugin install <slug>
- plugin uninstall <slug>
- skill publish <dir> --publish
- skill install <slug>
- mcp publish <json-file>

## Limitaciones v0.1

- Aislamiento per-user concurrente no garantizado (PluginManager es proceso-unico). OK para 1 usuario activo.
- Sin sandbox seccomp/AppArmor sobre codigo de plugin
- MCP guarda config; ejecucion via motor .laia-core existente
- Sin import remoto (GitHub) — P1

## Tests

26 tests nuevos (224 total backend):
- test_marketplace_schema.py: 6 tests Fase A
- test_marketplace.py: 13 tests Fase B (publish/approve/install lifecycle)
- test_marketplace_integration.py: 3 tests Fase E+F
- test_mcp_config.py: 4 tests Fase H
- test_marketplace_cli.sh: smoke CLI

## Bugs arreglados (post-v0.1)

### B1: Hardcoded path en tests (test_marketplace_integration.py)
El test `test_forwarder_reads_extra_tools_from_env` hardcodeaba ruta absoluta
del host `/home/laia-hermes/LAIA/.laia-core/...`. Dentro del container la ruta
es `/opt/agora/app/.laia-core/...`. Fix: escanear sys.path + fallback al layout
del repo.

### B2: Toolsets de plugins filtrados (agent_pool.py)
Las tools de plugins instalados se descubrian pero AGORA_ENABLED_TOOLSETS las
descartaba antes de exponerlas al LLM. Fix: `_materialize_marketplace_for()` ahora
devuelve `extra_toolsets` y `_build_aiagent()` los acumula dinamicamente.

### B3: Convencion de handlers (examples corrigidos)
Los handlers de plugins deben seguir la convencion de .laia-core/tools/registry.py:
- Signature: `def handler(args: dict, **kw) -> str`
- Return: un string (tipicamente `json.dumps()` de un dict resultado)
No `def handler(name=..., **kw) -> dict` como estaban los ejemplos iniciales.

## Convencion para desarrollar plugins

```python
# LAIA tool handler convention (see .laia-core/tools/registry.py):
#   - Signature: def handler(args: dict, **kw) -> str
#   - Return:    a string (often json.dumps of a result envelope)

import json

def _say_hello(args: dict | None = None, **_: object) -> str:
    args = args or {}
    name = str(args.get("name") or "mundo")
    return json.dumps({
        "ok": True,
        "result": f"hola {name} desde el marketplace AGORA 🚀",
        "source": "marketplace-hello@0.1.2",
    }, ensure_ascii=False)

def register(ctx) -> None:
    ctx.register_tool("say_hello", "hello", {...}, _say_hello)
```

## Ejemplos plantados

### marketplace-hello v0.1.2
Tool: `say_hello(name?)` - devuelve saludo personalizado.
Source: examples/marketplace/marketplace-hello/
Toolset: hello

### agora-now v0.1.2
Tool: `current_time()` - devuelve fecha/hora UTC+local sin bash.
Source: examples/marketplace/agora-now/
Toolset: clock

### marketplace-onboarding (skill)
Skill markdown que ensena al agente a explicar el marketplace.
Source: examples/marketplace/skills/marketplace-onboarding.md

Los tres aprobados, publicados e instalados para jorge-dev.
Persisten entre rebuilds en /srv/laia/agora/plugin-store/ y skill-store/.

## Estructura del container laia-agora

```
/opt/agora/
├── app/                         ← codigo (imagen)
│   ├── .laia-core/              ← motor + plugins bundled
│   │   ├── plugins/agora-executor-forwarder/
│   │   └── tools/registry.py
│   ├── services/agora-backend/  ← backend FastAPI
│   │   ├── app/main.py
│   │   ├── app/marketplace.py
│   │   ├── app/marketplace_storage.py
│   │   ├── app/agent_pool.py
│   │   └── app/admin.py
│   ├── services/laia-executor/  ← executor (tests)
│   └── workspace_store/
├── venv/                        ← Python venv
└── data/                        ← bind mount /srv/laia/agora/
    ├── agora.db
    ├── auth.json (symlink ro)
    ├── plugin-store/
    ├── skill-store/
    ├── installed-plugins/{user}/
    └── installed-skills/{user}/
```

## Comandos utiles para inspeccionar

```bash
# Listar codigo
lxc exec laia-agora -- ls /opt/agora/app/services/agora-backend/app
# Ver archivo
lxc exec laia-agora -- cat /opt/agora/app/.../marketplace.py
# Shell interactivo
lxc exec laia-agora -- bash
# Logs
lxc exec laia-agora -- journalctl -u agora-backend -n 50
# Copiar al host
lxc file pull laia-agora/opt/agora/app/.../marketplace.py /tmp/m.py
```

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Marketplace v0.1 — Plugins, Skills y MCP

# AGORA Marketplace v0.1

## Proposito

Sistema de publicacion, aprobacion, instalacion y materializacion de plugins, skills y configuraciones MCP para PA-AGORA.

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│ AGORA Backend (laia-agora)                          │
│                                                     │
│ marketplace.py          marketplace_storage.py      │
│ ┌─────────────────┐    ┌────────────────────────┐   │
│ │ /api/plugins/    │    │ CRUD plugins/skills/MCP │   │
│ │   catalog        │◄───│ publish/approve/reject  │   │
│ │ /api/me/plugins/ │    │ install/uninstall       │   │
│ │ /api/me/skills/  │    │ tarball validation      │   │
│ │ /api/admin/      │    │ per-user materialize    │   │
│ │   marketplace/   │    │                         │   │
│ └─────────────────┘    └────────────────────────┘   │
│                                                     │
│ agent_pool.py                                       │
│ _materialize_marketplace_for(user)                  │
│   -> extrae plugins/skills a dir del usuario        │
│   -> setea LAIA_EXTRA_PLUGIN_DIRS                   │
│   -> invalida sesion -> next request re-crea AIAgent│
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Host                                                │
│                                                     │
│ infra/dev/laia-marketplace.py (CLI)                 │
│   plugin publish <dir> --publish                    │
│   plugin install <slug>                             │
│   plugin uninstall <slug>                           │
│   skill publish <dir> --publish                     │
│   mcp publish <json-file>                           │
│                                                     │
│ TUI: agora-control-center-tui.py                    │
│   Pestana 9: Marketplace (a=approve, x=reject, v=view)│
└─────────────────────────────────────────────────────┘
```

## Endpoints

| Metodo | Ruta | Auth | Descripcion |
|--------|------|------|-------------|
| GET | /api/plugins/catalog | JWT | Catalogo publico de plugins aprobados |
| GET | /api/me/plugins | JWT | Plugins instalados por el usuario |
| POST | /api/me/plugins/install | JWT | Instalar plugin |
| DELETE | /api/me/plugins/{slug} | JWT | Desinstalar plugin |
| GET | /api/me/skills | JWT | Skills instalados por el usuario |
| POST | /api/me/skills/install | JWT | Instalar skill |
| DELETE | /api/me/skills/{slug} | JWT | Desinstalar skill |
| GET | /api/admin/marketplace/pending | Admin | Plugins/skills pendientes de aprobacion |
| POST | /api/admin/marketplace/{id}/approve | Admin | Aprobar plugin/skill |
| POST | /api/admin/marketplace/{id}/reject | Admin | Rechazar plugin/skill |

## Flujo de publicacion

1. Desarrollador crea plugin con plugin.yaml + __init__.py
2. CLI: laia-marketplace.py plugin publish hello-mp --publish
3. Backend valida tarball (plugin.yaml schema, __init__.py existe, sin path-traversal)
4. Plugin queda en estado "pending"
5. Admin abre TUI -> pestana 9 -> selecciona -> "a" para aprobar
6. Plugin queda en estado "approved" y aparece en /api/plugins/catalog
7. Usuario: laia-marketplace.py plugin install hello-mp
8. AgentPool._materialize_marketplace_for() extrae plugin a dir del usuario
9. LAIA_EXTRA_PLUGIN_DIRS apunta al dir -> AIAgent lo carga en la proxima request

## DB Schema (4 tablas nuevas)

plugins: id, slug, version, kind, manifest_json, tarball_b64, author_id, status (pending|approved|rejected), created_at
skills: id, slug, version, kind, manifest_json, tarball_b64, author_id, status, created_at
user_plugins: user_id, plugin_id, installed_at
user_skills: user_id, skill_id, installed_at
+ mcp_servers_json en users (config JSON para MCP)

## CLI host-side

infra/dev/laia-marketplace.py --slug jorge-dev <comando>:
- plugin publish <dir> --publish
- plugin install <slug>
- plugin uninstall <slug>
- skill publish <dir> --publish
- skill install <slug>
- mcp publish <json-file>

## Limitaciones v0.1

- Aislamiento per-user concurrente no garantizado (PluginManager es proceso-unico). OK para 1 usuario activo.
- Sin sandbox seccomp/AppArmor sobre codigo de plugin
- MCP guarda config; ejecucion via motor .laia-core existente
- Sin import remoto (GitHub) — P1

## Tests

26 tests nuevos (224 total backend):
- test_marketplace_schema.py: 6 tests Fase A
- test_marketplace.py: 13 tests Fase B (publish/approve/install lifecycle)
- test_marketplace_integration.py: 3 tests Fase E+F
- test_mcp_config.py: 4 tests Fase H
- test_marketplace_cli.sh: smoke CLI

## Bugs arreglados (post-v0.1)

### B1: Hardcoded path en tests (test_marketplace_integration.py)
El test `test_forwarder_reads_extra_tools_from_env` hardcodeaba ruta absoluta
del host `/home/laia-hermes/LAIA/.laia-core/...`. Dentro del container la ruta
es `/opt/agora/app/.laia-core/...`. Fix: escanear sys.path + fallback al layout
del repo.

### B2: Toolsets de plugins filtrados (agent_pool.py)
Las tools de plugins instalados se descubrian pero AGORA_ENABLED_TOOLSETS las
descartaba antes de exponerlas al LLM. Fix: `_materialize_marketplace_for()` ahora
devuelve `extra_toolsets` y `_build_aiagent()` los acumula dinamicamente.

### B3: Convencion de handlers (examples corrigidos)
Los handlers de plugins deben seguir la convencion de .laia-core/tools/registry.py:
- Signature: `def handler(args: dict, **kw) -> str`
- Return: un string (tipicamente `json.dumps()` de un dict resultado)
No `def handler(name=..., **kw) -> dict` como estaban los ejemplos iniciales.

## Convencion para desarrollar plugins

```python
# LAIA tool handler convention (see .laia-core/tools/registry.py):
#   - Signature: def handler(args: dict, **kw) -> str
#   - Return:    a string (often json.dumps of a result envelope)

import json

def _say_hello(args: dict | None = None, **_: object) -> str:
    args = args or {}
    name = str(args.get("name") or "mundo")
    return json.dumps({
        "ok": True,
        "result": f"hola {name} desde el marketplace AGORA 🚀",
        "source": "marketplace-hello@0.1.2",
    }, ensure_ascii=False)

def register(ctx) -> None:
    ctx.register_tool("say_hello", "hello", {...}, _say_hello)
```

## Ejemplos plantados

### marketplace-hello v0.1.2
Tool: `say_hello(name?)` - devuelve saludo personalizado.
Source: examples/marketplace/marketplace-hello/
Toolset: hello

### agora-now v0.1.2
Tool: `current_time()` - devuelve fecha/hora UTC+local sin bash.
Source: examples/marketplace/agora-now/
Toolset: clock

### marketplace-onboarding (skill)
Skill markdown que ensena al agente a explicar el marketplace.
Source: examples/marketplace/skills/marketplace-onboarding.md

Los tres aprobados, publicados e instalados para jorge-dev.
Persisten entre rebuilds en /srv/laia/agora/plugin-store/ y skill-store/.

## Estructura del container laia-agora

```
/opt/agora/
├── app/                         ← codigo (imagen)
│   ├── .laia-core/              ← motor + plugins bundled
│   │   ├── plugins/agora-executor-forwarder/
│   │   └── tools/registry.py
│   ├── services/agora-backend/  ← backend FastAPI
│   │   ├── app/main.py
│   │   ├── app/marketplace.py
│   │   ├── app/marketplace_storage.py
│   │   ├── app/agent_pool.py
│   │   └── app/admin.py
│   ├── services/laia-executor/  ← executor (tests)
│   └── workspace_store/
├── venv/                        ← Python venv
└── data/                        ← bind mount /srv/laia/agora/
    ├── agora.db
    ├── auth.json (symlink ro)
    ├── plugin-store/
    ├── skill-store/
    ├── installed-plugins/{user}/
    └── installed-skills/{user}/
```

## Comandos utiles para inspeccionar

```bash
# Listar codigo
lxc exec laia-agora -- ls /opt/agora/app/services/agora-backend/app
# Ver archivo
lxc exec laia-agora -- cat /opt/agora/app/.../marketplace.py
# Shell interactivo
lxc exec laia-agora -- bash
# Logs
lxc exec laia-agora -- journalctl -u agora-backend -n 50
# Copiar al host
lxc file pull laia-agora/opt/agora/app/.../marketplace.py /tmp/m.py
```
