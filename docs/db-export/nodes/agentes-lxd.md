# Agentes personales — LXD (v2.2)

## Metadata

- ID: `130`
- Slug: `agentes-lxd`
- Kind: `doc`
- Status: `active`
- Filename: `agentes-lxd.md`
- Parent: `agentes-personales`
- Source kind: `manual`
- Created at: `2026-05-08T15:45:22.111035+00:00`
- Updated at: `2026-05-19T11:13:52.676863`
- Aliases: `agentes-lxd`

## Summary

Contenedores LXD agent-<slug>: perfil laia-employee, imagen laia-agent (executor), bind mounts persistentes, red lxdbr0, auth Bearer token. Legacy laia-* compatible.

## Body

# PA-AGORA LXD v2.2

## Naming: agent-<slug> (Mayo 2026)

Nuevos containers usan `agent-<slug>`. Legacy `laia-<slug>` mantenido para laia-agora y laia-jorge.

## Contenedores: agent-{slug}, imagen laia-agent (Ubuntu 22.04 + executor), perfil laia-employee (CPU 2, RAM 512MB, unprivileged), red lxdbr0, puerto 9091.

## Bind mounts: /srv/laia/users/{slug}/home -> /home/user | /srv/laia/users/{slug}/plugins -> /opt/laia/plugins | /srv/laia/users/{slug}/workspace -> /var/lib/laia/workspace

## Creacion: sudo LAIA_ROOT=~/LAIA bash create-agent.sh jorge-dev (genera api_token, container agent-jorge-dev, bind mounts, executor-token 0600)

## Seguridad: container unprivileged, root dentro, sin acceso a otros containers, Bearer token por peticion

> 📅 Actualizado: 2026-05-18

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agentes-personales` (Agentes personales — Hijos de LAIA (v2.1)) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Agentes personales — LXD (v2.2)

# PA-AGORA LXD v2.2

## Naming: agent-<slug> (Mayo 2026)

Nuevos containers usan `agent-<slug>`. Legacy `laia-<slug>` mantenido para laia-agora y laia-jorge.

## Contenedores: agent-{slug}, imagen laia-agent (Ubuntu 22.04 + executor), perfil laia-employee (CPU 2, RAM 512MB, unprivileged), red lxdbr0, puerto 9091.

## Bind mounts: /srv/laia/users/{slug}/home -> /home/user | /srv/laia/users/{slug}/plugins -> /opt/laia/plugins | /srv/laia/users/{slug}/workspace -> /var/lib/laia/workspace

## Creacion: sudo LAIA_ROOT=~/LAIA bash create-agent.sh jorge-dev (genera api_token, container agent-jorge-dev, bind mounts, executor-token 0600)

## Seguridad: container unprivileged, root dentro, sin acceso a otros containers, Bearer token por peticion

> 📅 Actualizado: 2026-05-18
