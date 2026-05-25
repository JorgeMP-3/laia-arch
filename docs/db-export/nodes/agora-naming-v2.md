# AGORA Naming v2 — Convencion agent-<slug>

## Metadata

- ID: `211`
- Slug: `agora-naming-v2`
- Kind: `doc`
- Status: `active`
- Filename: `agora-naming-v2.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T16:10:02.389755+00:00`
- Updated at: `2026-05-18T17:06:21.945624+00:00`
- Aliases: `agora-naming-v2`

## Summary

Nuevos containers usan agent-<slug>. Legacy laia-<slug> mantenido para laia-agora y laia-jorge. Hardening: admin.py, rebuild-1/4, preflight.sh migrados.

## Body

# AGORA Naming v2 — agent-<slug>

> 📅 Documentado: 2026-05-18 | 237 tests verdes

## Convencion

| Tipo | Naming | Ejemplos |
|------|--------|----------|
| **Nuevos usuarios** | `agent-<slug>` | `agent-jorge-dev`, `agent-maria` |
| **Cerebro (PROTEGIDO)** | `laia-agora` | NO se renombra |
| **Legacy sprint 2 (PROTEGIDO)** | `laia-jorge` | NO se renombra, STOPPED, preservado |
| **Legacy stray (ELIMINAR)** | `laia-<slug>` cualquiera excepto los protegidos | `laia-jorge-dev` → destruido por rebuild-4 |

## Helper central

`services/agora-backend/app/agent_identity.py`:

```python
PROTECTED_LAIA_CONTAINERS = {"laia-agora", "laia-jorge"}

def canonical_container_name(slug: str) -> str:
    return f"agent-{slug}"

def legacy_container_name(slug: str) -> str:
    return f"laia-{slug}"

def candidate_container_names(slug: str) -> list[str]:
    return [canonical_container_name(slug), legacy_container_name(slug)]

def slug_from_container(name: str) -> str | None:
    for prefix in ("agent-", "laia-"):
        if name.startswith(prefix):
            return name.removeprefix(prefix)
    return None

def is_user_agent_container(name: str) -> bool:
    return (name.startswith("agent-") or name.startswith("laia-")) \
           and name not in PROTECTED_LAIA_CONTAINERS
```

## Scripts migrados al nuevo naming

### rebuild-4-first-user.sh
- Crea `agent-$SLUG`
- **Destruye** `laia-$SLUG` si existe (salvo `--keep-legacy`)
- No toca `laia-agora` ni `laia-jorge` (protegidos)

### rebuild-1-cleanup.sh
- Limpia containers de test `agent-*` y `laia-*` (excepto protegidos)
- Nueva linea: `grep -E '^(laia-|agent-)'`

### preflight.sh
- Detecta containers `agent-*` sin state file
- Detecta containers `laia-*` (no protegidos) sin state file
- Warning: "ejecuta rebuild-state.sh --slug X o lxc delete --force X"

### chat-with-deployed.sh
- Lee `.container` del state JSON (dinamico, no hardcodea `laia-$SLUG`)

### admin.py:716
- `f"laia-{slug}"` → `candidate_container_names(slug)`

### orchestrator/lxd.py
- Documentada duplicacion intencional de los helpers (el orchestrator es host-side, no importa agora-backend)

## State files

Los archivos en `~/.laia/state/` mantienen el nombre legacy `laia-state-<slug>.json`
por compatibilidad, pero el campo `.container` contiene `agent-<slug>`:

```json
{
  "slug": "jorge-dev",
  "container": "agent-jorge-dev",
  "ipv4": "10.99.0.58",
  "api_token": "...",
  "password": "chattest"
}
```

## Limpieza manual del lab

```bash
# Ver containers
lxc list

# Eliminar legacy stray (NO protegidos)
sudo lxc delete --force laia-jorge-dev

# O dejar que rebuild-4 lo haga automaticamente
sudo bash infra/lxd/scripts/rebuild-4-first-user.sh --slug jorge-dev
```

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Naming v2 — Convencion agent-<slug>

# AGORA Naming v2 — agent-<slug>

> 📅 Documentado: 2026-05-18 | 237 tests verdes

## Convencion

| Tipo | Naming | Ejemplos |
|------|--------|----------|
| **Nuevos usuarios** | `agent-<slug>` | `agent-jorge-dev`, `agent-maria` |
| **Cerebro (PROTEGIDO)** | `laia-agora` | NO se renombra |
| **Legacy sprint 2 (PROTEGIDO)** | `laia-jorge` | NO se renombra, STOPPED, preservado |
| **Legacy stray (ELIMINAR)** | `laia-<slug>` cualquiera excepto los protegidos | `laia-jorge-dev` → destruido por rebuild-4 |

## Helper central

`services/agora-backend/app/agent_identity.py`:

```python
PROTECTED_LAIA_CONTAINERS = {"laia-agora", "laia-jorge"}

def canonical_container_name(slug: str) -> str:
    return f"agent-{slug}"

def legacy_container_name(slug: str) -> str:
    return f"laia-{slug}"

def candidate_container_names(slug: str) -> list[str]:
    return [canonical_container_name(slug), legacy_container_name(slug)]

def slug_from_container(name: str) -> str | None:
    for prefix in ("agent-", "laia-"):
        if name.startswith(prefix):
            return name.removeprefix(prefix)
    return None

def is_user_agent_container(name: str) -> bool:
    return (name.startswith("agent-") or name.startswith("laia-")) \
           and name not in PROTECTED_LAIA_CONTAINERS
```

## Scripts migrados al nuevo naming

### rebuild-4-first-user.sh
- Crea `agent-$SLUG`
- **Destruye** `laia-$SLUG` si existe (salvo `--keep-legacy`)
- No toca `laia-agora` ni `laia-jorge` (protegidos)

### rebuild-1-cleanup.sh
- Limpia containers de test `agent-*` y `laia-*` (excepto protegidos)
- Nueva linea: `grep -E '^(laia-|agent-)'`

### preflight.sh
- Detecta containers `agent-*` sin state file
- Detecta containers `laia-*` (no protegidos) sin state file
- Warning: "ejecuta rebuild-state.sh --slug X o lxc delete --force X"

### chat-with-deployed.sh
- Lee `.container` del state JSON (dinamico, no hardcodea `laia-$SLUG`)

### admin.py:716
- `f"laia-{slug}"` → `candidate_container_names(slug)`

### orchestrator/lxd.py
- Documentada duplicacion intencional de los helpers (el orchestrator es host-side, no importa agora-backend)

## State files

Los archivos en `~/.laia/state/` mantienen el nombre legacy `laia-state-<slug>.json`
por compatibilidad, pero el campo `.container` contiene `agent-<slug>`:

```json
{
  "slug": "jorge-dev",
  "container": "agent-jorge-dev",
  "ipv4": "10.99.0.58",
  "api_token": "...",
  "password": "chattest"
}
```

## Limpieza manual del lab

```bash
# Ver containers
lxc list

# Eliminar legacy stray (NO protegidos)
sudo lxc delete --force laia-jorge-dev

# O dejar que rebuild-4 lo haga automaticamente
sudo bash infra/lxd/scripts/rebuild-4-first-user.sh --slug jorge-dev
```
