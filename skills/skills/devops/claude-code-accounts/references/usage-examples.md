# Claude Code — ejemplos prácticos de uso

## 1) Análisis de un proyecto en Docker

**Cuándo usar:** cuando el proyecto vive dentro de contenedores y queremos entenderlo sin tocarlo.

**Cuenta:** Maribel

**Prompt recomendado:**
> Analiza este proyecto y dime qué información vale la pena guardar para Hermes. Identifica archivos clave, riesgos antes de tocar nada y el orden de lectura recomendado. No modifiques archivos.

**Ejemplo de proyectos:**
- Areté v7
- PixelCore
- Presentaciones

---

## 2) Inspección rápida en el host

**Cuándo usar:** cuando la tarea está fuera de Docker o es una comprobación local.

**Cuenta:** Jorge

**Prompt recomendado:**
> Revisa esta ruta local y resume solo lo útil para Hermes: estructura, archivos clave y posibles riesgos. No hagas cambios.

---

## 3) Antes de hacer cambios

**Objetivo:** evitar gastar toques innecesarios y no tocar nada sensible sin plan.

**Checklist:**
1. Identificar entorno (host o Docker)
2. Elegir cuenta correcta
3. Leer contexto mínimo
4. Confirmar si hace falta cambiar algo
5. Si basta con contexto, parar ahí

---

## 4) Uso prudente de Maribel

Maribel es una cuenta compartida, así que conviene:
- evitar exploraciones amplias sin objetivo
- no iterar en prompts triviales
- pedir primero una síntesis útil
- parar en cuanto el contexto suficiente ya esté claro

---

## 5) Uso prudente de Jorge

Jorge también debe usarse con control:
- no convertirlo en agente de exploración infinita
- priorizar tareas de valor real
- usar prompts concretos
- evitar duplicar trabajo que ya está en memoria o en guías

---

## 6) Regla de decisión rápida

| Situación | Cuenta |
|---|---|
| Tarea dentro de Docker | Maribel |
| Tarea en host | Jorge |
| Tarea ambigua | Determinar entorno primero |
| Tarea de bajo valor | No gastar toque |

---

## 7) Qué devolver

Claude Code debe devolver solo:
- archivos clave
- riesgos
- contexto útil para Hermes
- pasos siguientes

No hace falta ruido ni explicaciones largas.
