# AGORA v0.5 — Hardening de Reglas ②⑥⑨⑩⑪ + Logout

## Metadata

- ID: `225`
- Slug: `agora-v05-hardening`
- Kind: `doc`
- Status: `active`
- Filename: `agora-v05-hardening.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T12:39:09.611564+00:00`
- Updated at: `2026-05-19T12:39:09.611564+00:00`
- Aliases: `agora-v05-hardening`

## Summary

Claude Code Opus 4.7 — 2026-05-19. P0: split laia_coordinator en base/admin toolsets, reservar slug 'laia'. P1: logout con revoke de tokens, audit regla ⑥. 91 tests verdes.

## Body

# AGORA v0.5 — Hardening de Reglas

> &#x1F4C5; 2026-05-19 | Claude Code Opus 4.7 | 91 tests verdes

## P0.2 — Slug "laia" reservado (regla ②)

**Archivo:** `app/models.py`

```python
RESERVED_AGENT_SLUGS = {"laia", "agora", "arch", "admin", "root", "system",
                         "laia-agora", "laia-arch", "laia-core"}
```

`field_validator("slug")` en `CreateAgentRequest` y `RegisterAgentRequest`.
Ningun empleado puede crear un agente con slug reservado. Cumple regla ②.

Tests: `test_agents.py` 27/27 (+2: reserved slug en create y register).

## P0.3 — Marketplace pool invalidation

Ya estaba implementado en `app/marketplace.py:281,292,372,383`
(`_invalidate_pool_for(user.id)` en los 4 endpoints de install/uninstall).
El audit miraba solo `main.py`. Sin cambios necesarios.

## P0.1 Fase 2 — Split del toolset de LAIA Coordinator (reglas ⑨⑩⑪)

### Plugin: `.laia-core/plugins/laia-coordinator/__init__.py`

Toolset dividido en dos:

| Toolset | Tools | Quien |
|---------|-------|-------|
| `laia_coordinator_base` | 2 tools: `laia_list_users`, `laia_workspace_search` | Empleados + admins |
| `laia_coordinator_admin` | 6 tools: `laia_user_overview`, `laia_read_audit`, `laia_read_usage`, `laia_send_message`, `laia_alert_admin`, `laia_recent_children` | Solo admins |

Thread-locals nuevos:
- `_chat.mode` — True cuando el thread esta en modo LAIA chat
- `_chat.role` — rol del actor (`agora_admin` | `employee`)

Helpers: `set_laia_chat_mode(role)`, `clear_laia_chat_mode()`, `_require_laia_mode()`, `_require_admin()`.

### AgentPool: `app/agent_pool.py`

`get_or_create()` acepta `mode="laia"` + `actor_role`:
- Skip `_materialize_marketplace_for` (LAIA no carga plugins del actor)
- Skip `_bind_self_edit_session` (regla ⑪)
- System prompt desde `agent_areas[user_laia]`
- Toolsets: `laia_coordinator_base` para todos, `+_admin` si `actor_role == "agora_admin"`
- `_bind_laia_chat_mode(actor_role)` setea el thread-local del plugin

### Endpoint: `app/laia_chat.py`

- `/api/laia/chat` abierto a cualquier usuario autenticado (sin `require_roles`)
- LLM config y usage tracking atribuidos al actor (no a `user_laia`)
- `session_id` namespaceado como `laia-<actor.id>-<sid>`
- Empleados reciben tools `_base` (2 tools reales), admins `_base + _admin` (8)
- Docstring explica interpretacion de regla ⑩: tools read-only sobre `agora.db` no pueden ejecutarse en el executor del usuario (solo `laia-agora` tiene la DB)

Tests: `test_laia_coordinator.py` 16/16 (+4 nuevos: split por rol, refuse empleado en admin tool, base tool OK empleado, refuse fuera LAIA mode, employee LAIA chat).

---

## P1 — Logout / Revoke de tokens

### DB: `app/database.py`

Nueva columna: `users.tokens_valid_since INTEGER NOT NULL DEFAULT 0`.
Migracion idempotente.

### Storage: `app/storage.py`

- `tokens_valid_since(user_id)` → int (cutoff timestamp)
- `revoke_user_tokens(user_id, cutoff=None)` → bool

### Auth: `app/auth.py`

`current_user` verifica: si `iat <= tokens_valid_since` → 401 "token revoked".

