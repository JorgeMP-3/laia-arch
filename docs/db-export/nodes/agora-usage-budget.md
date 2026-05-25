# Usage Ledger + Budget + Pricing

## Metadata

- ID: `218`
- Slug: `agora-usage-budget`
- Kind: `doc`
- Status: `active`
- Filename: `agora-usage-budget.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:36:17.987996+00:00`
- Updated at: `2026-05-19T08:36:17.987996+00:00`
- Aliases: `agora-usage-budget`

## Summary

usage_ledger trackea tokens y coste USD por llamada. pricing.py estima costes. Budget diario/mensual/tokens por usuario. Admin configura limites.

## Body

# Usage Ledger + Budget + Pricing

> &#x1F4C5; 2026-05-18 | 342 tests backend

## Proposito

Control de costes del LLM: tracking de tokens por llamada, estimacion de coste USD,
limites de presupuesto por usuario.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/pricing.py` | Tabla de precios USD/1M tokens por provider+modelo |
| `app/agent_pool.py` | `record_usage_for_session()` escribe en usage_ledger |
| DB: `usage_ledger` | Tracking por llamada |
| DB: `users` (+3 columnas) | Budget caps |

## DB: usage_ledger

```sql
usage_ledger(id AUTOINCREMENT, user_id, session_id, ts, provider, model,
    tokens_input DEFAULT 0, tokens_output DEFAULT 0, cost_usd, kind DEFAULT 'chat')
```

Kinds: `chat`, `scheduled`, `child`, `webhook`, `laia-chat`.
Indexado por `(user_id, ts)` y `(user_id, kind)`.

## Pricing (pricing.py)

Tabla estatica + overrides via YAML (`$AGORA_DATA_DIR/pricing.yaml` con cache por mtime):

| Provider | Modelo | Input/1M | Output/1M |
|----------|--------|----------|-----------|
| anthropic | claude-sonnet-4-6 | $3.00 | $15.00 |
| openai | gpt-5.5 | $2.50 | $15.00 |
| deepseek | deepseek-chat | $0.27 | $1.10 |
| xai | grok-4 | $2.00 | $8.00 |
| openrouter | wildcard | $1.00 | $4.00 |

Modelos desconocidos -> `cost_usd = NULL` (trackeados pero sin limite $).

## Budget (users table)

```sql
users.budget_daily_usd REAL
users.budget_monthly_usd REAL
users.budget_tokens_daily INTEGER
```

Admin endpoints: `GET/PATCH /api/admin/users/{id}/budget`, `GET /api/admin/usage`

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Usage Ledger + Budget + Pricing

# Usage Ledger + Budget + Pricing

> &#x1F4C5; 2026-05-18 | 342 tests backend

## Proposito

Control de costes del LLM: tracking de tokens por llamada, estimacion de coste USD,
limites de presupuesto por usuario.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/pricing.py` | Tabla de precios USD/1M tokens por provider+modelo |
| `app/agent_pool.py` | `record_usage_for_session()` escribe en usage_ledger |
| DB: `usage_ledger` | Tracking por llamada |
| DB: `users` (+3 columnas) | Budget caps |

## DB: usage_ledger

```sql
usage_ledger(id AUTOINCREMENT, user_id, session_id, ts, provider, model,
    tokens_input DEFAULT 0, tokens_output DEFAULT 0, cost_usd, kind DEFAULT 'chat')
```

Kinds: `chat`, `scheduled`, `child`, `webhook`, `laia-chat`.
Indexado por `(user_id, ts)` y `(user_id, kind)`.

## Pricing (pricing.py)

Tabla estatica + overrides via YAML (`$AGORA_DATA_DIR/pricing.yaml` con cache por mtime):

| Provider | Modelo | Input/1M | Output/1M |
|----------|--------|----------|-----------|
| anthropic | claude-sonnet-4-6 | $3.00 | $15.00 |
| openai | gpt-5.5 | $2.50 | $15.00 |
| deepseek | deepseek-chat | $0.27 | $1.10 |
| xai | grok-4 | $2.00 | $8.00 |
| openrouter | wildcard | $1.00 | $4.00 |

Modelos desconocidos -> `cost_usd = NULL` (trackeados pero sin limite $).

## Budget (users table)

```sql
users.budget_daily_usd REAL
users.budget_monthly_usd REAL
users.budget_tokens_daily INTEGER
```

Admin endpoints: `GET/PATCH /api/admin/users/{id}/budget`, `GET /api/admin/usage`
