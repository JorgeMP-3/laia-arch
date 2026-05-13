# AGORA personal agents with LXD

Estado: operativo inicial verificado.

## Modelo

Cada empleado tiene un contenedor LXD propio y un workspace personal propio.

```text
ARCH
└── administra
    ├── laia-jorge  -> /opt/laia/workspaces/personal/workspace.db
    ├── laia-maria  -> /opt/laia/workspaces/personal/workspace.db
    └── laia-carlos -> /opt/laia/workspaces/personal/workspace.db
```

AGORA no administra el fleet. AGORA solo expone al usuario su propio agente personal.

## Por que LXD

LXD permite un Ubuntu completo con systemd, servicios, snapshots y aislamiento de filesystem. Docker se mantiene para servicios de app, no como estrategia principal para agentes personales.

## Perfil base

Perfil:

```text
infra/lxd/profiles/laia-employee.yaml
```

Valores iniciales:

- 2 CPU.
- 4GB RAM.
- unprivileged.
- nesting desactivado por defecto.
- red `lxdbr0`.

Aplicar perfil:

```bash
infra/lxd/scripts/check-host.sh
infra/lxd/scripts/init-defaults.sh   # solo si faltan pool/red
infra/lxd/scripts/apply-profile.sh
infra/lxd/scripts/verify-lxd-setup.sh
```

## Crear agente

Script previsto:

```bash
infra/lxd/scripts/create-agent.sh jorge
```

Debe crear:

```text
container: laia-jorge
workspace: /opt/laia/workspaces/personal/workspace.db
data:      /opt/laia/data
logs:      /opt/laia/logs
```

Estado verificado el 2026-05-11:

- imagen local `laia-agent` publicada;
- contenedor `laia-jorge` creado y en ejecucion;
- `laia-jorge/initial` creado como snapshot inicial;
- `laia-jorge/runtime-ready` creado tras instalar runtime completo;
- `laia-jorge/runtime-installed` creado tras instalar el runtime real;
- `laia-jorge/workspace-initialized` creado tras inicializar WorkspaceStore personal;
- `/opt/laia/healthcheck.sh` devuelve `laia-agent-runtime-ok`.
- `python3-pip`, `python3-venv`, `jq`, `git` y `curl` verificados.
- contenedor temporal `laia-smoke` creado desde `laia-agent`, verificado y eliminado.
- servicio `laia-agent.service` activo y habilitado dentro de `laia-jorge`;
- runtime instalado en `/opt/laia/agent`;
- estado vivo en `/opt/laia/data/status.json`;
- logs en `/opt/laia/logs/agent.log`;
- cola local de tareas en `/opt/laia/data/tasks`.
- workspace personal real en `/opt/laia/workspaces/personal/workspace.db`;
- `workspace_store` vendorizado en `/opt/laia/agent/vendor/workspace_store`;
- tareas de workspace verificadas: crear nodo, listar nodos, leer nodo y buscar.
- perfil editable real en `/opt/laia/data/profile`;
- tareas de perfil verificadas: leer perfil, actualizar preferencias y activar/desactivar skills.

La salida a Internet de `lxdbr0` requiere reglas NAT/FORWARD en el host. Si se pierde tras reinicio o cambio de firewall:

```bash
sudo infra/lxd/scripts/fix-egress-root.sh
```

Verificado:

- `ping 1.1.1.1` desde `laia-jorge`;
- HTTP 200 contra `ports.ubuntu.com`;
- `apt-get update` dentro de `laia-jorge`.

## Snapshots

Antes de cambios importantes:

```bash
infra/lxd/scripts/snapshot-agent.sh jorge pre-cambio
```

Restaurar:

```bash
infra/lxd/scripts/restore-agent.sh jorge pre-cambio
```

Tambien se puede usar `laiactl`:

```bash
infra/laiactl snapshot-agent jorge pre-cambio
infra/laiactl restore-agent jorge pre-cambio --yes
```

## Runtime

Codigo fuente:

```text
services/laia-agent-runtime
```

Instalar o actualizar dentro de un contenedor:

```bash
infra/laiactl install-agent-runtime jorge
```

Gestionar servicio:

```bash
infra/laiactl agent-status jorge
infra/laiactl restart-agent jorge
infra/laiactl stop-agent jorge
infra/laiactl start-agent jorge
```

Tareas locales soportadas inicialmente:

- `ping`;
- `write_file`;
- `read_file`.
- `workspace_init`;
- `workspace_upsert_node`;
- `workspace_get_node`;
- `workspace_list_nodes`;
- `workspace_search`.
- `profile_init`;
- `profile_get`;
- `profile_update`;
- `skill_enable`;
- `skill_disable`.

## Perfil del agente

Ruta dentro del contenedor:

```text
/opt/laia/data/profile
├── persona.md
├── instructions.md
├── skills.json
└── preferences.json
```

Comandos de `laiactl`:

```bash
infra/laiactl init-agent-profile jorge
infra/laiactl agent-profile jorge
infra/laiactl set-agent-persona jorge /ruta/persona.md
infra/laiactl set-agent-instructions jorge /ruta/instructions.md
infra/laiactl enable-agent-skill jorge planning.deep
infra/laiactl disable-agent-skill jorge tasks.basic
```

El runtime protege las escrituras concurrentes del perfil con un lock de archivo en:

```text
/opt/laia/data/profile/.profile.lock
```

## Workspace personal

Inicializar:

```bash
infra/laiactl init-agent-workspace jorge
```

Ruta dentro del contenedor:

```text
/opt/laia/workspaces/personal/workspace.db
```

El runtime usa el mismo paquete `workspace_store` del host, copiado dentro del contenedor en:

```text
/opt/laia/agent/vendor/workspace_store
```

Esto mantiene el schema compatible con LAIA y evita que cada agente tenga una DB inventada distinta.

## Seguridad

Por defecto:

- sin `security.nesting`;
- sin rutas del host montadas;
- sin Docker socket;
- sin acceso a workspaces de otros empleados;
- sin acceso a ARCH.

Activar nesting solo por excepcion:

```bash
lxc config set laia-jorge security.nesting true
```

## Integracion con ARCH y AGORA

ARCH mantiene el registro global:

```text
/srv/laia/agents/registry.json
```

ARCH usa `laiactl` y/o los modulos del orquestador para:

- crear agentes;
- instalar runtime;
- hacer snapshot/restore;
- parar/arrancar servicios;
- verificar salud.

AGORA no toca ese registro global directamente. AGORA solo consume una vista filtrada por ownership:

- el usuario `jorge` solo puede operar sobre `laia-jorge`;
- el usuario `maria` solo puede operar sobre `laia-maria`.

Endpoints esperados en AGORA:

```text
GET /api/agent
GET /api/agent/profile
PATCH /api/agent/profile
GET /api/workspace/nodes
POST /api/tasks
```

Los endpoints de AGORA deben validar ownership antes de leer o escribir perfil, runtime o workspace.
