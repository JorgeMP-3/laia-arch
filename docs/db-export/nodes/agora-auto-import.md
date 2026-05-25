# Auto-Import — Sincronizacion Externa

## Metadata

- ID: `219`
- Slug: `agora-auto-import`
- Kind: `doc`
- Status: `active`
- Filename: `agora-auto-import.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:36:18.011413+00:00`
- Updated at: `2026-05-19T08:36:18.011413+00:00`
- Aliases: `agora-auto-import`

## Summary

Framework de proveedores para importar datos desde GitHub, Notion, Linear. EchoProvider para testing. Sincronizacion via cron (default cada 6h).

## Body

# Auto-Import

> &#x1F4C5; 2026-05-18 | 342 tests backend

## Proposito

Importar datos automaticamente desde fuentes externas al workspace del usuario.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/auto_import/__init__.py` | Interfaz ImportProvider + registro + sync runner |
| `app/auto_import/echo_provider.py` | Stub: crea N nodos sinteticos para testing |
| DB: `auto_imports` | Config por usuario |

## Interfaz

```python
class ImportProvider(Protocol):
    name: str
    def sync(user_id: str, config: dict, target_ws) -> dict
```

## DB: auto_imports

```sql
auto_imports(id, user_id, provider, config_json, last_synced_at, last_status,
    last_error, last_count, cron_expr DEFAULT '0 */6 * * *',
    target_workspace DEFAULT 'private', enabled DEFAULT 1)
```

## Proveedores

| Provider | Estado |
|----------|--------|
| `echo` | Implementado (testing) |
| `github` | Stub |
| `notion` | Stub |
| `linear` | Stub |

## Flujo

1. `scheduler.py` detecta `auto_imports` con `next_run` vencido
2. `run_import()` resuelve el provider, llama `sync()`
3. Actualiza `last_synced_at`, `last_status`, `last_count`
4. Registra evento de auditoria. Errores capturados (no-raise)

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Auto-Import — Sincronizacion Externa

# Auto-Import

> &#x1F4C5; 2026-05-18 | 342 tests backend

## Proposito

Importar datos automaticamente desde fuentes externas al workspace del usuario.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/auto_import/__init__.py` | Interfaz ImportProvider + registro + sync runner |
| `app/auto_import/echo_provider.py` | Stub: crea N nodos sinteticos para testing |
| DB: `auto_imports` | Config por usuario |

## Interfaz

```python
class ImportProvider(Protocol):
    name: str
    def sync(user_id: str, config: dict, target_ws) -> dict
```

## DB: auto_imports

```sql
auto_imports(id, user_id, provider, config_json, last_synced_at, last_status,
    last_error, last_count, cron_expr DEFAULT '0 */6 * * *',
    target_workspace DEFAULT 'private', enabled DEFAULT 1)
```

## Proveedores

| Provider | Estado |
|----------|--------|
| `echo` | Implementado (testing) |
| `github` | Stub |
| `notion` | Stub |
| `linear` | Stub |

## Flujo

1. `scheduler.py` detecta `auto_imports` con `next_run` vencido
2. `run_import()` resuelve el provider, llama `sync()`
3. Actualiza `last_synced_at`, `last_status`, `last_count`
4. Registra evento de auditoria. Errores capturados (no-raise)
