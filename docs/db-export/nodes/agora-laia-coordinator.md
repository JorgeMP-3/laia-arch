# LAIA Coordinator — El Agente Padre en AGORA

## Metadata

- ID: `213`
- Slug: `agora-laia-coordinator`
- Kind: `doc`
- Status: `active`
- Filename: `agora-laia-coordinator.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:33:53.471272+00:00`
- Updated at: `2026-05-19T08:33:53.471272+00:00`
- Aliases: `agora-laia-coordinator`

## Summary

Chat admin-only SSE con LAIA (user_laia). Inbox per-user con coordinator_messages. Laia puede enviar mensajes, alertas y listar usuarios.

## Body

# LAIA Coordinator

> 📅 Documentado: 2026-05-18 | 342 tests backend

## Proposito

LAIA (el agente padre) tiene presencia en AGORA como un usuario sintetico `user_laia`.
Desde el Control Center o API, un admin puede chatear con LAIA directamente. LAIA puede
enviar mensajes a usuarios via inbox y ejecutar herramientas de coordinacion.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/laia_identity.py` | Constantes de identidad: ID, username, token, soul, instrucciones |
| `app/laia_chat.py` | Endpoints SSE: `GET /api/laia/inbox-count`, `POST /api/laia/chat` |

## Identidad

```python
LAIA_USER_ID = "user_laia"
LAIA_USERNAME = "laia"
LAIA_TOKEN = "laia-coordinator-token"
LAIA_SOUL = "Soy LAIA, la coordinadora del ecosistema AGORA..."
LAIA_INSTRUCTIONS = "Puedo listar usuarios, enviar mensajes, alertar al admin..."
```

El seed es idempotente — no sobreescribe si ya existe.

## Endpoints

| Metodo | Ruta | Auth | Descripcion |
|--------|------|------|-------------|
| GET | /api/laia/inbox-count | Admin | Mensajes no leidos por usuario |
| POST | /api/laia/chat | Admin | Chat SSE con LAIA |

## Inbox (coordinator_messages)

```sql
coordinator_messages(user_id, from_role, text, severity, read, created_at, read_at)
```

LAIA puede enviar mensajes a cualquier usuario. El usuario los ve como notificaciones.
Severities: `info`, `warn`, `error`.

## Toolset de LAIA

LAIA tiene acceso a herramientas exclusivas que los usuarios normales no tienen:
- `laia_list_users` — listar todos los usuarios
- `laia_send_message` — enviar mensaje a un usuario
- `laia_alert_admin` — alertar al admin (Jorge)
- `laia_get_user_info` — info detallada de un usuario

## Patron tecnico

Chat SSE usa `asyncio.Queue` + `loop.run_in_executor` para puentear el `run_conversation`
sync del AIAgent a streaming async. Sentinel `_STREAM_SENTINEL` senala fin del worker.
Registra uso en `usage_ledger` con `kind="laia-chat"`.

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA Coordinator — El Agente Padre en AGORA

# LAIA Coordinator

> 📅 Documentado: 2026-05-18 | 342 tests backend

## Proposito

LAIA (el agente padre) tiene presencia en AGORA como un usuario sintetico `user_laia`.
Desde el Control Center o API, un admin puede chatear con LAIA directamente. LAIA puede
enviar mensajes a usuarios via inbox y ejecutar herramientas de coordinacion.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/laia_identity.py` | Constantes de identidad: ID, username, token, soul, instrucciones |
| `app/laia_chat.py` | Endpoints SSE: `GET /api/laia/inbox-count`, `POST /api/laia/chat` |

## Identidad

```python
LAIA_USER_ID = "user_laia"
LAIA_USERNAME = "laia"
LAIA_TOKEN = "laia-coordinator-token"
LAIA_SOUL = "Soy LAIA, la coordinadora del ecosistema AGORA..."
LAIA_INSTRUCTIONS = "Puedo listar usuarios, enviar mensajes, alertar al admin..."
```

El seed es idempotente — no sobreescribe si ya existe.

## Endpoints

| Metodo | Ruta | Auth | Descripcion |
|--------|------|------|-------------|
| GET | /api/laia/inbox-count | Admin | Mensajes no leidos por usuario |
| POST | /api/laia/chat | Admin | Chat SSE con LAIA |

## Inbox (coordinator_messages)

```sql
coordinator_messages(user_id, from_role, text, severity, read, created_at, read_at)
```

LAIA puede enviar mensajes a cualquier usuario. El usuario los ve como notificaciones.
Severities: `info`, `warn`, `error`.

## Toolset de LAIA

LAIA tiene acceso a herramientas exclusivas que los usuarios normales no tienen:
- `laia_list_users` — listar todos los usuarios
- `laia_send_message` — enviar mensaje a un usuario
- `laia_alert_admin` — alertar al admin (Jorge)
- `laia_get_user_info` — info detallada de un usuario

## Patron tecnico

Chat SSE usa `asyncio.Queue` + `loop.run_in_executor` para puentear el `run_conversation`
sync del AIAgent a streaming async. Sentinel `_STREAM_SENTINEL` senala fin del worker.
Registra uso en `usage_ledger` con `kind="laia-chat"`.
