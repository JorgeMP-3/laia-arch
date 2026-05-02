# Fases de WORKHARD

## Convenciones de tipo en TODO.md

Cada paso en `TODO.md` puede ser de tres tipos:

### SHELL: — Comando ejecutable directamente
```
SHELL:cd ~/proyecto && npm run build
```
Ejecuta un comando de terminal directamente. Apropiado cuando el paso es automatizable sin intervención.

### PROMPT: — Requiere IA o intervención manual
```
PROMPT:Revisar el código y detectar errores de estilo en server.py
```
El paso requiere juicio, análisis o trabajo creativo. Se pausa hasta que alguien lo ejecuta. El trabajo se deja preparado para que la IA pueda tomarlo directamente.

### CHECK: — Hito verificable (novedad)
```
CHECK:El documento RA1.md tiene más de 200 líneas y cubre todos los puntos requeridos
```
Un CHECK marca un **hito cualitativo**, no un comando. Se marca como ✅ cuando se verifica manualmente que la condición se cumple. No es ni un comando ni un prompt — es un criterio de aceptación.

**Cuándo usar CHECK:**
- La calidad del trabajo no se puede medir con un comando (documentación, revisión, coherencia)
- Se quiere dejar claro qué significa "hecho" para un paso subjetivo
- El paso siguiente depende de que el anterior cumpla ciertos criterios

**Diferencias clave:**
| Tipo | ¿Se ejecuta? | ¿Se marca hecho? | ¿Ejemplo? |
|---|---|---|---|
| SHELL | Sí, automáticamente | Por script/verificación | `npm test` |
| PROMPT | No, pausa | Cuando alguien lo hace | Revisar texto |
| CHECK | No, es una condición | Cuando la condición se cumple | "Tiene más de 200 líneas" |

## 1. Configuración

- Elegir modo `normal` o `super`
- Elegir IA `single` o `dual`
- Guardar selección en `SESSION.md`

## 2. Entendimiento

- Registrar objetivo
- Definir alcance inicial
- En modo `super`, investigar y generar cuestionario

## 3. Planificación

- Dividir el trabajo en pasos pequeños
- Asignar riesgo a cada paso
- Generar `TODO.md`

## 4. Ejecución

- Ejecutar el siguiente paso pendiente
- Verificar resultado
- Actualizar `TODO.md`, `SESSION.md` y `LOG.md`
- Hacer checkpoint git si aplica

## 5. Cierre

- Dejar resumen del estado
- Marcar sesión como `complete`, `paused` o `aborted`
- Permitir `resume` cuando no esté completa
