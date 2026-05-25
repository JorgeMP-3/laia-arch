# Base de agentes personales

## Metadata

- ID: `67`
- Slug: `agentes-base`
- Kind: `doc`
- Status: `active`
- Filename: `agentes-base.md`
- Parent: `agentes-personales`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:53.624320+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `agentes-base`

## Summary

Configuracion base de agentes hijos de LAIA en LXD: runtime, workspace, perfil editable.

## Body

# Base de PA-AGORA

## Contenedor LXD
- Imagen base: Ubuntu 22.04 (`laia-agent`)
- Runtime: `services/laia-agent-runtime` instalado en `/opt/laia/agent`
- Python 3.11+ con venv en `/opt/laia/runtime/venv`
- Usuario sin privilegios: `laia-agent`
- Servicio systemd: `laia-agent.service`

## Estructura dentro del contenedor

```
/opt/laia/
├── agent/                    # Codigo del runtime (solo lectura)
│   ├── src/
│   └── vendor/workspace_store/
├── runtime/venv/             # Virtual environment
├── data/
│   ├── profile/              # Ficheros editables por el usuario
│   │   ├── persona.md
│   │   ├── instructions.md
│   │   ├── skills.json
│   │   └── preferences.json
│   ├── tasks/                # Cola de tareas
│   │   ├── inbox/
│   │   ├── done/
│   │   └── failed/
│   └── status.json
├── workspaces/personal/
│   └── workspace.db          # Workspace personal aislado
└── logs/
    └── agent.log
```

## Personalizacion

Cada usuario puede editar (via AGORA):
- **Nombre visible** del agente (NO "LAIA")
- **persona.md**: personalidad, tono, estilo
- **instructions.md**: instrucciones de comportamiento
- **skills.json**: skills activas/desactivadas
- **preferences.json**: avatar, idioma, configuracion

## Plugins

- Plugins propios: SI, instalables dentro del contenedor
- Plugins del host (`/home/laia-hermes/LAIA/plugins/`): NO visibles
- `workspace-context`: NO heredado

## Creacion de un agente

```bash
# Desde LAIA-ARCH:
infra/laiactl create-agent jorge
infra/laiactl install-agent-runtime jorge
infra/laiactl init-agent-workspace jorge
infra/laiactl init-agent-profile jorge
infra/laiactl verify-agent jorge

# Snapshot inicial
infra/laiactl snapshot-agent jorge initial
```

## Restricciones

- Sin acceso al host
- Sin Docker socket
- Sin `~/.laia-arch/`
- Sin plugins del host
- Sin acceso a otros contenedores
- Tools limitadas (ver `herramientas-bloqueadas.md`)

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agentes-personales` (Agentes personales — Hijos de LAIA (v2.1)) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Base de agentes personales

# Base de PA-AGORA

## Contenedor LXD
- Imagen base: Ubuntu 22.04 (`laia-agent`)
- Runtime: `services/laia-agent-runtime` instalado en `/opt/laia/agent`
- Python 3.11+ con venv en `/opt/laia/runtime/venv`
- Usuario sin privilegios: `laia-agent`
- Servicio systemd: `laia-agent.service`

## Estructura dentro del contenedor

```
/opt/laia/
├── agent/                    # Codigo del runtime (solo lectura)
│   ├── src/
│   └── vendor/workspace_store/
├── runtime/venv/             # Virtual environment
├── data/
│   ├── profile/              # Ficheros editables por el usuario
│   │   ├── persona.md
│   │   ├── instructions.md
│   │   ├── skills.json
│   │   └── preferences.json
│   ├── tasks/                # Cola de tareas
│   │   ├── inbox/
│   │   ├── done/
│   │   └── failed/
│   └── status.json
├── workspaces/personal/
│   └── workspace.db          # Workspace personal aislado
└── logs/
    └── agent.log
```

## Personalizacion

Cada usuario puede editar (via AGORA):
- **Nombre visible** del agente (NO "LAIA")
- **persona.md**: personalidad, tono, estilo
- **instructions.md**: instrucciones de comportamiento
- **skills.json**: skills activas/desactivadas
- **preferences.json**: avatar, idioma, configuracion

## Plugins

- Plugins propios: SI, instalables dentro del contenedor
- Plugins del host (`/home/laia-hermes/LAIA/plugins/`): NO visibles
- `workspace-context`: NO heredado

## Creacion de un agente

```bash
# Desde LAIA-ARCH:
infra/laiactl create-agent jorge
infra/laiactl install-agent-runtime jorge
infra/laiactl init-agent-workspace jorge
infra/laiactl init-agent-profile jorge
infra/laiactl verify-agent jorge

# Snapshot inicial
infra/laiactl snapshot-agent jorge initial
```

## Restricciones

- Sin acceso al host
- Sin Docker socket
- Sin `~/.laia-arch/`
- Sin plugins del host
- Sin acceso a otros contenedores
- Tools limitadas (ver `herramientas-bloqueadas.md`)

> 📅 Documentado: 2026-05-12
