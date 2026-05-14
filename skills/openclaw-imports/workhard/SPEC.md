# WORKHARD — Referencia rápida

## Rutas

- Skill: `~/.openclaw/skills/workhard/`
- Workspace: `~/.openclaw/workspace/workhard/WORK/[proyecto]/`

## Comandos de usuario

- `/workhard [objetivo]`
- `/workhard super [objetivo]`
- `/workhard resume`
- `/workhard status`
- `/workhard abort`
- `/workhard log`

## Scripts equivalentes

- `scripts/init.sh --objective "[objetivo]"`
- `scripts/init.sh --mode super --objective "[objetivo]"`
- `scripts/resume.sh`
- `scripts/status.sh`
- `scripts/init.sh abort`
- `scripts/init.sh log`

## Fases

1. Configuración
2. Entendimiento e investigación
3. Planificación
4. Ejecución
5. Cierre o pausa

## Archivos del proyecto

- `CONTEXTO.md`
- `TODO.md`
- `LOG.md`
- `NOTES.md`
- `SESSION.md`

## Riesgo

- `low`: auto
- `medium`: confirmar si hay TTY
- `high`: approval obligatorio
- `critical`: approval explícito

## Convención en TODO

- `SHELL:...`
- `PROMPT:...`

## Reanudación

- `SESSION.md` manda
- `CURRENT_PROJECT` en el workspace apunta al proyecto activo
- `resume.sh` sintetiza respuestas del cuestionario si existen y sigue el flujo
