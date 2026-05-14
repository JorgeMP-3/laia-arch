# LAIA — Arquitectura oficial del repositorio

Fecha: 2026-05-12

Este documento fija la fuente oficial de cada parte del ecosistema para evitar duplicidad entre prototipos.

## Modelo de producto

LAIA es un ecosistema de agentes con un **agente padre unico** (LAIA) que opera en dos contextos:

- **LAIA ARCH**: contexto admin. Vive en el host nativo. Control total del sistema, infraestructura, LXD, agentes, workspaces y seguridad. Solo accesible por el administrador.
- **LAIA AGORA**: contexto coordinador. Vive en su propio contenedor LXD (`laia-agora`). Monitoriza el trabajo de los usuarios, asigna tareas via la plataforma AGORA y alerta a LAIA ARCH. NO puede modificar contenedores de usuarios. Accesible por todos los usuarios.

Los agentes personales son **hijos de LAIA**, uno por usuario en contenedor LXD (`laia-{usuario}`). Cada usuario elige el nombre de su agente (NO puede llamarse "LAIA") y puede editar sus ficheros de comportamiento, skills, memories y plugins propios.

## Fuentes oficiales

| Area | Ruta oficial | Estado |
|---|---|---|
| UI ARCH | `laia-ui/packages/arch-app` | Oficial |
| UI AGORA | `laia-ui/packages/agora-app` | Oficial |
| UI compartida | `laia-ui/packages/ui` | Oficial |
| API compartida/types | `laia-ui/packages/shared` | Oficial |
| Backend AGORA | `services/agora-backend` | Base inicial creada |
| Agent Runtime | `services/laia-agent-runtime` | Oficial |
| Infra servidor | `infra/` | Orquestador + LXD + nginx |
| Hermes core | `.laia-arch/` | Oficial como core tecnico |
| WorkspaceStore | `workspace_store/` | Oficial |
| Plugin workspace-context | `plugins/workspace-context/` | Oficial (solo visible por LAIA ARCH) |
| Workspaces DB-first | `workspaces/` | Oficial |

## Prototipos y material legacy

| Ruta | Clasificacion | Uso permitido |
|---|---|---|
| `laia-agora/` | Prototipo/legacy | Referencia visual/infra; no desarrollar ahi features nuevas. |
| `workspaces/laia-ecosystem/code/agora/monorepo/` | Prototipo documental | Extraer ideas/config si sirven; no es base productiva. |
| `.laia-arch/workspace-ui/` | Runtime servido de ARCH | Destino de despliegue para `arch-app/dist`; no editar UI fuente ahi. |
| `hermes-agent-upstream-test/` | Upstream/test | Referencia de Hermes; no mezclar con LAIA productivo. |

## Regla de desarrollo

1. Toda UI nueva de ARCH/AGORA se desarrolla en `laia-ui`.
2. Todo backend propio de AGORA se desarrolla en `services/agora-backend`.
3. Toda configuracion de servidor va en `infra/`.
4. Los datos productivos viven fuera del repo, bajo `/srv/laia`.
5. Los agentes personales se implementan con LXD, no con Docker como estrategia principal.
6. Docker puede usarse para servicios de app, pero no debe montar `.hermes`, `~/LAIA` ni Docker socket en AGORA produccion.
7. Los plugins del host (`/home/laia-hermes/LAIA/plugins/`) NO son visibles para los agentes hijos.

## Frontera de responsabilidades

LAIA ARCH (contexto admin, host nativo):

- administra todos los contenedores LXD, incluyendo `laia-agora`;
- ejecuta `laiactl`;
- crea, elimina, actualiza, reinicia y restaura agentes;
- controla despliegues, networking, snapshots, limites y seguridad;
- puede ver el estado global de todos los agentes;
- recibe alertas de LAIA AGORA.

LAIA AGORA (contexto coordinador, contenedor `laia-agora`):

- monitoriza el estado de los agentes personales;
- asigna tareas a traves de la plataforma AGORA;
- gestiona el marketplace de skills;
- envia alertas a LAIA ARCH;
- NO ejecuta comandos en contenedores de usuarios;
- NO modifica ficheros de agentes personales;
- NO gestiona infraestructura.

AGORA (plataforma web):

- expone al usuario su propio agente personal;
- permite editar nombre, perfil, skills, comportamiento, memories y plugins propios;
- permite ver tareas asignadas por LAIA AGORA;
- acceso al marketplace de skills;
- no puede listar agentes ajenos;
- no puede crear ni borrar contenedores;
- no puede ejecutar operaciones globales de infraestructura.

Regla de ownership:

- `usuario jorge` -> contenedor `laia-jorge` -> agente "Nombrix" (nombre elegido por Jorge)
- `usuario maria` -> contenedor `laia-maria` -> agente "MariaBot" (nombre elegido por Maria)
- `coordinador` -> contenedor `laia-agora` -> LAIA AGORA
- AGORA siempre debe validar la relacion usuario-contenedor antes de tocar runtime, perfil o workspace.

## Topologia objetivo en servidor

```text
/home/laia-hermes/LAIA/
├── .laia-arch/
├── laia-ui/
├── services/
│   ├── agora-backend/
│   └── laia-agent-runtime/
├── infra/
│   ├── laiactl
│   ├── orchestrator/
│   ├── nginx/
│   ├── systemd/
│   ├── docker/
│   └── lxd/
├── workspace_store/
├── plugins/
└── workspaces/

LXD containers:
├── laia-agora      (LAIA AGORA — coordinador)
├── laia-jorge      (agente personal de Jorge)
├── laia-maria      (agente personal de Maria)
└── laia-carlos     (agente personal de Carlos)

/srv/laia/
├── agora/
│   ├── app-data/
│   └── uploads/
├── arch/
│   └── state/
├── agents/
│   └── registry.json
└── backups/
```

## Despliegue UI

ARCH:

```bash
cd /home/laia-hermes/LAIA/laia-ui
pnpm build:arch
rm -rf /home/laia-hermes/LAIA/.laia-arch/workspace-ui/frontend/dist
cp -r /home/laia-hermes/LAIA/laia-ui/packages/arch-app/dist /home/laia-hermes/LAIA/.laia-arch/workspace-ui/frontend/dist
```

AGORA:

```bash
cd /home/laia-hermes/LAIA/laia-ui
pnpm build:agora
```

AGORA aun necesita servicio/nginx oficial antes de desplegarse en produccion.

## Siguiente bloque

Completar `services/agora-backend` como backend de la plataforma AGORA:

- auth basica y ownership usuario -> agente;
- healthcheck;
- endpoints para perfil, workspace y tareas del agente propio;
- endpoints del coordinador (LAIA AGORA);
- lectura de estado del agente propio;
- bloqueo explicito de operaciones globales.

Las operaciones globales sobre LXD y el fleet de agentes quedan del lado de LAIA ARCH.
