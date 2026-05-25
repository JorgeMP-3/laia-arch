# Herramientas bloqueadas en agentes personales

## Metadata

- ID: `52`
- Slug: `herramientas-bloqueadas`
- Kind: `doc`
- Status: `archived`
- Filename: `herramientas-bloqueadas.md`
- Parent: `seguridad`
- Source kind: `manual`
- Created at: `2026-05-08T08:04:28.750215+00:00`
- Updated at: `2026-05-12 08:30:25`
- Aliases: `herramientas-bloqueadas`

## Summary

Lista de herramientas y patrones bloqueados en agentes hijos. Incluye restriccion de plugins del host.

## Body

# Herramientas bloqueadas en agentes personales

## Filosofia
Los agentes personales (hijos de LAIA) operan en un entorno de trabajo seguro. Deben ser utiles pero sin acceso a administracion del sistema ni a recursos del host.

## Restriccion de plugins del host

**Los agentes hijos NO tienen acceso a los plugins del host.**
- No ven `/home/laia-hermes/LAIA/plugins/workspace-context`
- No heredan herramientas de administracion de LAIA ARCH
- Solo pueden usar plugins instalados dentro de su propio contenedor

## Bloqueos por herramienta

### terminal_tool
**Patrones bloqueados:**
- sudo, su -
- systemctl, service
- pm2
- docker, docker compose, docker-compose
- kill, killall, pkill
- reboot, shutdown, halt, poweroff
- chmod 777, chown, chgrp
- crontab -r
- rm -rf /, rm -rf /home/*
- lxc, lxd

### execute_code
**Modulos bloqueados:**
- subprocess, os.system, os.popen
- pty.spawn, pty.openpty
- fcntl.ioctl, fcntl.fcntl
- socket.*, requests

### delegate_task
- Max depth: 1 (no recursion)
- Sin acceso a tools de administracion

### workspace_*
**Tools de escritura bloqueadas:**
- workspace_scan_artifacts
- workspace_migrate_legacy
- workspace_clean_exports
- workspace_verify_db_completeness

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `seguridad` (Seguridad y aislamiento) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Herramientas bloqueadas en agentes personales

# Herramientas bloqueadas en agentes personales

## Filosofia
Los agentes personales (hijos de LAIA) operan en un entorno de trabajo seguro. Deben ser utiles pero sin acceso a administracion del sistema ni a recursos del host.

## Restriccion de plugins del host

**Los agentes hijos NO tienen acceso a los plugins del host.**
- No ven `/home/laia-hermes/LAIA/plugins/workspace-context`
- No heredan herramientas de administracion de LAIA ARCH
- Solo pueden usar plugins instalados dentro de su propio contenedor

## Bloqueos por herramienta

### terminal_tool
**Patrones bloqueados:**
- sudo, su -
- systemctl, service
- pm2
- docker, docker compose, docker-compose
- kill, killall, pkill
- reboot, shutdown, halt, poweroff
- chmod 777, chown, chgrp
- crontab -r
- rm -rf /, rm -rf /home/*
- lxc, lxd

### execute_code
**Modulos bloqueados:**
- subprocess, os.system, os.popen
- pty.spawn, pty.openpty
- fcntl.ioctl, fcntl.fcntl
- socket.*, requests

### delegate_task
- Max depth: 1 (no recursion)
- Sin acceso a tools de administracion

### workspace_*
**Tools de escritura bloqueadas:**
- workspace_scan_artifacts
- workspace_migrate_legacy
- workspace_clean_exports
- workspace_verify_db_completeness
