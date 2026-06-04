# CLAUDE.md — LAIA ECOSYSTEM (código de producto)

> `~/LAIA` es el **código fuente del ecosistema LAIA** (capa LAIA-ARCH). Al instalar se copia a
> `/opt/laia` (`laia-release`) → trátalo como **artefacto de producto**.
> `AGENTS.md` es un symlink a este archivo.
>
> La **doctrina de cómo trabajan las IAs y el catálogo de skills NO viven aquí**: viven en
> **`~/laia-developers`** (desplegados también en la config global de cada agente). Léelas primero:
> - Doctrina (la idea, el equipo, mentalidad, workflow, guardarraíles) → `~/laia-developers/AGENTS.md`
> - El server (tenants, seguridad, GPU) → `~/laia-developers/SERVER.md`
>
> Este doc es lo **específico de LAIA**: su tracker, su git, su operativa de tests/estilo/release.

## Contexto del ecosistema

**Canónico (visión): `LAIA_ECOSYSTEM.md`** (este repo) — **no se edita sin Jorge.**
ANTES DE HACER NADA EN LAIA, léelo (o el resumen: `~/laia-developers/LAIA_ECOSYSTEM-primer.md`).

**Proveniencia del core**: `.laia-core/` (el runtime del agente) es un fork de **Hermes Agent
v0.11.0** (Nous Research, MIT — `github.com/NousResearch/hermes-agent`), renombrado en masa
`hermes`→`laia` (~1.350 refs). **NO es un fork git**: no hay remote upstream; el código
original quedó en `origin/archive/hermes-upstream`. Upstream sigue muy activo (v0.12+) →
integrar mejoras suyas = **cherry-pick adaptado, nunca merge ciego** (estrategia:
`.plans/PLAN_SYNC_UPSTREAM_HERMES_v0.14.md`). El install viejo de prod (`/opt/laia-v0.11.0`)
se llama "era-Hermes" por esto.

## Tracker e historia de LAIA → `~/laia-developers/workflow-main/`

- Bugs → `PROBLEMS.md` · Planes/PRDs → `plans/` · Bitácora → `CHANGELOG.md` · Seguridad →
  `SECURITY.md` · Drafts → `_inbox/` · Handoffs → `handoffs/` · Índice → `00-start-here.md`.
- Runbook de release (promote, deploy, rollback, hotfix) → `release-flow.md`.
- **Cierre de turno** (obligatorio): `~/laia-developers/AGENTS.md` §6.7 — las entradas van a
  esos ficheros de `workflow-main`, nunca a `/tmp`.

## Git / release (LAIA)

- `main` = desarrollo validado (**nunca commit directo**) · `stable` = producción (el instalador
  apunta aquí; solo recibe **fast-forward** desde `main` o hotfix aprobado) · `wip/<agente>/<tarea>`
  = trabajo · tags `vX.Y.Z` solo sobre `stable`.
- **1 tarea = 1 branch = 1 PR.** Manual operativo y errores típicos →
  `~/laia-developers/workflow-main/git-github-guide.md` + `release-flow.md`.

### Criterios para promover una release (lógica; comandos en `release-flow.md`)

1. La VM dev instala/clona end-to-end. 2. `tests/installer/run_all.sh` pasa. 3. Backend
(`make test`) y/o typecheck de frontend pasan, o los fallos quedan documentados.
4. `CHANGELOG.md` al día. 5. **Sin secretos nuevos en git.**

- **Deploy**: `laia-release` versiona en `/opt/laia-vX.Y.Z` y mueve el symlink `/opt/laia`;
  verificación `laia diagnose` + `curl /api/health`. **Rollback**: `laia-rollback` (revierte el
  symlink en segundos).
- ⚠️ **Trampa con containers**: `laia-release` NO reconstruye imágenes LXD. Si el release toca
  `agora-backend/`, `laia-executor/`, `.laia-core/` o `infra/lxd/`, hay que reconstruir
  imágenes a mano (`rebuild-2-images.sh`) antes de validar.

## Tests (obligatorio — la regla general está en AGENTS.md §6.3)

**Toda integración nueva lleva su test en `~/LAIA/tests/`** (naming `test_<area>.{sh,py}` o
subcarpeta si tiene varios archivos). Antes de declarar "hecho": la **suite completa**:

```bash
# Backend (pytest)
cd ~/LAIA/services/agora-backend && .venv/bin/python -m pytest tests/ -v
# Shell (host/container/orquestación)
cd ~/LAIA/tests && ./test_preflight.sh && ./test_smoke_scripts.sh
# Frontend (typecheck)
cd ~/LAIA/laia-ui && npx tsc --noEmit -p packages/arch-app/tsconfig.json && \
                     npx tsc --noEmit -p packages/agora-app/tsconfig.json
# Go (tooling de host, p.ej. infra/resourced)
cd ~/LAIA/infra/<modulo> && gofmt -l . && go vet ./... && go test ./...
```

- Niveles: **suite local** (lo anterior) → **CI en cada PR** (`.github/workflows/ci.yml`:
  pytest py3.11+py3.14, installer host-free, integrity perfil `ci`; lo que necesita host real
  se reporta como **SKIP documentado** — nada de caps silenciosos) → **integridad con
  ecosistema vivo** (LXD + containers: a mano en la VM `laia-dev` o vía monitor).
- Tests con dependencia viva (container/red/backend) → **skip limpio** si falta, jamás error
  críptico. Tests = contratos, no change-detectors (`workflow-main/design-rules.md`).

## Estilo de código

- **Python**: PEP 8, type hints (`from __future__ import annotations`), `pydantic` para modelos
  de datos, `sqlite3` de stdlib (no ORM).
- **TypeScript/React**: componentes funcionales con hooks, tokens `--d-*` del design system,
  `@laia/ui` para componentes compartidos.
- **Go** (tooling de host): stdlib-first, deps mínimas pineadas, binario estático (CGO=0).
- **Shell**: `#!/usr/bin/env bash` + `set -euo pipefail`. Google Shell Style.
- **Idioma**: comentarios y docstrings en **inglés** (gate T-DOC del CI); docs en español.
- Antes de push: la parte de la suite que toque tu cambio (mínimo `make test` backend o
  typecheck frontend, según aplique).

## Paths de LAIA

| Path | Qué contiene |
|---|---|
| `~/LAIA/` | Código del proyecto (este repo). |
| `~/LAIA/tests/` | Tests del ecosistema. **Toda integración nueva lleva test aquí.** |
| `/srv/laia/` | Datos operacionales + secretos (fuente de verdad). No tocar sin OK. |
| `/opt/laia/` | Copia instalada (producción local del host). |
| `~/LAIA-ARCH/` | Mesa viva del operador (workspaces, memories, skills, SOUL.md). |
| `~/laia-developers/` | Base de los agentes: doctrina, skills, `workflow-main`. |

## Si encuentras una contradicción

Gana `LAIA_ECOSYSTEM.md`. Si te bloquea, **escala a Jorge antes de actuar**.
