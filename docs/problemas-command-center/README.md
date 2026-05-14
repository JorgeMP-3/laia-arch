# Problemas del Command Center — Sesión 2026-05-07

## Sesión de pruebas del 7 de mayo de 2026

Documento donde se registran todos los problemas descubiertos mientras se probaba el Command Center (herramienta de orquestación multi-agente de Hermes Agent).

---

## Problema 1: `claude-code-cc2` con `permission_mode=bypass` — muerte instantánea

**Síntoma:** Al hacer spawn de `claude-code-cc2` con `permission_mode: "bypass"`, la terminal muere a los ~0 segundos tras mostrar la confirmación de permisos.

**Comando exacto:**
```python
command_center_spawn(
    agent_type="claude-code-cc2",
    cwd="/home/laia-arch/LAIA",
    label="cc2 test",
    permission_mode="bypass",
    require_user_approval=False
)
command_center_inject(terminal_id, prompt, press_enter=True, require_user_approval=False)
```

**Resultado:** Terminal muerta en <1s. La respuesta del inject fue `pending_approval=true` (el approval se ignora porque require_user_approval=False), pero la terminal ya no existía cuando se intentó injectar.

**Hipótesis:** El proceso de Claude Code (Maribel) recibe las flags de skip-permissions, confirma internamente, y el proceso padre (PTY shell) muere por algún motivo. Podría estar relacionado con el sandbox bwrap.

**Impacto:** No se puede usar `claude-code-cc2` con la sesión de Maribel en Command Center.

---

## Problema 2: `claude-code-planner` con `permission_mode=bypass` — muerte instantánea

**Síntoma:** Mismo comportamiento que cc2. Spawn con `bypass`, terminal muerta en ~0s.

**Comando exacto:**
```python
command_center_spawn(
    agent_type="claude-code-planner",
    cwd="/home/laia-arch/LAIA",
    permission_mode="bypass",
    require_user_approval=False
)
```

**Resultado:** Muere antes de poder injectar nada.

**Impacto:** No se puede usar bypass con ningún agente claude-code en esta configuración.

---

## Problema 3: `claude-code-planner` con `permission_mode=default` — muerte tras inject

**Síntoma:** Spawn sin bypass funciona (terminal viva). Pero tras injectar un prompt de ~1329 bytes, el agente procesa el paste pero muere antes de ejecutar acciones.

**Flujo:**
1. Spawn `claude-code-planner` con `permission_mode: "default"`, `require_user_approval: False` → terminal viva ✅
2. `command_center_inject(id, texto_largo)` → pending_approval, se aprueba manualmente en UI → texto inyectado ✅
3. Agente procesa el paste (se ve en output), pero muere sin producir ningún resultado
4. Terminal pasa a estado "HTTP 404: Terminal not found"

**Prompt inyectado (resumen):**
- Leer el plan existente en workspace `laia-arch` (nodo `laia-tools-plan`)
- Inventariar los scripts en `/home/laia-arch/LAIA/.laia-arch/bin/`
- Crear un plan expandido en `/home/laia-arch/LAIA/workspaces/laia-arch/code/laia-tools/PLAN_EXPANDIDO.md`

**Hipótesis:** El prompt era demasiado largo (1329 bytes) para injectar seguido, o el sandbox bwrap no permite que Claude Code ejecute operaciones de filesystem fuera de su working directory, o el proceso padre del PTY muere por alguna señal.

**Verificación:** El archivo `PLAN_EXPANDIDO.md` nunca se creó — la carpeta `code/laia-tools/` estaba vacía.

**Impacto:** No se puede delegar trabajo real a Claude Code via inject. El agente inicia pero no completa ninguna tarea.

---

## Problema 4: Sandbox bwrap — restricciones filesystem

**Síntoma:** Los agentes spawn con sandbox bwrap. Parece que hay restricciones sobre qué rutas pueden escribir.

**Nota:** No se verificó directamente pero es la hipótesis más probable para los fallos anteriores.

**Impacto:** Posible incompatibilidad entre el trabajo asignado (escribir archivos en `code/`) y las restricciones del sandbox.

---

## Problema 5: Flujo de approval confuso

**Síntoma:** `command_center_inject` con `require_user_approval=False` igualmente devuelve `pending_approval=True`. El approval sigue apareciendo aunque se diga que no se requiere.

