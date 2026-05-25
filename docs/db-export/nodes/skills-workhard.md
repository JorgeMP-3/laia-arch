# Workhard Skill

## Metadata

- ID: `97`
- Slug: `skills-workhard`
- Kind: `doc`
- Status: `active`
- Filename: `skills-workhard.md`
- Parent: `hermes`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:02.838965+00:00`
- Updated at: `2026-05-08T08:34:02.838965+00:00`
- Aliases: `skills-workhard`

## Summary

Skill para trabajos largos y estructurados con fases, investigacion opcional, planificacion en TODO.

## Body

# Workhard Skill

# Integrated Tools — Workhard

## Resumen

Skill para trabajos largos y estructurados con fases, investigacion opcional, planificacion en TODO.md, ejecucion paso a paso, checkpoints git y reanudacion via SESSION.md.

**Ubicacion:** `skills/openclaw-imports/workhard/SKILL.md`

## Cuando usar

- Usuario escribe `/workhard`
- Pide proyecto complejo por fases
- Quiere dividir trabajo en pasos de 15-30 minutos
- Necesita resume/status
- Quiere modo super con investigacion y cuestionario previo

## Comandos

```bash
/workhard [objetivo]       # modo normal, ia single
/workhard super [objetivo] # modo super, ia single
/workhard resume           # reanudar sesion
/workhard status           # ver estado
/workhard abort            # abortar
/workhard log              # ver log
```

Tambien disponible via menu:

```bash
scripts/menu.sh            # elegir modo y tipo de IA
scripts/init.sh --mode normal --ia single --objective "..."
scripts/init.sh --mode super --ia dual --objective "..."
```

## Modos de operacion

### Normal
- Objetivo del usuario pasa directo a `CONTEXTO.md`
- `plan.sh` divide en pasos de 15-30 min
- `execute.sh` ejecuta cada paso con gates de riesgo

### Super
- `investigate.sh` crea investigacion inicial
- `questionnaire.sh` genera preguntas para afinar alcance
- Respuestas se sintetizan en `CONTEXTO.md`
- Planifica con contexto enriquecido

## Archivos persistentes del proyecto

Todos viven en `workspace/workhard/WORK/[NOMBRE_PROYECTO]/`:

| Archivo | Proposito |
|---|---|
| `CONTEXTO.md` | Contexto inicial o enriquecido |
| `TODO.md` | Contrato de pasos: descripcion, comando/prompt, riesgo, estado |
| `LOG.md` | Historial de ejecucion |
| `NOTES.md` | Notas varias |
| `SESSION.md` | Fuente de verdad para reanudacion |
| `INVESTIGATION.md` | Mode super: investigacion inicial |
| `QUESTIONNAIRE.md` | Mode super: preguntas para usuario |

## Estructura de TODO.md

Cada paso:
```
## Paso 1: Descripcion
status: pending
risk: low|medium|high|critical
command: SHELL:comando ejecutable
prompt: PROMPT:prompt para IA
```

**Reglas:**
- `TODO.md` es el contrato: cada paso necesita descripcion, comando/prompt, riesgo, estado
- Riesgos `high` y `critical` requieren confirmacion antes de ejecutar
- Si paso es `PROMPT:` sin automatizacion segura, pausar y dejar listo

## Flujo completo

### 1. Configuracion
```bash
menu.sh  # elige normal|super y single|dual
# guarda en SESSION.md
```

### 2. Entendimiento
- **normal**: objetivo → CONTEXTO.md
- **super**: investigate.sh + questionnaire.sh → CONTEXTO.md enriquecido

### 3. Planificacion
```bash
plan.sh  # genera TODO.md
# deja SESSION.md listo para ejecutar
```

### 4. Ejecucion
```bash
execute.sh  # siguiente paso pendiente
# gates segun riesgo
# ejecuta, verifica, actualiza TODO.md
# registra en LOG.md
# checkpoint git si aplica
```

### 5. Reanudacion
```bash
resume.sh  # reabre sesion
# si super esperando respuestas: sintetiza en CONTEXTO.md
# si ya hay plan: continua desde siguiente paso
```

## Checkpoints git

Si el proyecto esta dentro de un repositorio git, se ejecuta checkpoint despues de cada paso verificado:

```bash
git add -A
git commit -m "Checkpoint: paso X completado"
```

## Detener/Abortar

```bash
/workhard abort  # ejecuta init.sh abort
```

## Limitaciones

- Para objetivos genericos, `plan.sh` puede generar pasos `PROMPT:` que requieren intervencion de IA
- Para casos simples conocidos, `plan.sh` intenta producir comandos `SHELL:` ejecutables de extremo a extremo
- Los scripts pueden correr solos desde terminal o ser invocados por la skill

## Nodos relacionados

- `integrated-tools` — indice maestro
- `integrated-openclaw` — gateway OpenClaw
- `integrated-workspace-tools` — skills workspace


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Workhard Skill

# Workhard Skill

# Integrated Tools — Workhard

## Resumen

Skill para trabajos largos y estructurados con fases, investigacion opcional, planificacion en TODO.md, ejecucion paso a paso, checkpoints git y reanudacion via SESSION.md.

**Ubicacion:** `skills/openclaw-imports/workhard/SKILL.md`

## Cuando usar

- Usuario escribe `/workhard`
- Pide proyecto complejo por fases
- Quiere dividir trabajo en pasos de 15-30 minutos
- Necesita resume/status
- Quiere modo super con investigacion y cuestionario previo

## Comandos

```bash
/workhard [objetivo]       # modo normal, ia single
/workhard super [objetivo] # modo super, ia single
/workhard resume           # reanudar sesion
/workhard status           # ver estado
/workhard abort            # abortar
/workhard log              # ver log
```

Tambien disponible via menu:

```bash
scripts/menu.sh            # elegir modo y tipo de IA
scripts/init.sh --mode normal --ia single --objective "..."
scripts/init.sh --mode super --ia dual --objective "..."
```

## Modos de operacion

### Normal
- Objetivo del usuario pasa directo a `CONTEXTO.md`
- `plan.sh` divide en pasos de 15-30 min
- `execute.sh` ejecuta cada paso con gates de riesgo

### Super
- `investigate.sh` crea investigacion inicial
- `questionnaire.sh` genera preguntas para afinar alcance
- Respuestas se sintetizan en `CONTEXTO.md`
- Planifica con contexto enriquecido

## Archivos persistentes del proyecto

Todos viven en `workspace/workhard/WORK/[NOMBRE_PROYECTO]/`:

| Archivo | Proposito |
|---|---|
| `CONTEXTO.md` | Contexto inicial o enriquecido |
| `TODO.md` | Contrato de pasos: descripcion, comando/prompt, riesgo, estado |
| `LOG.md` | Historial de ejecucion |
| `NOTES.md` | Notas varias |
| `SESSION.md` | Fuente de verdad para reanudacion |
| `INVESTIGATION.md` | Mode super: investigacion inicial |
| `QUESTIONNAIRE.md` | Mode super: preguntas para usuario |

## Estructura de TODO.md

Cada paso:
```
## Paso 1: Descripcion
status: pending
risk: low|medium|high|critical
command: SHELL:comando ejecutable
prompt: PROMPT:prompt para IA
```

**Reglas:**
- `TODO.md` es el contrato: cada paso necesita descripcion, comando/prompt, riesgo, estado
- Riesgos `high` y `critical` requieren confirmacion antes de ejecutar
- Si paso es `PROMPT:` sin automatizacion segura, pausar y dejar listo

## Flujo completo

### 1. Configuracion
```bash
menu.sh  # elige normal|super y single|dual
# guarda en SESSION.md
```

### 2. Entendimiento
- **normal**: objetivo → CONTEXTO.md
- **super**: investigate.sh + questionnaire.sh → CONTEXTO.md enriquecido

### 3. Planificacion
```bash
plan.sh  # genera TODO.md
# deja SESSION.md listo para ejecutar
```

### 4. Ejecucion
```bash
execute.sh  # siguiente paso pendiente
# gates segun riesgo
# ejecuta, verifica, actualiza TODO.md
# registra en LOG.md
# checkpoint git si aplica
```

### 5. Reanudacion
```bash
resume.sh  # reabre sesion
# si super esperando respuestas: sintetiza en CONTEXTO.md
# si ya hay plan: continua desde siguiente paso
```

## Checkpoints git

Si el proyecto esta dentro de un repositorio git, se ejecuta checkpoint despues de cada paso verificado:

```bash
git add -A
git commit -m "Checkpoint: paso X completado"
```

## Detener/Abortar

```bash
/workhard abort  # ejecuta init.sh abort
```

## Limitaciones

- Para objetivos genericos, `plan.sh` puede generar pasos `PROMPT:` que requieren intervencion de IA
- Para casos simples conocidos, `plan.sh` intenta producir comandos `SHELL:` ejecutables de extremo a extremo
- Los scripts pueden correr solos desde terminal o ser invocados por la skill

## Nodos relacionados

- `integrated-tools` — indice maestro
- `integrated-openclaw` — gateway OpenClaw
- `integrated-workspace-tools` — skills workspace


> 📅 Documentado: 2026-05-08
