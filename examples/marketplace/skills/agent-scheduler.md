---
name: agent-scheduler
description: >
  Permite al agente programarse tasks recurrentes y subscribirse a
  webhooks externos para reaccionar a eventos.
version: 0.1.0
---

# Programar tasks y webhooks

Tienes acceso a 8 tools del toolset `agent_scheduler`. Los jobs viven en
`agora.db` y un tick loop del backend los ejecuta.

## Schedule

| Tool | Cuándo |
|---|---|
| `schedule_create(name, cron_expr, prompt, deliver?)` | "Recuérdame X cada semana", "revisa Y cada hora". |
| `schedule_list(status?)` | "Qué tasks tengo programadas?" |
| `schedule_pause(job_id)` | "Pausa la task X". |
| `schedule_resume(job_id)` | "Resume la task X". |
| `schedule_delete(job_id)` | "Borra la task X". |

Formato `cron_expr`:
- 5-field cron UTC: `*/5 * * * *` (cada 5 min), `0 9 * * 1` (lunes 9am).
- Alias: `@hourly`, `@daily`, `@weekly`, `@monthly`, `@yearly`.
- One-shot: `in 10m`, `in 2h`, `in 1d` (se pausan tras ejecutar).

`deliver` puede ser `"local"` (solo log), `"origin"` (a tu telegram si está
linkeado), o `"telegram:<chat_id>"`.

## Webhooks

| Tool | Cuándo |
|---|---|
| `webhook_subscribe(slug, prompt, deliver?)` | "Quiero reaccionar cuando llegue un PR de GitHub". |
| `webhook_list()` | "Qué webhooks tengo?" |
| `webhook_remove(id)` | Borrar uno. |

`webhook_subscribe` devuelve la URL pública y el `secret`. El externo debe
firmar el body con HMAC-SHA256 y mandarlo en header `X-Laia-Signature`.

## Reglas

- Antes de crear un job, valida el `cron_expr` mentalmente: ¿el user quería
  exacto eso? "Cada 5 min" puede ser excesivo — confirma si la frecuencia
  pega.
- Cuando creas un job recurrente, **resume al user qué hará y cuándo**
  (siguiente run según `next_run_at` de la respuesta).
- Si el user dice "olvídalo", usa `schedule_delete`, no `pause`.
- Los webhook secrets se ven solo en `webhook_subscribe`; si el user los
  pierde, debe re-suscribir.
