---
name: workhard
description: Skill para trabajos largos y estructurados con fases, investigación opcional, planificación en TODO.md, ejecución paso a paso, checkpoints git y reanudación por SESSION.md. Úsala cuando el usuario escriba "/workhard", pida un proyecto complejo por fases, quiera dividir trabajo en pasos de 15-30 minutos, necesite resume/status, o quiera un modo super con investigación y cuestionario previo.
---

# WORKHARD

WORKHARD convierte un trabajo largo en un flujo persistente con archivos de estado dentro de `workspace/workhard/WORK/[proyecto]/`.

## Cuándo usarla

- Cuando el usuario escribe `/workhard ...`
- Cuando pide ejecutar un proyecto largo sin perder contexto
- Cuando hace falta un `TODO.md` como contrato entre planificación y ejecución
- Cuando el trabajo debe poder pausarse, reanudarse y auditarse

## Ruta rápida

1. Lee [SPEC.md](SPEC.md) para ver comandos, archivos y flujo.
2. Si necesitas detalle adicional, consulta:
- [PROJECT_IDEA.md](PROJECT_IDEA.md)
- [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md)
- [references/phases.md](references/phases.md)
- [references/risk-levels.md](references/risk-levels.md)

## Cómo enrutar el comando del usuario

- `/workhard [objetivo]`
  Ejecuta `scripts/init.sh --mode normal --ia single --objective "[objetivo]"`.
- `/workhard super [objetivo]`
  Ejecuta `scripts/init.sh --mode super --ia single --objective "[objetivo]"`.
- `/workhard resume`
  Ejecuta `scripts/resume.sh`.
- `/workhard status`
  Ejecuta `scripts/status.sh`.
- `/workhard abort`
  Ejecuta `scripts/init.sh abort`.
- `/workhard log`
  Ejecuta `scripts/init.sh log`.

Si el usuario quiere elegir manualmente modo o tipo de IA, usa `scripts/menu.sh` antes de `init.sh`, o pasa `--ia dual`.

## Reglas de operación

1. `TODO.md` es el contrato principal: cada paso necesita descripción, comando o prompt, riesgo y estado.
2. El trabajo siempre vive en `workspace/workhard/WORK/[NOMBRE_PROYECTO]/`.
3. `SESSION.md` es la fuente de verdad para reanudar.
4. Riesgos `high` y `critical` siempre requieren confirmación explícita antes de ejecutar.
5. Si un paso es `PROMPT:` y no hay automatización segura, pausa la sesión y deja el prompt listo para que la IA o el usuario lo ejecuten.
6. Si el proyecto está dentro de un repositorio git, ejecuta checkpoint después de cada paso verificado.

## Flujo

### 1. Configuración

- `menu.sh` elige `normal|super` y `single|dual`.
- Guarda la configuración en `SESSION.md`.

### 2. Entendimiento

- `normal`: el objetivo del usuario pasa directo a `CONTEXTO.md`.
- `super`: `investigate.sh` crea una investigación inicial y `questionnaire.sh` genera preguntas para afinar el alcance.

### 3. Planificación

- `plan.sh` divide el trabajo en pasos de 15-30 min.
- Genera `TODO.md` y deja `SESSION.md` listo para ejecutar.

### 4. Ejecución

- `execute.sh` toma el siguiente paso pendiente.
- Aplica gates según riesgo.
- Ejecuta, verifica, actualiza `TODO.md`, registra en `LOG.md` y hace checkpoint git si aplica.

### 5. Reanudación

- `resume.sh` reabre la sesión.
- Si el modo super estaba esperando respuestas, sintetiza `QUESTIONNAIRE_RESPONSES.md` en `CONTEXTO.md`.
- Si ya hay plan, continúa desde el siguiente paso.

## Archivos persistentes del proyecto

- `CONTEXTO.md`
- `TODO.md`
- `LOG.md`
- `NOTES.md`
- `SESSION.md`
- `INVESTIGATION.md` y `QUESTIONNAIRE.md` cuando el modo es `super`

## Notas de implementación

- Los scripts están pensados para poder correr solos desde terminal, pero también para ser invocados por la propia skill.
- Para objetivos genéricos, `plan.sh` puede generar pasos `PROMPT:` que requieren intervención de IA.
- Para casos simples conocidos, `plan.sh` intenta producir comandos `SHELL:` ejecutables de extremo a extremo.
