---
name: command-center
description: >
  Usa esta skill cuando necesites lanzar agentes externos (Claude Code, Codex, OpenCode, bash)
  en terminales PTY visibles en la UI del Command Center, o inyectarles prompts desde Hermes.
version: "1.0.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [command-center, terminals, pty, multi-agent, spawn, inject]
    category: devops
---

# Command Center — Terminales PTY multi-agente

## Qué es

El Command Center es una página de la UI (`/command-center`) donde se pueden ver múltiples
agentes trabajando en paralelo, cada uno en su propia terminal PTY interactiva.

El panel izquierdo es Hermes (fijo). El panel derecho muestra terminales PTY de agentes externos.

## Hermes tools (preferido — úsalos directamente)

Hermes tiene 4 herramientas nativas para el Command Center:

| Tool | Acción |
|---|---|
| `command_center_list` | Ver todas las terminales (id, tipo, estado) |
| `command_center_spawn` | Lanzar un nuevo agente PTY |
| `command_center_inject` | Enviar texto/prompt a una terminal activa |
| `command_center_kill` | Matar una terminal |

### Flujo básico:
1. `command_center_spawn` con `agent_type` y `cwd` → obtienes el `id`
2. `command_center_inject` con el `id` y el `text` del prompt
3. `command_center_list` para ver estado
4. `command_center_kill` cuando el worker termine

---

## API REST disponible (base: http://localhost:8077/api)

### Listar terminales activas
```
GET /api/terminals
→ [{id, agent_type, command, cwd, cols, rows, pid, exit_code, alive, created_at}]
```

### Lanzar un nuevo agente en terminal PTY
```
POST /api/terminals
Body: {
  agent_type: "bash" | "claude-code-planner" | "codex-worker" | "opencode-worker",
  cwd?: "/ruta/al/proyecto",   // opcional, default ~
  prompt?: "texto inicial",    // opcional, se inyecta 0.8s después del spawn
  cols?: 220,
  rows?: 50
}
→ {id, agent_type, alive: true, pid, ...}
```

Comandos interactivos que se lanzan por agent_type:
- `bash` → `bash -l`
- `claude-code-planner` → `claude`  (Claude Code interactivo)
- `codex-worker` → `codex`          (Codex interactivo)
- `opencode-worker` → `opencode`    (OpenCode interactivo)

### Inyectar texto en una terminal activa
```
POST /api/terminals/{id}/inject
Body: {
  text: "el prompt o comando a enviar",
  press_enter: true   // si false, solo escribe sin enviar
}
→ {ok: true, id, injected: N}
```

Usa este endpoint para que Hermes envíe prompts a agentes sin necesitar WebSocket.

### Matar una terminal
```
DELETE /api/terminals/{id}
→ {ok: true, id}
```

## Flujo recomendado para Hermes

### 1. Lanzar un worker y asignarle tarea

```bash
# Via terminal (para prueba):
curl -s -X POST http://localhost:8077/api/terminals \
  -H 'Content-Type: application/json' \
  -d '{"agent_type":"opencode-worker","cwd":"/home/familiamp/.hermes","prompt":"Revisa el archivo scripts/agent-monitor.py sin modificar nada y dime qué hace"}' \
  | python3 -m json.tool
```

Guarda el `id` que devuelva. El agente arranca y recibe el prompt automáticamente.

### 2. Inyectar seguimiento o nuevo prompt

```bash
curl -s -X POST http://localhost:8077/api/terminals/<ID>/inject \
  -H 'Content-Type: application/json' \
  -d '{"text":"Ahora dime qué funciones tienen más de 50 líneas","press_enter":true}'
```

### 3. Ver todas las terminales activas

```bash
curl -s http://localhost:8077/api/terminals | python3 -m json.tool
```

### 4. Lanzar múltiples workers en paralelo

Para lanzar 5 sesiones de OpenCode revisando áreas diferentes del codebase,
ejecuta 5 llamadas POST consecutivas con distintos `cwd` y `prompt`:

```bash
AREAS=(
  "Revisa ~/.hermes/hermes-agent/run_agent.py sin modificar nada"
  "Revisa ~/.hermes/hermes-agent/cli.py sin modificar nada"
  "Revisa ~/.hermes/hermes-agent/tools/ sin modificar nada"
  "Revisa ~/.hermes/hermes-agent/tui_gateway/ sin modificar nada"
  "Revisa ~/.hermes/workspace_store/__init__.py sin modificar nada"
)
for PROMPT in "${AREAS[@]}"; do
  curl -s -X POST http://localhost:8077/api/terminals \
    -H 'Content-Type: application/json' \
    -d "{\"agent_type\":\"opencode-worker\",\"prompt\":\"$PROMPT\"}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['id'], d['agent_type'])"
done
```

## Reglas

- Siempre usa `cwd` apuntando al proyecto real, no a `~/.hermes` para agentes de código.
- El `prompt` inicial se inyecta con 0.8s de delay — es para dar tiempo al agente a inicializarse.
- Para prompts de seguimiento usa el endpoint `/inject` en lugar del spawn.
- Cierra las terminales con DELETE cuando el agente haya terminado para liberar recursos.
- El Command Center es solo para workers externos (Claude Code, Codex, OpenCode).
  El chat de Hermes en el panel izquierdo sigue siendo el canal principal de Hermes.

## Notas técnicas

- El WebSocket `/api/terminals/{id}/ws` transmite output crudo del PTY en base64.
- La UI se conecta automáticamente cuando aparece un panel nuevo.
- Los terminales sobreviven recargas de página (el proceso sigue corriendo en el backend).
- Si el backend se reinicia, todos los terminales se matan (lifespan cleanup).
