# CLAUDE.md — LAIA-ARCH (código de producto)

> `~/LAIA` es el **código fuente del ecosistema LAIA** (capa LAIA-ARCH). Al instalar se copia a
> `/opt/laia` (`laia-release`) → trátalo como **artefacto de producto**.
>
> La **doctrina de cómo trabajan las IAs y el catálogo de skills NO viven aquí**: viven en
> **`~/laia-developers`** (desplegados también en la config global de cada agente). Léelas primero:
> - Doctrina compartida (protocolos, guardarraíles, qué no hacer) → `~/laia-developers/AGENTS.md`
> - El server (tenants, seguridad, GPU) → `~/laia-developers/SERVER.md`

## Contexto del ecosistema

**Canónico (visión): `LAIA_ECOSYSTEM.md`** (este repo) — **no se edita sin Jorge.**
ANTES DE HACER NADA EN LAIA, léelo (también accesible como `~/laia-developers/LAIA_ECOSYSTEM.md`, symlink auto-actualizado).

## Tracker e historia de LAIA → `~/laia-developers/workflow-main/`

El workflow de este proyecto vivía en `~/LAIA/workflow/` y se movió íntegro (2026-06-01):

- Bugs → `PROBLEMS.md` · Planes/PRDs → `plans/` · Bitácora → `CHANGELOG.md` · Seguridad →
  `SECURITY.md` · Drafts → `_inbox/` · Handoffs → `handoffs/` · Índice → `00-start-here.md`.
- Flujo dev→test→prod explicado → `dev-workflow.md` · runbook de release → `release-flow.md`.
- **Cierre de turno** (obligatorio): las entradas van a esos ficheros de `workflow-main`, no a `/tmp`.

## Git / release (LAIA)

- `main` = desarrollo validado (**nunca commit directo**) · `stable` = producción (el instalador
  apunta aquí) · `wip/<agente>/<tarea>` = trabajo · tags `vX.Y.Z` solo sobre `stable`.
- **1 tarea = 1 branch = 1 PR.** Modelo completo y errores típicos →
  `~/laia-developers/workflow-main/git-github-guide.md` + `release-flow.md`.
- Antes de declarar "hecho": suite completa (`tests/`, ver `workflow-main/02-how-to-work.md` §Tests).

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
