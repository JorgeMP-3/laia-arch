# LXD agents

Infraestructura para agentes personales de AGORA.

Cada empleado tendra un contenedor LXD propio:

```text
laia-jorge
laia-maria
laia-carlos
```

Dentro de cada contenedor:

```text
/opt/laia/
├── workspaces/personal/workspace.db
├── data/
├── runtime/
└── logs/
```

## Partes

```text
profiles/laia-employee.yaml
scripts/create-agent.sh
scripts/snapshot-agent.sh
scripts/restore-agent.sh
image-build/README.md
```

## Scripts

Comprobar host:

```bash
infra/lxd/scripts/check-host.sh
```

Aplicar perfil:

```bash
infra/lxd/scripts/apply-profile.sh
```

Inicializar defaults si faltan `default` o `lxdbr0`:

```bash
infra/lxd/scripts/init-defaults.sh
```

Verificar setup:

```bash
infra/lxd/scripts/verify-lxd-setup.sh
```

Crear agente:

```bash
infra/lxd/scripts/create-agent.sh jorge
```

Snapshot:

```bash
infra/lxd/scripts/snapshot-agent.sh jorge pre-update
```

Restore:

```bash
infra/lxd/scripts/restore-agent.sh jorge pre-update
```

## Regla

Los agentes personales son LXD unprivileged. No deben tener acceso a:

- `/home/laia-hermes/LAIA` del host;
- `.hermes`;
- Docker socket del host;
- workspaces de otros empleados.
