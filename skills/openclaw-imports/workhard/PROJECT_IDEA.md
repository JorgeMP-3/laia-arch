# WORKHARD — Skill de trabajo prolongado y sistemático

## Qué es

WORKHARD es una skill para OpenClaw orientada a trabajos largos y complejos. Su función es convertir un objetivo amplio en un flujo persistente con investigación opcional, planificación detallada, ejecución paso a paso y checkpoints verificables.

## Menú conceptual

```
1. Elegir modo
   - normal
   - super

2. Elegir tipo de IA
   - single
   - dual

3. Ejecutar el flujo
```

## Flujo principal

### Fase 1 — Configuración

- Selección de modo y tipo de IA
- Persistencia de configuración en `SESSION.md`

### Fase 2 — Entendimiento

- `normal`: recibe el objetivo y crea el contexto base
- `super`: investiga, genera cuestionario y sintetiza respuestas antes de planificar

### Fase 3 — Planificación

- Crea carpeta de trabajo
- Genera `CONTEXTO.md`
- Genera `TODO.md` con pasos pequeños, riesgos y estado

### Fase 4 — Ejecución

- Lee el siguiente paso desde `TODO.md`
- Aplica approval gates
- Ejecuta, verifica y actualiza estado
- Registra en `LOG.md`
- Hace checkpoint git si hay repositorio

### Fase 5 — Cierre

- Resume qué se completó
- Señala siguientes pasos opcionales
- Deja la sesión lista para `resume` o marcada como `complete`

## Diferencia entre modos

### `normal`

- Objetivo directo
- Contexto breve
- Planificación inmediata

### `super`

- Investigación previa
- Preguntas dinámicas
- Contexto enriquecido antes del plan

## Diferencia entre `single` y `dual`

### `single`

Una sola IA hace entendimiento, plan y ejecución.

### `dual`

La primera IA planifica y la segunda ejecuta usando `TODO.md` como contrato.

## Archivos del proyecto

Todo se guarda en:

`~/.openclaw/workspace/workhard/WORK/[NOMBRE_PROYECTO]/`

- `CONTEXTO.md`: objetivo, scope, decisiones, restricciones
- `TODO.md`: pasos, comandos/prompts, riesgos y estado
- `LOG.md`: historial con timestamp
- `NOTES.md`: notas libres
- `SESSION.md`: modo, fase, paso actual y estado

## Reglas clave

1. Cada paso debe ser pequeño y verificable.
2. `TODO.md` refleja siempre el estado real.
3. Riesgos `high` y `critical` no se ejecutan sin aprobación.
4. Cada paso completado intenta dejar el proyecto en estado limpio.
5. Si algo falla, la sesión se pausa con contexto suficiente para reanudar.
