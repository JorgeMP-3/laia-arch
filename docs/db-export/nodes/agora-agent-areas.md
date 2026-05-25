# AGORA Agent Areas — Identidad Centralizada del Agente

## Metadata

- ID: `210`
- Slug: `agora-agent-areas`
- Kind: `doc`
- Status: `active`
- Filename: `agora-agent-areas.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T16:10:02.353730+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `agora-agent-areas`

## Summary

Tabla agent_areas en agora.db. Soul, instrucciones, preferencias y nombre del agente viven en AGORA (no en el container). APIs /api/me/agent-area, hardening con max_length y auto-create. 237 tests.

## Body

# AGORA Agent Areas — Identidad Centralizada del Agente

> 📅 Documentado: 2026-05-18 | 237 tests verdes

## Proposito

La identidad del agente (nombre, personalidad, instrucciones, preferencias de comportamiento
y memoria) se **centraliza** en AGORA. El container del usuario (`agent-<slug>`) queda como
executor puro: archivos, procesos, workspace tecnico privado. El soul no esta en el container.

## DB: agent_areas

```sql
CREATE TABLE agent_areas (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    agent_display_name TEXT,         -- nombre visible: "Nombrix", "MariaBot"
    soul_md TEXT,                     -- personalidad del agente (markdown, max 50K)
    instructions_md TEXT,             -- instrucciones operativas (markdown, max 50K)
    memory_preferences_json TEXT,     -- preferencias de memoria (JSON)
    behavior_preferences_json TEXT,   -- comportamiento: tone, language, etc (JSON)
    created_at TEXT,
    updated_at TEXT
);
```

## APIs REST

### Usuario (requiere JWT del propio usuario)

| Metodo | Ruta | Auth | Descripcion |
|--------|------|------|-------------|
| `GET` | `/api/me/agent-area` | JWT | Leer area completa. **Auto-crea** con defaults vacios si no existe (nunca 404) |
| `PATCH` | `/api/me/agent-area` | JWT | Editar campos: `agent_display_name`, `soul_md`, `instructions_md`, `memory_preferences`, `behavior_preferences` |
| `GET` | `/api/me/agent-area/plugins` | JWT | Plugins instalados por este usuario |
| `GET` | `/api/me/agent-area/skills` | JWT | Skills instaladas por este usuario |
| `GET` | `/api/me/agent-area/memory` | JWT | Preferencias de memoria configuradas |

### Admin (requiere rol `agora_admin`)

| Metodo | Ruta | Auth | Descripcion |
|--------|------|------|-------------|
| `GET` | `/api/admin/users/<built-in function id>/agent-area` | Admin JWT | Leer area de cualquier usuario |
| `PATCH` | `/api/admin/users/<built-in function id>/agent-area` | Admin JWT | Editar area de cualquier usuario |

### Compatibilidad legacy

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/api/agent/profile` | Lee de `agent_areas` en vez del executor. Mismo formato respuesta: `{persona, instructions, skills, preferences}` |

## Integracion con AgentPool

Cuando el usuario inicia un chat:

1. `AgentPool.get_or_create()` llama a `agent_area_for_user(user_id)`
2. Lee `soul_md`, `instructions_md`, `agent_display_name`, `behavior_preferences_json`
3. Construye `ephemeral_system_prompt`:
   ```
   [Soul]
   Soy Nombrix, el PA-AGORA de Jorge.
   
   [Instructions]
   Responde en espanol claro y directo.
   
   [Preferences]
   tone: directo
   language: es
   ```
4. Lo pasa al constructor de `AIAgent` → el LLM lo ve como prompt del sistema
5. Si el usuario edita su area → `AgentPool.invalidate_user(user_id)` → la siguiente
   peticion reconstruye el AIAgent con el nuevo soul

## End-to-end: configurar la identidad

```bash
# Leer area actual
laia-marketplace.py --slug jorge-dev agent-area get

# Poner nombre visible
laia-marketplace.py --slug jorge-dev agent-area set-name "Nombrix"

# Poner soul desde archivo markdown
laia-marketplace.py --slug jorge-dev agent-area set-soul ./mi-soul.md

# O poner soul directamente como texto
laia-marketplace.py --slug jorge-dev agent-area set-soul "Soy Nombrix, PA-AGORA de Jorge."

# Poner instrucciones
laia-marketplace.py --slug jorge-dev agent-area set-instructions "Responde en espanol claro y directo."

# Configurar preferencias
laia-marketplace.py --slug jorge-dev agent-area set-pref tone directo
laia-marketplace.py --slug jorge-dev agent-area set-pref language es --scope memory

# Ver en la TUI
python3 infra/dev/agora-control-center-tui.py   # Tab → pestana 10 "Areas"

# Ver via API
curl -s http://127.0.0.1:8088/api/me/agent-area \
  -H "Authorization: Bearer $TOKEN" | jq .
```

