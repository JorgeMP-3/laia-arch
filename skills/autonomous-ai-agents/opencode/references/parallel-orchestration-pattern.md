# Patrón de orquestación paralelo con OpenCode en Command Center

## Resumen

Lanzar 4+ agentes OpenCode en paralelo, cada uno con un módulo distinto, y monitorizar su progreso hasta completarse.

## Patrón verificado (sesión 2026-05-06)

### 1. Preparar el terreno

```python
# 1. Inspectear el codebase real (DB-first)
workspace_list_folder(folder="code/arete-swift-no-funciona-sin-cuenta-apple/Sources", workspace="arete")
workspace_read_workspace_file(path="code/arete-swift-no-funciona-sin-cuenta-apple/SPEC.md", workspace="arete")

# 2. Determinar estado actual de cada módulo
# 3. Asignar un módulo por agente
```

### 2. Spawn masivo en paralelo

```python
# 4 spawns simultáneos
command_center_spawn(agent_type="opencode-worker", cwd="/home/proyecto", prompt="...")
command_center_spawn(agent_type="opencode-worker", cwd="/home/proyecto", prompt="...")
command_center_spawn(agent_type="opencode-worker", cwd="/home/proyecto", prompt="...")
command_center_spawn(agent_type="opencode-worker", cwd="/home/proyecto", prompt="...")
```

Cada `spawn` devuelve un `id` de terminal.

### 3. Inyectar prompts diferenciados INMEDIATAMENTE después del spawn

```python
command_center_inject(terminal_id="cfb500ef", text="TASK_FOR_AGENT_1")
command_center_inject(terminal_id="b1843c81", text="TASK_FOR_AGENT_2")
command_center_inject(terminal_id="0690d498", text="TASK_FOR_AGENT_3")
command_center_inject(terminal_id="3f834dad", text="TASK_FOR_AGENT_4")
```

⚠️ **El `prompt` del spawn NO es suficiente**. Debe haber un `inject` posterior para asignar la tarea real.

### 4. El prompt inlineado es CRÍTICO

```python
# ❌ MAL — causa dialogs de permiso que bloquean
text="""CODEBASE: ~/code/arete-swift
SPEC: ~/LAIA/workspaces/arete/code/arete-swift-no-funciona-sin-cuenta-apple/SPEC.md
READ SPEC.md PRIMERO.
TUS ARCHIVOS: ..."""

# ✅ BIEN — absoluto + contenido inlineado
text="""CODEBASE: /home/laia-arch/LAIA/workspaces/arete/code/arete-swift-no-funciona-sin-cuenta-apple
Implementa Nutrition module para Arete iOS.

READ THIS SPEC:
---
[CONTENIDO COMPLETO DEL SPEC.md INLINEADO]
---

TUS ARCHIVOS: NutritionView.swift, AddFoodView.swift, ...
STACK: SwiftUI, MVVM, Swift Charts
COLORS: Background #000000, Accent #e8185c, Nutrition #22c55e
...
"""
```

**Regla absoluta**: todo el contexto en el prompt inyectado.
El `cwd` del spawn puede ser `/home/laia-arch/LAIA/hermes-agent` (hermes-agent ya aprobado),
pero en el prompt se usa la ruta absoluta real del codebase.
No referencies specs externos como archivos — inlinealos.

### 5. Monitorización

```python
# Snapshot rápido (last 30 líneas de cada terminal)
command_center_read_all(tail_lines=30)

# Esperar a que todos produzcan output (5 min)
command_center_wait_all(
    poll_interval=10,
    timeout_seconds=300,
    terminal_ids=["id1", "id2", "id3", "id4"]
)
```

**`wait_all` timeout NO significa fallo**. Significa que los agentes están procesando sin output nuevo en ese intervalo. Seguir leyendo manualmente.

### 6. Señales de estado

| Output | Significado | Acción |
|--------|-------------|--------|
| `Permission required` + dialog | Agente bloqueado esperando confirmación | Matar y re-lanzar con prompt inlineado |
| `Build · MiniMax-M2.7 · 33%` | Compilando/escribiendo, NO bloqueado | Esperar 1-5 min |
| `ls -la ~/code/arete-swift` | Explorando codebase | Esperar |
| `▣  Build` (sin % ni modelo) | Sesión finalizada | Leer output final |
| `timed_out=true` | No hubo output nuevo en el poll interval | Leer `command_center_read_all` |

### 7. Kill de todas las terminales al terminar

```python
# Para cada terminal viva
command_center_kill(terminal_id="cfb500ef")
command_center_kill(terminal_id="b1843c81")
command_center_kill(terminal_id="0690d498")
command_center_kill(terminal_id="3f834dad")
```

## Factores de éxito

1. **Un módulo por agente** — sin solapamiento de archivos
2. **Prompt completamente inlineado** — sin paths externos que requieran permisos
3. **Workdir = codebase real** — cada agente opera en el proyecto real
4. **COLORS y STACK explícitos** — evita que el agente los invente
5. **Endpoints backend listados** — evita llamadas incorrectas
6. **Tiempo de espera suficiente** — 5-10 min por tarea compleja

## Fallos comunes

- Spawn sin inject posterior → el agente queda esperando en prompt interactivo
- Prompt con rutas a specs externos → dialog de permisos bloquea todo
- Esperar `wait_all` con timeout corto →误会 de que fallaron
- Matar agentes prematuramente cuando muestran progress bar