### API: `app/main.py`

- `POST /api/logout` — revoke de todos los tokens del usuario
- `/api/refresh` tambien verifica cutoff (no mintea access tokens nuevos)

"Sign out everywhere" sin denylist de JTIs.

Tests: `test_users.py` 22/22 (+2: logout revoca access+refresh, re-login post-logout funciona).

---

## P1 — Investigacion hard-delete (WONTFIX)

No hay `DELETE FROM users` en ninguna ruta. Todo es soft-delete (`active=0`).
Las filas en `user_plugins`, `user_skills`, `agent_areas` quedan por audit trail.
Documentado en `storage.py:disable_user` docstring.

---

## P1 — Regla ⑥ LXD ops audit warning

### Models: `app/models.py`

Añadido `host_admin` al Literal `Role` (sin uso forzado todavia).

### Admin: `app/admin.py`

Helper `_warn_host_op_via_agora_admin(actor, action)`:
- Emite `event_type=rule_6_host_op_via_agora_admin` en `events`
- Loggea WARN estructurado
- Aplicado a 5 endpoints: `containers/{name}/restart|snapshot|restore`, `system/restart-backend`, `users/{slug}/rebuild`

Pendiente migracion futura: asignar `host_admin` a Jorge, flippear `require_roles` en esos endpoints, eliminar helper.

Tests: `test_admin_control_center.py` 28/28 (+1: audit event regla ⑥).

---

## Resumen de tests

| Suite | Antes | Ahora | Nuevos |
|-------|-------|-------|--------|
| test_agents | 25 | 27 | +2 (reserved slug) |
| test_laia_coordinator | 10 | 16 | +6 (toolset split) |
| test_users | 20 | 22 | +2 (logout) |
| test_admin_control_center | 27 | 28 | +1 (regla ⑥) |
| **Total** | **82** | **91** | **+11** |

---

## Reglas del Documento Definitivo — Estado final

| Regla | Descripcion | Estado |
|-------|-------------|--------|
| ② | Slug "laia" reservado | ✅ Hardened |
| ⑥ | Admin AGORA no toca infra | ⚠️ Audit warning (pendiente migracion host_admin) |
| ⑨ | LAIA es modo de chat | ✅ Toolset role-aware |
| ⑩ | LAIA ejecuta en container del caller | ✅ DB reads local, executor wired |
| ⑪ | LAIA sin self-edit/scheduler/delegation | ✅ Excluidos del mode='laia' |

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA v0.5 — Hardening de Reglas ②⑥⑨⑩⑪ + Logout

# AGORA v0.5 — Hardening de Reglas

> &#x1F4C5; 2026-05-19 | Claude Code Opus 4.7 | 91 tests verdes

## P0.2 — Slug "laia" reservado (regla ②)

**Archivo:** `app/models.py`

```python
RESERVED_AGENT_SLUGS = {"laia", "agora", "arch", "admin", "root", "system",
                         "laia-agora", "laia-arch", "laia-core"}
```

`field_validator("slug")` en `CreateAgentRequest` y `RegisterAgentRequest`.
Ningun empleado puede crear un agente con slug reservado. Cumple regla ②.

Tests: `test_agents.py` 27/27 (+2: reserved slug en create y register).

## P0.3 — Marketplace pool invalidation

Ya estaba implementado en `app/marketplace.py:281,292,372,383`
(`_invalidate_pool_for(user.id)` en los 4 endpoints de install/uninstall).
El audit miraba solo `main.py`. Sin cambios necesarios.

## P0.1 Fase 2 — Split del toolset de LAIA Coordinator (reglas ⑨⑩⑪)

### Plugin: `.laia-core/plugins/laia-coordinator/__init__.py`

Toolset dividido en dos:

| Toolset | Tools | Quien |
|---------|-------|-------|
| `laia_coordinator_base` | 2 tools: `laia_list_users`, `laia_workspace_search` | Empleados + admins |
| `laia_coordinator_admin` | 6 tools: `laia_user_overview`, `laia_read_audit`, `laia_read_usage`, `laia_send_message`, `laia_alert_admin`, `laia_recent_children` | Solo admins |

Thread-locals nuevos:
- `_chat.mode` — True cuando el thread esta en modo LAIA chat
- `_chat.role` — rol del actor (`agora_admin` | `employee`)