**Comportamiento observado:**
```
Injected, waiting for approval...
pending_approval=true
```

**Impacto:** Confusión sobre si el texto se va a inyectar o no. Hay que ir a la UI a aprobar manualmente aunque `require_user_approval=False`.

---

## Configuración del entorno

```
Servidor: laia-arch (Dell OptiPlex 9020)
SO: Ubuntu 24.04
Hermes: instalación en ~/laia-arch/hermes-agent/venv/
Sandbox: bwrap (bubblewrap) activo por defecto
Cuentas Claude Code:
  - Jorge (host, default): ~/.claude/
  - Maribel (Docker, /home/familiamp/.claude/): CLARAUDE_CONFIG_DIR=/home/familiamp/.claude
```

---

## Soluciones parciales probadas

| Intento | Resultado |
|---------|-----------|
| Spawn cc2 con bypass | ❌ Muere instantáneamente |
| Spawn planner con bypass | ❌ Muere instantáneamente |
| Spawn planner sin bypass, inject largo | ❌ Muere tras procesar paste |
| Spawn bash + exec claude manualmente | ⏳ No probado aún |

---

## Preguntas abiertas

1. ¿Por qué el bypass causa muerte instantánea del proceso? ¿Es un bug en Hermes o en Claude Code?
2. ¿El sandbox bwrap está permitiendo o denegando escrituras en `code/`?
3. ¿Funcionaría si el prompt se inyectara en partes más pequeñas?
4. ¿Hay alguna forma de spawn sin sandbox bwrap para compar?
5. ¿El problema es específico de esta cuenta Maribel o pasa con cualquier claude-code?

---

## Técnicas de debugging aplicadas

- `command_center_list` — ver estado de terminales
- `command_center_read_all` — snapshot rápido
- `command_center_read(id, from_line=N)` — lectura incremental
- `command_center_wait(id, timeout=5)` — esperar y ver si revive
- `command_center_wait_all(ids, timeout=90)` — esperar en paralelo
- Búsqueda en sesión anterior con `session_search` para contexto previo

---

## Resolución parcial — Sesión 2026-05-07 tarde

**Descubrimiento:** cc2 (Maribel) funciona con bypass si:
1. Se spawn SIN `require_user_approval=False` (se deja pending approval manual)
2. Se inyecta el prompt EN UNA SOLA OPERACION (no en partes)
3. Se deja que el agente procese sin interrumpir

**Resultado exitoso:**
- Spawn `claude-code-cc2` con `permission_mode="bypass"`, `require_user_approval=False` → terminal viva ✅
- Prompt de 818 bytes inyectado → procesado correctamente ✅
- Agente completó la tarea en 2m 28s → archivo `PLAN_EXPANDIDO.md` creado (581 líneas, 20KB) ✅

**Nota:** El prompt inyectado fue la tarea completa en un solo bloque, no fragmentado. El bypass no mata al proceso cuando se usa así.

**Hipótesis revisada:** Los intentos anteriores con bypass+muerte pueden deberse a que el prompt se injectó y la terminal estaba en un estado particular (ya pidiendo input), o que había race conditions con el approval manual.

**Solución sugerida por cc2:** Usar `--file` para pasar prompts largos en lugar de inject PTY, y usar `laia-agent` como lanzador CLI que evite los problemas de bypass/bwrap.

---

## Resolución exitosa — Sesión 2026-05-07 tarde (cc2-plan-laia-status)

**Tarea completada:** `laia-status` — implementación completa (365 líneas, 12KB) en `/home/laia-arch/LAIA/.laia-arch/bin/laia-status`

**Factores de éxito:**
1. Spawn con bypass funcionando tras fix del usuario
2. Prompt inyectado de una sola vez (1989 bytes)
3. Agente tardó 5m30s en razonar (high effort) pero completó la implementación
4. Interrupt con `Esc` para sacar al agente de fase de reasoning y pasar a escritura

**Lecciones:**
- Para tareas de implementación con alta reflexión, dejar que cc2 razone todo lo que necesite antes de interrumpir
- El `Esc to interrupt` funciona bien para forzar que pase a acción cuando lleva mucho rato en reasoning
- `bash -n` siempre verificar tras implementación de cc2