## Hardening (Fases 1-4, Mayo 2026)

### F1 — Seguridad P0

| Campo | Validacion | Motivo |
|-------|-----------|--------|
| `soul_md` | `max_length=50_000` | Previene DoS: un cliente podia meter MB de markdown y AgentPool lo lee en cada construccion de AIAgent |
| `instructions_md` | `max_length=50_000` | Idem |
| `agent_display_name` | `min_length=1, max_length=80` | Consistencia |
| GET auto-create | Si el area no existe, se crea con defaults vacios | Evita 404 en primer acceso. Consistente con PATCH que ya auto-creaba |

### F2 — Consistencia naming agent-*

| Archivo | Cambio |
|---------|--------|
| `admin.py:716` | `f"laia-{slug}"` → `candidate_container_names()` |
| `orchestrator/lxd.py` | Documentada duplicacion intencional con comment |
| `rebuild-4-first-user.sh` | Destruye legacy `laia-<slug>` al crear nuevo (salvo `--keep-legacy`) |
| `rebuild-1-cleanup.sh` | Limpia `agent-*` stray ademas de `laia-*` |
| `preflight.sh` | Detecta containers `agent-*`/`laia-*` sin state file → sugiere rebuild-state o delete |

### F3 — Tests combinados

Nuevo test `test_combined_marketplace_install_and_area_edit_pass_through_to_aiagent`:
1. Crea usuario + login
2. PATCH agent-area con soul custom
3. Publica + aprueba + instala plugin
4. Llama a `AgentPool.get_or_create()` (AIAgent mockeado)
5. Verifica que `ephemeral_system_prompt` contiene el soul
6. Verifica que `LAIA_EXTRA_PLUGIN_DIRS` apunta al dir materializado

### F4 — CLI + TUI

```bash
# Nuevos subcomandos en laia-marketplace.py
agent-area get [--field area.soul_md]
agent-area set-soul <path-o-texto>
agent-area set-instructions <path-o-texto>
agent-area set-name <nombre>
agent-area set-pref <key> <value> [--scope memory|behavior]

# Nueva pestana en TUI
python3 infra/dev/agora-control-center-tui.py
# Tab → 10 "Areas": lista users + display_name + plugins/skills count + soul truncado + updated
```

## Modelos Pydantic

```python
class AgentArea(BaseModel):
    user_id: str
    agent_display_name: str = Field(min_length=1, max_length=80)
    soul_md: str = Field(default="", max_length=50_000)
    instructions_md: str = Field(default="", max_length=50_000)
    memory_preferences: dict[str, Any] = Field(default_factory=dict)
    behavior_preferences: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)

class AgentAreaUpdate(BaseModel):
    agent_display_name: str | None = Field(default=None, min_length=1, max_length=80)
    soul_md: str | None = Field(default=None, max_length=50_000)
    instructions_md: str | None = Field(default=None, max_length=50_000)
    memory_preferences: dict[str, Any] | None = None
    behavior_preferences: dict[str, Any] | None = None
```

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `services/agora-backend/app/agent_identity.py` | Helper de naming: `canonical_container_name`, `legacy_container_name`, `candidate_container_names`, `slug_from_container`, `PROTECTED_LAIA_CONTAINERS` |
| `services/agora-backend/app/models.py:196-220` | Modelos `AgentArea` y `AgentAreaUpdate` con validacion |
| `services/agora-backend/app/agent_pool.py` | `_build_agent_area_prompt()` + `invalidate_user()` |
| `services/agora-backend/app/main.py` | Endpoints `/api/me/agent-area` y `/api/admin/users/<built-in function id>/agent-area` |
| `services/agora-backend/tests/test_agent_area.py` | 10 tests (schema, API, cross-user, malformed JSON, auto-create) |
| `services/agora-backend/tests/test_marketplace_integration.py` | Test combinado marketplace + agent-area |
| `infra/dev/laia-marketplace.py` | CLI `agent-area get/set-soul/set-instructions/set-name/set-pref` |
| `infra/dev/agora-control-center-tui.py` | TUI pestana 10 "Areas" |
| `infra/lxd/scripts/rebuild-4-first-user.sh` | Destruye legacy `laia-<slug>` + `--keep-legacy` |
| `infra/dev/preflight.sh` | Detecta containers sin state file |

## Diferencia con el viejo sistema

