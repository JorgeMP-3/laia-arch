# WORKHARD — Especificación técnica

## Objetivo

Implementar una skill persistente en `~/.openclaw/skills/workhard/` que gestione trabajos largos mediante archivos de estado y scripts reutilizables.

## Estructura

```
~/.openclaw/skills/workhard/
├── SKILL.md
├── PROJECT_IDEA.md
├── TECHNICAL_SPEC.md
├── scripts/
│   ├── menu.sh
│   ├── init.sh
│   ├── investigate.sh
│   ├── questionnaire.sh
│   ├── plan.sh
│   ├── execute.sh
│   ├── checkpoint.sh
│   ├── verify-step.sh
│   ├── status.sh
│   └── resume.sh
├── references/
│   ├── templates/
│   │   ├── contexto.md
│   │   ├── todo.md
│   │   └── session.md
│   ├── phases.md
│   └── risk-levels.md
└── SPEC.md
```

## Directorio de trabajo

Cada proyecto vive en:

`~/.openclaw/workspace/workhard/WORK/[NOMBRE_PROYECTO]/`

Archivos esperados:

- `CONTEXTO.md`
- `TODO.md`
- `LOG.md`
- `NOTES.md`
- `SESSION.md`

Modo `super` añade:

- `INVESTIGATION.md`
- `QUESTIONNAIRE.md`
- `QUESTIONNAIRE_RESPONSES.md` opcional

## Modelo de datos

### `SESSION.md`

Campos persistentes:

- `project_name`
- `objective`
- `mode`
- `ia_mode`
- `phase`
- `current_step`
- `status`
- `created_at`
- `updated_at`
- `work_dir`

### `TODO.md`

Tabla principal:

| # | Descripción | Comando/Prompt | Riesgo | Estado | Completado |
|---|-------------|----------------|--------|--------|------------|

Estados esperados:

- `⏳` pendiente
- `🔄` en curso
- `✅` completado
- `❌` fallido
- `⏸` pausado

## Reglas de riesgo

- `low`: ejecuta automáticamente
- `medium`: advierte y confirma si hay TTY
- `high`: requiere confirmación explícita
- `critical`: requiere confirmación explícita y pausa si no hay TTY

## Reglas de ejecución

1. `plan.sh` genera pasos de 15-30 minutos.
2. `execute.sh` toma el primer paso pendiente.
3. `verify-step.sh` marca el resultado y actualiza el siguiente paso.
4. `checkpoint.sh` hace commit si el proyecto está en git y hay cambios.
5. `resume.sh` reanuda desde `SESSION.md`.

## Convención de comandos en `TODO.md`

- `SHELL:...` para comandos ejecutables por `execute.sh`
- `PROMPT:...` para pasos que requieren intervención de IA o revisión manual

## Integración esperada

- `/workhard [objetivo]` crea proyecto, planifica y ejecuta lo automatizable
- `/workhard super [objetivo]` investiga y deja cuestionario si faltan respuestas
- `/workhard resume` retoma la sesión
- `/workhard status` muestra el estado
- `/workhard abort` marca la sesión como abortada y limpia el puntero activo

## Testing mínimo

Caso de humo:

`/workhard "Crear un script Python que imprima Hola Mundo"`

Debe:

1. Crear el directorio del proyecto
2. Crear `CONTEXTO.md`, `TODO.md`, `LOG.md`, `NOTES.md`, `SESSION.md`
3. Ejecutar al menos un plan simple de extremo a extremo
4. Dejar `TODO.md` actualizado con pasos completados
