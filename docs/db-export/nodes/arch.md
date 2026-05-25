# ARCH — Contexto admin de LAIA

## Metadata

- ID: `44`
- Slug: `arch`
- Kind: `project`
- Status: `active`
- Filename: `arch.md`
- Parent: `index`
- Source kind: `manual`
- Created at: `2026-05-08T08:00:57.878315+00:00`
- Updated at: `2026-05-19T11:34:16.245385+00:00`
- Aliases: `arch`

## Summary

Contexto donde LAIA opera con control total sobre el host nativo. Solo accesible por el admin.

## Body

# LAIA-ARCH — Contexto admin de LAIA

ARCH es el contexto donde LAIA opera con control total sobre el sistema. Vive en el host nativo y solo es accesible por el administrador (Jorge).

## Ubicacion

LAIA-ARCH vive en el host nativo. NO esta en un contenedor. Tiene acceso directo al sistema operativo, a todas las herramientas y a toda la infraestructura.

## Estructura del sistema

```
~/LAIA/
├── .laia-arch/              # Nucleo de Hermes + herramientas de ARCH
│   ├── agent/               # Logica del agente
│   ├── gateway/             # Gateway de comunicacion
│   ├── tools/               # Herramientas
│   ├── plugins/             # Plugins internos
│   └── scripts/             # Scripts internos
├── laia-ui/                 # UI oficial (ARCH + AGORA)
├── services/                # Backends
│   ├── agora-backend/       # Backend de la plataforma AGORA
│   └── laia-agent-runtime/  # Runtime para agentes hijos
├── infra/                   # Infraestructura como codigo
│   ├── laiactl              # CLI de gestion de agentes LXD
│   ├── orchestrator/        # Orquestador Python
│   ├── nginx/               # Configuracion nginx
│   └── lxd/                 # Scripts y perfiles LXD
├── plugins/                 # Plugins del host
│   └── workspace-context/   # Sistema de memoria DB-first
└── workspaces/              # Bases de conocimiento
    └── laia-ecosystem/      # Este workspace
```

## Responsabilidades de LAIA-ARCH

- Gestionar el host y la infraestructura (nginx, cloudflared, systemd)
- Crear, eliminar, actualizar, reiniciar y restaurar agentes (contenedores LXD)
- Gestionar el contenedor `laia-agora` (LAIA AGORA)
- Controlar despliegues, networking, snapshots, limites y seguridad
- Ver el estado global de todos los agentes
- Aprobar cambios sensibles
- Recibir alertas de LAIA AGORA

## Ownership de LAIA

LAIA-ARCH es el **padre del ecosistema**. Desde aqui se gobierna:
- LAIA AGORA (contenedor `laia-agora`)
- Los PA-AGORA (contenedores `laia-{usuario}`)

## LAIA AGORA como extension

LAIA AGORA es el mismo agente LAIA pero ejecutandose en su propio contenedor (`laia-agora`) con menos privilegios. Es una extension de ARCH centrada en coordinar a los usuarios. Los usuarios normales solo ven a LAIA AGORA; nunca ven a LAIA-ARCH.

→ Servidores y Red: `servidores-red.md`
→ Seguridad y aislamiento: `seguridad.md`
→ Workspace UI: `workspace-ui-area.md`
→ Herramientas CLI: `herramientas-cli-area.md`
→ LAIA-ARCH admin: `laia-arch-admin.md`

## Relaciones salientes

- `contains` → `documentacion-existente` (Documentación existente del sistema) [peso=1.00]
- `contains` → `herramientas-cli-area` (Herramientas CLI y Scripts) [peso=1.00]
- `contains` → `laia-arch-admin` (LAIA-ARCH admin — Importante) [peso=1.00]
- `contains` → `seguridad` (Seguridad y aislamiento) [peso=1.00]
- `contains` → `servidores-red` (Servidores y Red) [peso=1.00]
- `contains` → `workspace-ui-area` (Workspace UI) [peso=1.00]

## Relaciones entrantes

- `contains` ← `index` (LAIA — Ecosistema v2.6) [peso=1.00]
- `project_of` ← `index` (LAIA — Ecosistema v2.6) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# ARCH — Contexto admin de LAIA

# LAIA-ARCH — Contexto admin de LAIA

ARCH es el contexto donde LAIA opera con control total sobre el sistema. Vive en el host nativo y solo es accesible por el administrador (Jorge).

## Ubicacion

LAIA-ARCH vive en el host nativo. NO esta en un contenedor. Tiene acceso directo al sistema operativo, a todas las herramientas y a toda la infraestructura.

## Estructura del sistema

```
~/LAIA/
├── .laia-arch/              # Nucleo de Hermes + herramientas de ARCH
│   ├── agent/               # Logica del agente
│   ├── gateway/             # Gateway de comunicacion
│   ├── tools/               # Herramientas
│   ├── plugins/             # Plugins internos
│   └── scripts/             # Scripts internos
├── laia-ui/                 # UI oficial (ARCH + AGORA)
├── services/                # Backends
│   ├── agora-backend/       # Backend de la plataforma AGORA
│   └── laia-agent-runtime/  # Runtime para agentes hijos
├── infra/                   # Infraestructura como codigo
│   ├── laiactl              # CLI de gestion de agentes LXD
│   ├── orchestrator/        # Orquestador Python
│   ├── nginx/               # Configuracion nginx
│   └── lxd/                 # Scripts y perfiles LXD
├── plugins/                 # Plugins del host
│   └── workspace-context/   # Sistema de memoria DB-first
└── workspaces/              # Bases de conocimiento
    └── laia-ecosystem/      # Este workspace
```

## Responsabilidades de LAIA-ARCH

- Gestionar el host y la infraestructura (nginx, cloudflared, systemd)
- Crear, eliminar, actualizar, reiniciar y restaurar agentes (contenedores LXD)
- Gestionar el contenedor `laia-agora` (LAIA AGORA)
- Controlar despliegues, networking, snapshots, limites y seguridad
- Ver el estado global de todos los agentes
- Aprobar cambios sensibles
- Recibir alertas de LAIA AGORA

## Ownership de LAIA

LAIA-ARCH es el **padre del ecosistema**. Desde aqui se gobierna:
- LAIA AGORA (contenedor `laia-agora`)
- Los PA-AGORA (contenedores `laia-{usuario}`)

## LAIA AGORA como extension

LAIA AGORA es el mismo agente LAIA pero ejecutandose en su propio contenedor (`laia-agora`) con menos privilegios. Es una extension de ARCH centrada en coordinar a los usuarios. Los usuarios normales solo ven a LAIA AGORA; nunca ven a LAIA-ARCH.

→ Servidores y Red: `servidores-red.md`
→ Seguridad y aislamiento: `seguridad.md`
→ Workspace UI: `workspace-ui-area.md`
→ Herramientas CLI: `herramientas-cli-area.md`
→ LAIA-ARCH admin: `laia-arch-admin.md`

→ Documentación existente del sistema: `documentacion-existente.md`
→ Herramientas CLI y Scripts: `herramientas-cli-area.md`
→ LAIA-ARCH admin — Importante: `laia-arch-admin.md`
→ Seguridad y aislamiento: `seguridad.md`
→ Servidores y Red: `servidores-red.md`
→ Workspace UI: `workspace-ui-area.md`