| Viejo (sprint 2) | Nuevo (v2.3+) |
|------------------|---------------|
| Perfil en archivos sueltos dentro del container (`/opt/laia/data/profile/`) | Centralizado en `agent_areas` (agora.db) |
| Se leia via `lxc exec python -c get_profile()` | Se lee de DB (sin depender del container) |
| Sin impacto en el LLM | Inyectado como `ephemeral_system_prompt` en AIAgent |
| Requeria container corriendo | Funciona aunque el container este parado |
| Sin validacion de tamaño | `max_length=50_000` en soul/instructions |

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Agent Areas — Identidad Centralizada del Agente

# AGORA Agent Areas — Identidad Centralizada del Agente

> 📅 Documentado: 2026-05-18 | 237 tests verdes

## Proposito

La identidad del agente (nombre, personalidad, instrucciones, preferencias de comportamiento
y memoria) se **centraliza** en AGORA. El container del usuario (`agent-<slug>`) queda como
executor puro: archivos, procesos, workspace tecnico privado. El soul no esta en el container.

## DB: agent_areas

```sql
CREATE TABLE agent_areas (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    agent_display_name TEXT,         -- nombre visible: "Nombrix", "MariaBot"
    soul_md TEXT,                     -- personalidad del agente (markdown, max 50K)
    instructions_md TEXT,             -- instrucciones operativas (markdown, max 50K)
    memory_preferences_json TEXT,     -- preferencias de memoria (JSON)
    behavior_preferences_json TEXT,   -- comportamiento: tone, language, etc (JSON)
    created_at TEXT,
    updated_at TEXT
);
```

## APIs REST

### Usuario (requiere JWT del propio usuario)

| Metodo | Ruta | Auth | Descripcion |
|--------|------|------|-------------|
| `GET` | `/api/me/agent-area` | JWT | Leer area completa. **Auto-crea** con defaults vacios si no existe (nunca 404) |
| `PATCH` | `/api/me/agent-area` | JWT | Editar campos: `agent_display_name`, `soul_md`, `instructions_md`, `memory_preferences`, `behavior_preferences` |
| `GET` | `/api/me/agent-area/plugins` | JWT | Plugins instalados por este usuario |
| `GET` | `/api/me/agent-area/skills` | JWT | Skills instaladas por este usuario |
| `GET` | `/api/me/agent-area/memory` | JWT | Preferencias de memoria configuradas |

### Admin (requiere rol `agora_admin`)

| Metodo | Ruta | Auth | Descripcion |
|--------|------|------|-------------|
| `GET` | `/api/admin/users/<built-in function id>/agent-area` | Admin JWT | Leer area de cualquier usuario |
| `PATCH` | `/api/admin/users/<built-in function id>/agent-area` | Admin JWT | Editar area de cualquier usuario |

### Compatibilidad legacy

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/api/agent/profile` | Lee de `agent_areas` en vez del executor. Mismo formato respuesta: `{persona, instructions, skills, preferences}` |

## Integracion con AgentPool

Cuando el usuario inicia un chat:

1. `AgentPool.get_or_create()` llama a `agent_area_for_user(user_id)`
2. Lee `soul_md`, `instructions_md`, `agent_display_name`, `behavior_preferences_json`
3. Construye `ephemeral_system_prompt`:
   ```
   [Soul]
   Soy Nombrix, el PA-AGORA de Jorge.
   
   [Instructions]
   Responde en espanol claro y directo.
   
   [Preferences]
   tone: directo
   language: es
   ```
4. Lo pasa al constructor de `AIAgent` → el LLM lo ve como prompt del sistema
5. Si el usuario edita su area → `AgentPool.invalidate_user(user_id)` → la siguiente
   peticion reconstruye el AIAgent con el nuevo soul

## End-to-end: configurar la identidad

```bash
# Leer area actual
laia-marketplace.py --slug jorge-dev agent-area get

# Poner nombre visible
laia-marketplace.py --slug jorge-dev agent-area set-name "Nombrix"

# Poner soul desde archivo markdown
laia-marketplace.py --slug jorge-dev agent-area set-soul ./mi-soul.md

# O poner soul directamente como texto
laia-marketplace.py --slug jorge-dev agent-area set-soul "Soy Nombrix, PA-AGORA de Jorge."

# Poner instrucciones
laia-marketplace.py --slug jorge-dev agent-area set-instructions "Responde en espanol claro y directo."

# Configurar preferencias
laia-marketplace.py --slug jorge-dev agent-area set-pref tone directo
laia-marketplace.py --slug jorge-dev agent-area set-pref language es --scope memory

# Ver en la TUI
python3 infra/dev/agora-control-center-tui.py   # Tab → pestana 10 "Areas"

# Ver via API
curl -s http://127.0.0.1:8088/api/me/agent-area \
  -H "Authorization: Bearer $TOKEN" | jq .
