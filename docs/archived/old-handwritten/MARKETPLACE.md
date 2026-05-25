# AGORA Marketplace — v0.1

> 📅 Actualizado: 2026-05-19

Plugins y skills compartibles entre usuarios de AGORA, con publicación
desde el área personal, revisión humana en el control center y carga
dinámica sin reconstruir la imagen LXD.

> **Estado v0.1.** Foundation operativa: DB schema + API + CLI + TUI admin
> + integración con AgentPool y forwarder. Falta UI agora-app (la rebuildea
> el usuario), sandboxing avanzado y aislamiento per-user concurrente.

## Modelo de capas (tiers)

| Capa | Origen | Visible para |
|---|---|---|
| **System** | `/opt/agora/app/.laia-core/plugins/` bundled en imagen | Todos, read-only |
| **Published** | `plugin_registry` con `status=approved` + `visibility=published` | Catálogo público |
| **Personal** | `plugin_registry` con `visibility=personal` | Solo el owner |

Mismo modelo para skills.

## Ciclo de vida

```
upload  → status=draft   visibility=personal     (solo owner)
publish → status=review  visibility=personal     (admin lo ve)
approve → status=approved visibility=published   (catálogo público)
reject  → status=rejected visibility=personal    (owner puede resubmit)
revoke  → status=rejected visibility=personal    (mismo, desde catálogo)
delete  → fila eliminada del registry            (sólo si no hay installs activos)
```

`install` añade una fila a `plugin_installs(user_id, plugin_id)` y dispara
`AgentPool.invalidate_user(user_id)`. La próxima vez que el usuario chatea,
`AgentPool.get_or_create` materializa los plugins instalados en
`/opt/agora/data/installed-plugins/<user_slug>/`, exporta
`LAIA_EXTRA_PLUGIN_DIRS` y `LAIA_FORWARDED_TOOLS_EXTRA`, fuerza
`discover_plugins(force=True)`, y construye un `AIAgent` que ya ve los
nuevos tools/skills.

## API

### Usuario

```
POST   /api/me/plugins/upload                   body: {slug, version, kind, blob_b64, forward_tools}
POST   /api/me/plugins/{id}/publish             status draft|rejected → review
DELETE /api/me/plugins/{id}                     409 si tiene installs activos
GET    /api/me/plugins                          lo mío (todo estado)
GET    /api/me/plugins/installs                 lo que tengo instalado
POST   /api/me/plugins/install                  body: {slug | plugin_id, version?, settings?}
DELETE /api/me/plugins/installs/{plugin_id}     uninstall

GET    /api/plugins/catalog                     published+approved

# Skills: simétrico bajo /api/me/skills/* y /api/skills/catalog.

GET    /api/user/llm-config                     incluye mcp_servers
PATCH  /api/user/llm-config                     mcp_servers: list | [] (clear) | null (unchanged)
```

### Admin (`role == agora_admin`)

```
GET    /api/admin/marketplace/pending           plugins + skills en review
POST   /api/admin/plugins/{id}/approve
POST   /api/admin/plugins/{id}/reject           body: {reason}
POST   /api/admin/plugins/{id}/revoke           body: {reason}    (catálogo → personal+rejected)
POST   /api/admin/skills/{id}/approve
POST   /api/admin/skills/{id}/reject            body: {reason}
```

## Crear un plugin

Estructura mínima dentro del área personal del usuario (host o container):

```
hello-mp/
  plugin.yaml      # slug:, version:, kind: (standalone|backend|exclusive)
  __init__.py      # def register(ctx): ctx.register_tool(...)
```

El loader carga el `__init__.py` como `laia_plugins.<slug_normalizado>` y
llama `register(ctx)`. La API de `ctx` es la misma que para plugins
bundled — `ctx.register_tool`, `ctx.register_hook`, `ctx.register_skill`,
etc. Ver `.laia-core/laia_cli/plugins.py:211` (`PluginContext`).

## Crear una skill personal

Skills v0.1 son un único archivo markdown con frontmatter YAML:

```markdown
---
name: my-skill
description: ...
---
# Detalle / instrucciones para el agente
```

Subir con `infra/dev/laia-marketplace.py --slug X skill publish ./my-skill.md --publish`.

## Flujo end-to-end

```bash
# 1. Crear plugin local
mkdir hello-mp && cd hello-mp
cat > plugin.yaml <<EOF
slug: hello-mp
version: 0.1.0
kind: standalone
EOF
cat > __init__.py <<'EOF'
def register(ctx):
    ctx.register_tool(
        "say_hello", "hello", {}, lambda **kw: "hola mundo desde marketplace"
    )
EOF
cd ..

# 2. Publicar como jorge-dev (state file aporta credentials)
infra/dev/laia-marketplace.py --slug jorge-dev plugin publish ./hello-mp --publish

# 3. Admin aprueba
python3 infra/dev/agora-control-center-tui.py
# Tab → Marketplace → Enter → 'a' aprobar

# 4. Otro usuario lo instala
AGORA_USERNAME=otro AGORA_PASSWORD=pw1234 \
  infra/dev/laia-marketplace.py plugin install hello-mp

# 5. El próximo turno de chat del usuario carga el plugin sin redeploy
bash infra/dev/smoke-test.sh --slug otro
```

## Tests

- `services/agora-backend/tests/test_marketplace_schema.py` (Fase A) — DB.
- `services/agora-backend/tests/test_marketplace.py` (Fase B) — API.
- `services/agora-backend/tests/test_marketplace_integration.py` (E+F).
- `services/agora-backend/tests/test_mcp_config.py` (Fase H) — MCP per-user.
- `tests/test_plugin_extra_dirs.py` (Fase D) — loader.
- `tests/test_marketplace_cli.sh` (Fase C) — CLI semantic check.

Lanzar:

```bash
cd services/agora-backend
PYTHONPATH=/home/laia-hermes/LAIA/.laia-core .venv/bin/pytest tests/ -q
# esperado: 224 passed

PYTHONPATH=/home/laia-hermes/LAIA/.laia-core \
  /home/laia-hermes/LAIA/services/agora-backend/.venv/bin/python \
  /home/laia-hermes/LAIA/tests/test_plugin_extra_dirs.py
bash /home/laia-hermes/LAIA/tests/test_marketplace_cli.sh
```

## Limitaciones v0.1

1. **Aislamiento per-user concurrente**: la materialización vía env vars
   serializa bajo el lock del AgentPool. Dos usuarios simultáneos
   construirán sus AIAgents secuencialmente, pero el `PluginManager`
   global recoge plugins distintos en cada construcción. Multi-user
   concurrente con distintos plugin sets es P1.
2. **Sandbox**: plugins aprobados ejecutan Python directo en
   `laia-agora`. Confianza por review humana.
3. **MCP** está expuesto como config persistente; la *ejecución* MCP
   depende del motor `.laia-core` (`tools/mcp_tool.py`). v0.1 no
   intercepta el chat para activar servers.
4. **Sin marketplace remoto**. `install` solo opera contra el catálogo
   local del cerebro. Importar desde GitHub es P1.

## Deploy

Los cambios v0.1 viven en el código del repo. Para que el container
`laia-agora` los ejecute hay que reconstruir la imagen:

```bash
sudo bash infra/lxd/scripts/rebuild-2-images.sh
sudo bash infra/lxd/scripts/rebuild-3-provision-agora.sh
sudo bash infra/lxd/scripts/rebuild-4-first-user.sh --slug jorge-dev
bash infra/dev/smoke-test.sh --slug jorge-dev
```

Las migraciones de schema corren automáticamente al boot (`ensure_schema`
en `database.py`); no hay paso manual.
