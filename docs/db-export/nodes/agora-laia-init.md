# laia-init — Wizard de Instalacion

## Metadata

- ID: `220`
- Slug: `agora-laia-init`
- Kind: `doc`
- Status: `active`
- Filename: `agora-laia-init.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:36:18.028864+00:00`
- Updated at: `2026-05-19T08:36:18.028864+00:00`
- Aliases: `agora-laia-init`

## Summary

Script interactivo (8 pasos) que toma un host limpio con LXD + repo y lo deja con AGORA + LAIA + primer usuario. Soporta --non-interactive, --dry-run.

## Body

# laia-init — Wizard de Instalacion

> &#x1F4C5; 2026-05-18 | Shell tests verdes

## Proposito

Instalacion guiada de AGORA desde un host limpio. 8 pasos con defaults inteligentes.

## Archivos

| Archivo | Rol |
|---------|-----|
| `infra/dev/laia-init.sh` | Wizard principal (8 pasos) |
| `infra/dev/laia-init-checks.sh` | Pre-checks (LXD, deps, auth.json) |

## Modos

| Flag | Descripcion |
|------|-------------|
| (sin flags) | Interactivo: pregunta cada paso |
| `--non-interactive` | Lee de env vars, falla si faltan |
| `--dry-run` | Imprime que haria sin ejecutar |
| `--skip-images` | No reconstruye imagenes LXD |
| `--skip-first-user` | No provisiona el primer usuario |

## 8 pasos

1. `laia-init-checks.sh` — verifica LXD, git, jq, curl, auth.json
2. LXD defaults — storage pool, network bridge, perfiles
3. auth.json — verificacion/configuracion de OAuth
4. Prompt — nombre del admin, API key LLM, provider
5. rebuild-2 — construye imagenes LXD
6. rebuild-3 — provisiona laia-agora
7. seed-base-skills.sh — publica skills base
8. rebuild-4 — provisiona primer usuario + verificacion

## Env vars para non-interactive

```bash
LAIA_ADMIN_USERNAME=jorge
LAIA_ADMIN_PASSWORD=dev-admin
LAIA_LLM_PROVIDER=deepseek
LAIA_LLM_API_KEY=sk-...
AGORA_BACKEND_PORT=8088
```

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# laia-init — Wizard de Instalacion

# laia-init — Wizard de Instalacion

> &#x1F4C5; 2026-05-18 | Shell tests verdes

## Proposito

Instalacion guiada de AGORA desde un host limpio. 8 pasos con defaults inteligentes.

## Archivos

| Archivo | Rol |
|---------|-----|
| `infra/dev/laia-init.sh` | Wizard principal (8 pasos) |
| `infra/dev/laia-init-checks.sh` | Pre-checks (LXD, deps, auth.json) |

## Modos

| Flag | Descripcion |
|------|-------------|
| (sin flags) | Interactivo: pregunta cada paso |
| `--non-interactive` | Lee de env vars, falla si faltan |
| `--dry-run` | Imprime que haria sin ejecutar |
| `--skip-images` | No reconstruye imagenes LXD |
| `--skip-first-user` | No provisiona el primer usuario |

## 8 pasos

1. `laia-init-checks.sh` — verifica LXD, git, jq, curl, auth.json
2. LXD defaults — storage pool, network bridge, perfiles
3. auth.json — verificacion/configuracion de OAuth
4. Prompt — nombre del admin, API key LLM, provider
5. rebuild-2 — construye imagenes LXD
6. rebuild-3 — provisiona laia-agora
7. seed-base-skills.sh — publica skills base
8. rebuild-4 — provisiona primer usuario + verificacion

## Env vars para non-interactive

```bash
LAIA_ADMIN_USERNAME=jorge
LAIA_ADMIN_PASSWORD=dev-admin
LAIA_LLM_PROVIDER=deepseek
LAIA_LLM_API_KEY=sk-...
AGORA_BACKEND_PORT=8088
```
