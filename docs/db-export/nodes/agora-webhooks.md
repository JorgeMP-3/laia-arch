# Webhooks — Triggers Externos por Usuario

## Metadata

- ID: `217`
- Slug: `agora-webhooks`
- Kind: `doc`
- Status: `active`
- Filename: `agora-webhooks.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:33:53.541365+00:00`
- Updated at: `2026-05-19T08:36:17.974434+00:00`
- Aliases: `agora-webhooks`

## Summary

Cada usuario tiene POST /api/wh/<slug> con HMAC-SHA256. Recibe payloads externos (max 64KB), dispara AIAgent, devuelve respuesta. Secreto de 64 chars hex.

## Body

# Webhooks — Triggers Externos por Usuario

> &#x1F4C5; Documentado: 2026-05-18 | 342 tests backend

## Proposito

Cada usuario tiene un endpoint webhook unico. Sistemas externos pueden enviar payloads
que disparan una ejecucion del agente y devuelven respuesta.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/webhooks.py` | HMAC validation, trigger, response |
| DB: `webhook_subscriptions` | Configuracion por usuario |

## DB: webhook_subscriptions

```sql
webhook_subscriptions(id, user_id, slug UNIQUE, secret, prompt, deliver DEFAULT 'local',
    last_trigger_at, last_status, triggers_total, created_at, updated_at)
```

## Endpoint

```
POST /api/wh/<slug>
Header: X-Laia-Signature: <hmac-sha256>
Body: cualquier JSON (max 64KB)
```

## Seguridad

- `generate_secret()` -> 64 caracteres hexadecimales aleatorios
- `compute_hmac(secret, body)` -> HMAC-SHA256
- `constant_time_compare()` — evita timing attacks
- Slug desconocido -> 404 (misma respuesta que 401 para no filtrar existencia)

## Flujo

1. Sistema externo envia POST a `/api/wh/<slug>` con firma HMAC
2. AGORA valida la firma contra el secreto del usuario
3. Busca el `prompt` configurado en `webhook_subscriptions`
4. Crea una sesion AIAgent via AgentPool
5. Ejecuta: `<prompt del usuario> + JSON payload`
6. Devuelve respuesta truncada (preview)
7. Evicta sesion del pool
8. Registra evento de auditoria

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Webhooks — Triggers Externos por Usuario

# Webhooks — Triggers Externos por Usuario

> &#x1F4C5; Documentado: 2026-05-18 | 342 tests backend

## Proposito

Cada usuario tiene un endpoint webhook unico. Sistemas externos pueden enviar payloads
que disparan una ejecucion del agente y devuelven respuesta.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/webhooks.py` | HMAC validation, trigger, response |
| DB: `webhook_subscriptions` | Configuracion por usuario |

## DB: webhook_subscriptions

```sql
webhook_subscriptions(id, user_id, slug UNIQUE, secret, prompt, deliver DEFAULT 'local',
    last_trigger_at, last_status, triggers_total, created_at, updated_at)
```

## Endpoint

```
POST /api/wh/<slug>
Header: X-Laia-Signature: <hmac-sha256>
Body: cualquier JSON (max 64KB)
```

## Seguridad

- `generate_secret()` -> 64 caracteres hexadecimales aleatorios
- `compute_hmac(secret, body)` -> HMAC-SHA256
- `constant_time_compare()` — evita timing attacks
- Slug desconocido -> 404 (misma respuesta que 401 para no filtrar existencia)

## Flujo

1. Sistema externo envia POST a `/api/wh/<slug>` con firma HMAC
2. AGORA valida la firma contra el secreto del usuario
3. Busca el `prompt` configurado en `webhook_subscriptions`
4. Crea una sesion AIAgent via AgentPool
5. Ejecuta: `<prompt del usuario> + JSON payload`
6. Devuelve respuesta truncada (preview)
7. Evicta sesion del pool
8. Registra evento de auditoria