```

## Hardening (Fases 1-4, Mayo 2026)

### F1 — Seguridad P0

| Campo | Validacion | Motivo |
|-------|-----------|--------|
| `soul_md` | `max_length=50_000` | Previene DoS: un cliente podia meter MB de markdown y AgentPool lo lee en cada construccion de AIAgent |
| `instructions_md` | `max_length=50_000` | Idem |
| `agent_display_name` | `min_length=1, max_length=80` | Consistencia |
| GET auto-create | Si el area no existe, se crea con defaults vacios | Evita 404 en primer acceso. Consistente con PATCH que ya auto-creaba |

### F2 — Consistencia naming agent-*

| Archivo | Cambio |
|---------|--------|
| `admin.py:716` | `f"laia-{slug}"` → `candidate_container_names()` |
| `orchestrator/lxd.py` | Documentada duplicacion intencional con comment |
| `rebuild-4-first-user.sh` | Destruye legacy `laia-<slug>` al crear nuevo (salvo `--keep-legacy`) |
| `rebuild-1-cleanup.sh` | Limpia `agent-*` stray ademas de `laia-*` |
| `preflight.sh` | Detecta containers `agent-*`/`laia-*` sin state file → sugiere rebuild-state o delete |

### F3 — Tests combinados

Nuevo test `test_combined_marketplace_install_and_area_edit_pass_through_to_aiagent`:
1. Crea usuario + login
2. PATCH agent-area con soul custom
3. Publica + aprueba + instala plugin
4. Llama a `AgentPool.get_or_create()` (AIAgent mockeado)
5. Verifica que `ephemeral_system_prompt` contiene el soul
6. Verifica que `LAIA_EXTRA_PLUGIN_DIRS` apunta al dir materializado

### F4 — CLI + TUI

```bash
# Nuevos subcomandos en laia-marketplace.py
agent-area get [--field area.soul_md]
agent-area set-soul <path-o-texto>
agent-area set-instructions <path-o-texto>
agent-area set-name <nombre>
agent-area set-pref <key> <value> [--scope memory|behavior]

# Nueva pestana en TUI
python3 infra/dev/agora-control-center-tui.py
# Tab → 10 "Areas": lista users + display_name + plugins/skills count + soul truncado + updated
```

## Modelos Pydantic

```python
class AgentArea(BaseModel):
    user_id: str
    agent_display_name: str = Field(min_length=1, max_length=80)
    soul_md: str = Field(default="", max_length=50_000)
    instructions_md: str = Field(default="", max_length=50_000)
    memory_preferences: dict[str, Any] = Field(default_factory=dict)
    behavior_preferences: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)

class AgentAreaUpdate(BaseModel):
    agent_display_name: str | None = Field(default=None, min_length=1, max_length=80)
    soul_md: str | None = Field(default=None, max_length=50_000)
    instructions_md: str | None = Field(default=None, max_length=50_000)
    memory_preferences: dict[str, Any] | None = None
    behavior_preferences: dict[str, Any] | None = None
```

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `services/agora-backend/app/agent_identity.py` | Helper de naming: `canonical_container_name`, `legacy_container_name`, `candidate_container_names`, `slug_from_container`, `PROTECTED_LAIA_CONTAINERS` |
| `services/agora-backend/app/models.py:196-220` | Modelos `AgentArea` y `AgentAreaUpdate` con validacion |
| `services/agora-backend/app/agent_pool.py` | `_build_agent_area_prompt()` + `invalidate_user()` |
| `services/agora-backend/app/main.py` | Endpoints `/api/me/agent-area` y `/api/admin/users/<built-in function id>/agent-area` |
| `services/agora-backend/tests/test_agent_area.py` | 10 tests (schema, API, cross-user, malformed JSON, auto-create) |
| `services/agora-backend/tests/test_marketplace_integration.py` | Test combinado marketplace + agent-area |
| `infra/dev/laia-marketplace.py` | CLI `agent-area get/set-soul/set-instructions/set-name/set-pref` |
| `infra/dev/agora-control-center-tui.py` | TUI pestana 10 "Areas" |
| `infra/lxd/scripts/rebuild-4-first-user.sh` | Destruye legacy `laia-<slug>` + `--keep-legacy` |
| `infra/dev/preflight.sh` | Detecta containers sin state file |

## Diferencia con el viejo sistema

| Viejo (sprint 2) | Nuevo (v2.3+) |
|------------------|---------------|
| Perfil en archivos sueltos dentro del container (`/opt/laia/data/profile/`) | Centralizado en `agent_areas` (agora.db) |
| Se leia via `lxc exec python -c get_profile()` | Se lee de DB (sin depender del container) |
| Sin impacto en el LLM | Inyectado como `ephemeral_system_prompt` en AIAgent |
| Requeria container corriendo | Funciona aunque el container este parado |
| Sin validacion de tamaño | `max_length=50_000` en soul/instructions |
