# LAIA Tools Plan

## Metadata

- ID: `105`
- Slug: `laia-tools-plan`
- Kind: `doc`
- Status: `active`
- Filename: `laia-tools-plan.md`
- Parent: `herramientas-cli-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:05.812869+00:00`
- Updated at: `2026-05-08T08:34:05.812869+00:00`
- Aliases: `laia-tools-plan`

## Summary

**Estado:** Fase 1 en curso

## Body

# Plan: LAIA Tools — Mejora y Nuevas Herramientas

# Plan: LAIA Tools — Mejora y Nuevas Herramientas

**Estado:** Fase 1 en curso
**Fecha:** 2026-05-07
**Última actualización:** 2026-05-07 — `laia-status` completado

---

## Fase 1 — Fundamentos ✅/⏳

| # | Herramienta | Estado | Implementación |
|---|-------------|--------|----------------|
| 1 | `laia-status` | ✅ **DONE** | `/home/laia-arch/LAIA/.laia-arch/bin/laia-status` (365 líneas, 12KB) |
| 2 | `laia-health` | ⏳ Pendiente | — |
| 3 | `laia-logs` | ⏳ Pendiente | — |

---

## Fase 2 — Docker y servidor

| # | Herramienta | Estado |
|---|-------------|--------|
| 4 | `laia-dock` | ⏳ Pendiente |
| 5 | `laia-tunnel` | ⏳ Pendiente |

---

## Fase 3 — Seguridad y SSH

| # | Herramienta | Estado |
|---|-------------|--------|
| 6 | `laia-ssh` | ⏳ Pendiente |
| 7 | `unpack-laia-secrets` | ⏳ Pendiente |

---

## Fase 4 — Mejoras de existentes

| # | Herramienta | Estado |
|---|-------------|--------|
| 8 | Mejorar `clone-laia` | ⏳ Pendiente |
| 9 | Mejorar `gsave` | ⏳ Pendiente |
| 10 | Mejorar `laia-restart` | ⏳ Pendiente |
| 11 | Mejorar `hermes-start` | ⏳ Pendiente |

---

## Fase 5 — Extras

| # | Herramienta | Estado |
|---|-------------|--------|
| 12 | `laia-backup` | ⏳ Pendiente |
| 13 | `laia-update` | ⏳ Pendiente |

---

## Detalle: `laia-status` (completado)

**Ubicación:** `/home/laia-arch/LAIA/.laia-arch/bin/laia-status`
**Líneas:** 365 | **Tamaño:** 12KB | **Fecha:** 2026-05-07

### Flags implementados
- (sin args) — vista completa de todos los servicios
- `--short` — una línea por servicio con icono ✓/─/✗
- `--json` — JSON válido con timestamp ISO8601, overall: ok|degraded
- `--watch` — loop clear + render cada 2s, Ctrl+C limpio vía trap
- `--logs N` — tail de gateway/workspace-ui/agent/errors, filtrable con `--service`
- `--service SVC` — matching por substring
- `--help` / `-h`

### Servicios monitorizados
- hermes.service (systemd)
- workspace-ui (:8077 via lsof)
- tui_gateway (pgrep)
- claude-secondary (Docker)
- nginx (systemd/proc)
- cloudflared (systemd/proc)

### Exit codes
- 0 = todo OK
- 1 = algún servicio en fallo
- 2 = uso incorrecto

### Notas técnicas
- Colores ANSI solo si `[ -t 1 ]`
- Output útil a stdout, errores a stderr
- Verificado con `bash -n`
- Estado real: hermes ✓, tui_gateway ✓, nginx ✓, cloudflared ✓ | workspace-ui ✗, claude-secondary ✗


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `herramientas-cli-area` (Herramientas CLI y Scripts) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA Tools Plan

# Plan: LAIA Tools — Mejora y Nuevas Herramientas

# Plan: LAIA Tools — Mejora y Nuevas Herramientas

**Estado:** Fase 1 en curso
**Fecha:** 2026-05-07
**Última actualización:** 2026-05-07 — `laia-status` completado

---

## Fase 1 — Fundamentos ✅/⏳

| # | Herramienta | Estado | Implementación |
|---|-------------|--------|----------------|
| 1 | `laia-status` | ✅ **DONE** | `/home/laia-arch/LAIA/.laia-arch/bin/laia-status` (365 líneas, 12KB) |
| 2 | `laia-health` | ⏳ Pendiente | — |
| 3 | `laia-logs` | ⏳ Pendiente | — |

---

## Fase 2 — Docker y servidor

| # | Herramienta | Estado |
|---|-------------|--------|
| 4 | `laia-dock` | ⏳ Pendiente |
| 5 | `laia-tunnel` | ⏳ Pendiente |

---

## Fase 3 — Seguridad y SSH

| # | Herramienta | Estado |
|---|-------------|--------|
| 6 | `laia-ssh` | ⏳ Pendiente |
| 7 | `unpack-laia-secrets` | ⏳ Pendiente |

---

## Fase 4 — Mejoras de existentes

| # | Herramienta | Estado |
|---|-------------|--------|
| 8 | Mejorar `clone-laia` | ⏳ Pendiente |
| 9 | Mejorar `gsave` | ⏳ Pendiente |
| 10 | Mejorar `laia-restart` | ⏳ Pendiente |
| 11 | Mejorar `hermes-start` | ⏳ Pendiente |

---

## Fase 5 — Extras

| # | Herramienta | Estado |
|---|-------------|--------|
| 12 | `laia-backup` | ⏳ Pendiente |
| 13 | `laia-update` | ⏳ Pendiente |

---

## Detalle: `laia-status` (completado)

**Ubicación:** `/home/laia-arch/LAIA/.laia-arch/bin/laia-status`
**Líneas:** 365 | **Tamaño:** 12KB | **Fecha:** 2026-05-07

### Flags implementados
- (sin args) — vista completa de todos los servicios
- `--short` — una línea por servicio con icono ✓/─/✗
- `--json` — JSON válido con timestamp ISO8601, overall: ok|degraded
- `--watch` — loop clear + render cada 2s, Ctrl+C limpio vía trap
- `--logs N` — tail de gateway/workspace-ui/agent/errors, filtrable con `--service`
- `--service SVC` — matching por substring
- `--help` / `-h`

### Servicios monitorizados
- hermes.service (systemd)
- workspace-ui (:8077 via lsof)
- tui_gateway (pgrep)
- claude-secondary (Docker)
- nginx (systemd/proc)
- cloudflared (systemd/proc)

### Exit codes
- 0 = todo OK
- 1 = algún servicio en fallo
- 2 = uso incorrecto

### Notas técnicas
- Colores ANSI solo si `[ -t 1 ]`
- Output útil a stdout, errores a stderr
- Verificado con `bash -n`
- Estado real: hermes ✓, tui_gateway ✓, nginx ✓, cloudflared ✓ | workspace-ui ✗, claude-secondary ✗


> 📅 Documentado: 2026-05-08