Helpers: `set_laia_chat_mode(role)`, `clear_laia_chat_mode()`, `_require_laia_mode()`, `_require_admin()`.

### AgentPool: `app/agent_pool.py`

`get_or_create()` acepta `mode="laia"` + `actor_role`:
- Skip `_materialize_marketplace_for` (LAIA no carga plugins del actor)
- Skip `_bind_self_edit_session` (regla ⑪)
- System prompt desde `agent_areas[user_laia]`
- Toolsets: `laia_coordinator_base` para todos, `+_admin` si `actor_role == "agora_admin"`
- `_bind_laia_chat_mode(actor_role)` setea el thread-local del plugin

### Endpoint: `app/laia_chat.py`

- `/api/laia/chat` abierto a cualquier usuario autenticado (sin `require_roles`)
- LLM config y usage tracking atribuidos al actor (no a `user_laia`)
- `session_id` namespaceado como `laia-<actor.id>-<sid>`
- Empleados reciben tools `_base` (2 tools reales), admins `_base + _admin` (8)
- Docstring explica interpretacion de regla ⑩: tools read-only sobre `agora.db` no pueden ejecutarse en el executor del usuario (solo `laia-agora` tiene la DB)

Tests: `test_laia_coordinator.py` 16/16 (+4 nuevos: split por rol, refuse empleado en admin tool, base tool OK empleado, refuse fuera LAIA mode, employee LAIA chat).

---

## P1 — Logout / Revoke de tokens

### DB: `app/database.py`

Nueva columna: `users.tokens_valid_since INTEGER NOT NULL DEFAULT 0`.
Migracion idempotente.

### Storage: `app/storage.py`

- `tokens_valid_since(user_id)` → int (cutoff timestamp)
- `revoke_user_tokens(user_id, cutoff=None)` → bool

### Auth: `app/auth.py`

`current_user` verifica: si `iat <= tokens_valid_since` → 401 "token revoked".

### API: `app/main.py`

- `POST /api/logout` — revoke de todos los tokens del usuario
- `/api/refresh` tambien verifica cutoff (no mintea access tokens nuevos)

"Sign out everywhere" sin denylist de JTIs.

Tests: `test_users.py` 22/22 (+2: logout revoca access+refresh, re-login post-logout funciona).

---

## P1 — Investigacion hard-delete (WONTFIX)

No hay `DELETE FROM users` en ninguna ruta. Todo es soft-delete (`active=0`).
Las filas en `user_plugins`, `user_skills`, `agent_areas` quedan por audit trail.
Documentado en `storage.py:disable_user` docstring.

---

## P1 — Regla ⑥ LXD ops audit warning

### Models: `app/models.py`

Añadido `host_admin` al Literal `Role` (sin uso forzado todavia).

### Admin: `app/admin.py`

Helper `_warn_host_op_via_agora_admin(actor, action)`:
- Emite `event_type=rule_6_host_op_via_agora_admin` en `events`
- Loggea WARN estructurado
- Aplicado a 5 endpoints: `containers/{name}/restart|snapshot|restore`, `system/restart-backend`, `users/{slug}/rebuild`

Pendiente migracion futura: asignar `host_admin` a Jorge, flippear `require_roles` en esos endpoints, eliminar helper.

Tests: `test_admin_control_center.py` 28/28 (+1: audit event regla ⑥).

---

## Resumen de tests

| Suite | Antes | Ahora | Nuevos |
|-------|-------|-------|--------|
| test_agents | 25 | 27 | +2 (reserved slug) |
| test_laia_coordinator | 10 | 16 | +6 (toolset split) |
| test_users | 20 | 22 | +2 (logout) |
| test_admin_control_center | 27 | 28 | +1 (regla ⑥) |
| **Total** | **82** | **91** | **+11** |

---

## Reglas del Documento Definitivo — Estado final

| Regla | Descripcion | Estado |
|-------|-------------|--------|
| ② | Slug "laia" reservado | ✅ Hardened |
| ⑥ | Admin AGORA no toca infra | ⚠️ Audit warning (pendiente migracion host_admin) |
| ⑨ | LAIA es modo de chat | ✅ Toolset role-aware |
| ⑩ | LAIA ejecuta en container del caller | ✅ DB reads local, executor wired |
| ⑪ | LAIA sin self-edit/scheduler/delegation | ✅ Excluidos del mode='laia' |
