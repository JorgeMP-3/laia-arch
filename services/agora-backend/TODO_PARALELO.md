# Trabajo paralelizable para otra IA

Estas tareas pueden avanzar en paralelo sin tocar `services/agora-backend/app/main.py` directamente.

## Bloque A — Infra

Ruta sugerida:

```text
infra/
```

Tareas:

- Crear propuesta de `nginx/agora.conf`.
- Crear propuesta de `systemd/agora-backend.service`.
- Definir puertos oficiales.
- Documentar despliegue de `agora-app/dist`.

## Bloque B — LXD

Ruta sugerida:

```text
infra/lxd/
```

Tareas:

- Crear perfil `laia-employee`.
- Crear script `create-agent`.
- Crear script `snapshot-agent`.
- Crear script `restore-agent`.
- Documentar estructura interna del contenedor.

## Bloque C — UI AGORA contra API real

Ruta sugerida:

```text
laia-ui/packages/agora-app
```

Tareas:

- Conectar dashboard a `/api/tasks`.
- Crear vista de tareas.
- Crear vista de agentes.
- Crear panel de coordinator report.

## Bloque D — Seguridad

Ruta sugerida:

```text
docs/security-agora.md
```

Tareas:

- Definir matriz de permisos endpoint por endpoint.
- Definir politica de publicacion personal -> colectivo.
- Definir auditoria minima para eventos.

