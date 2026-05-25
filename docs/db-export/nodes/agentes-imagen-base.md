# Imagen base de agentes — Sistema de aprovisionamiento

## Metadata

- ID: `133`
- Slug: `agentes-imagen-base`
- Kind: `doc`
- Status: `active`
- Filename: `agentes-imagen-base.md`
- Parent: `agentes-personales`
- Source kind: `tool`
- Created at: `2026-05-08T16:04:39.550745+00:00`
- Updated at: `2026-05-19T11:13:52.676999`
- Aliases: `agentes-imagen-base`

## Summary

Sistema de imagen base LXD para aprovisionar agentes de empleados rápidamente

## Body

# Imagen base de agentes — Sistema de aprovisionamiento

## Concepto

Todos los empleados arrancan desde una **imagen base LXD compartida**: Ubuntu 22.04 + Hermes Agent + toolset-AGORA pre-instalados. Crear un nuevo agente es un comando, no una instalación.

```
┌──────────────────────────────────┐
│ laia-agent:latest (imagen base)  │
│                                  │
│  - Ubuntu 22.04                   │
│  - Python 3.11                   │
│  - Hermes Agent                   │
│  - Toolset-AGORA configurado      │
│  - /opt/data/ vacío               │
│  - Sin acceso a código host        │
└──────────────────────────────────┘
           │
    lxc launch laia-agent:latest
           │
    ┌──────┴──────┬──────────┐
    ▼             ▼          ▼
 laia-jorge   laia-maria  laia-carlos
 (10.0.0.50)  (10.0.0.51)  (10.0.0.52)
```

## Crear la imagen base

### Paso 1 — Contenedor temporal

```bash
lxc launch ubuntu:22.04 laia-agent-base
```

### Paso 2 — Instalar runtime

```bash
lxc exec laia-agent-base -- apt update
lxc exec laia-agent-base -- apt install -y python3 python3-venv git curl
```

### Paso 3 — Instalar Hermes Agent

```bash
# Clonar el repositorio (solo el runtime, NO el código completo de LAIA)
lxc exec laia-agent-base -- git clone https://github.com/NousResearch/hermes-agent.git /opt/hermes

# Instalar en modo desarrollo (accesible para el agente)
lxc exec laia-agent-base -- bash -c "cd /opt/hermes && python3 -m venv venv && ./venv/bin/pip install -e ."

# Instalar herramientas base
lxc exec laia-agent-base -- /opt/hermes/venv/bin/pip install requests pyyaml
```

### Paso 4 — Configurar toolset-AGORA

```bash
# Script de configuración que aplica restricciones
cat << 'EOF' > /tmp/setup-agora.sh
#!/bin/bash
# Configurar toolset de empleado (restricciones)

mkdir -p /opt/data
mkdir -p /opt/hermes/config

cat > /opt/hermes/config/toolset-agora.yaml << 'YAML'
# Herramientas permitidas para empleados
allowed_tools:
  - terminal (solo comandos locales, sin sudo)
  - execute_code (Python, sin subprocess)
  - workspace_read (solo lectura)
  - web_search
  - web_extract
  - vision_analyze
  - text_to_speech
  - send_message
  - todo
  - delegate_task

# Herramientas BLOQUEADAS
blocked_tools:
  - workspace_write
  - workspace_upsert_node
  - execute_code (con subprocess/shell)
  - terminal (con sudo/apt系统性)
  - search_files
  - session_search

# Límites de red
network:
  outbound: true
  inbound: false
  internal_containers: false
YAML

echo "Toolset AGORA configurado"
EOF

lxc file push /tmp/setup-agora.sh laia-agent-base/tmp/
lxc exec laia-agent-base -- bash /tmp/setup-agora.sh
```

### Paso 5 — Publicar imagen

```bash
# Publicar como imagen con alias
lxc publish laia-agent-base --alias laia-agent:latest

# Versionado: crear también una versión con fecha
lxc publish laia-agent-base --alias laia-agent:2026-05

# Limpiar contenedor temporal
lxc delete laia-agent-base

# Ver imágenes disponibles
lxc image list
```

## Crear empleado nuevo

```bash
# Aprovisionar nuevo empleado
lxc launch laia-agent:latest laia-jorge

# Asignar IP estática
lxc config device add laia-jorge eth0 nic \
  name=eth0 \
  network=lxd-bridge \
  ipv4.address=10.0.0.50/24

# Configurar recursos
lxc config set laia-jorge limits.memory 8GB
lxc config set laia-jorge limits.cpu 4

# Habilitar nesting (si el empleado necesita Docker dentro)
lxc config set laia-jorge security.nesting true

# Ver que está corriendo
lxc list
lxc exec laia-jorge -- free -h
```

## Actualizar versión de LAIA para todos

### Flujo de actualización

```bash
# 1. Crear contenedor desde la imagen actual
lxc launch laia-agent:latest laia-update-v2

# 2. Instalar nueva versión de Hermes
lxc exec laia-update-v2 -- bash -c "cd /opt/hermes && git pull"
lxc exec laia-update-v2 -- /opt/hermes/venv/bin/pip install -e .

# 3. Publicar nueva imagen
lxc publish laia-update-v2 --alias laia-agent:v2
lxc delete laia-update-v2

# 4. Probar con un empleado (rollback fácil)
lxc stop laia-jorge
lxc launch laia-agent:v2 laia-jorge-test
lxc exec laia-jorge-test -- /opt/hermes/venv/bin/hermes --version

# 5. Si todo bien, recrear todos los empleados
for empleado in jorge maria carlos; do
  lxc stop laia-$empleado
  lxc launch laia-agent:v2 laia-$empleado
done

# 6. Rollback: usar imagen anterior si hay problema
lxc stop laia-jorge
lxc launch laia-agent:v1 laia-jorge
```

### Actualización automática (futuro)

Para actualizar todos los contenedores de forma incremental sin parar el servicio:

```bash
# Imagen azul-verde: crear nueva imagen, probar, conmutar
# Esto es lo que haría AGORA Coordinator cuando ARCH lo decida
```

## Snapshot antes de cambios arriesgados

```bash
# Antes de que empleado instale algo nuevo
lxc snapshot laia-jorge pre-experimento-nginx

# Si rompe algo:
lxc restore laia-jorge pre-experimento-nginx

# Ver todos los snapshots
lxc info laia-jorge --all-snapshots
```

## Notas importantes

- **El código base de LAIA solo está en el host.** El contenedor solo tiene el runtime de Hermes (copiado en /opt/hermes), no el código completo de ARCH/AGORA.
- **Imagen ligera de crear.** No se incluye código de usuario, solo el entorno de ejecución del agente.
- **Consistencia 100%.** Todos los empleados corren exactamente la misma versión del agente.
- **Rollback instantáneo.** Si una actualización falla, volver a la imagen anterior y recrear el contenedor.

## Estado

- **Estado:** CONCEPTUAL — pendiente de validar en servidor Dell 9020
- **Imagen base:** pendiente de crear y probar
- **Script de aprovisionamiento:** pendiente de desarrollar

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agentes-personales` (Agentes personales — Hijos de LAIA (v2.1)) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Imagen base de agentes — Sistema de aprovisionamiento

# Imagen base de agentes — Sistema de aprovisionamiento

## Concepto

Todos los empleados arrancan desde una **imagen base LXD compartida**: Ubuntu 22.04 + Hermes Agent + toolset-AGORA pre-instalados. Crear un nuevo agente es un comando, no una instalación.

```
┌──────────────────────────────────┐
│ laia-agent:latest (imagen base)  │
│                                  │
│  - Ubuntu 22.04                   │
│  - Python 3.11                   │
│  - Hermes Agent                   │
│  - Toolset-AGORA configurado      │
│  - /opt/data/ vacío               │
│  - Sin acceso a código host        │
└──────────────────────────────────┘
           │
    lxc launch laia-agent:latest
           │
    ┌──────┴──────┬──────────┐
    ▼             ▼          ▼
 laia-jorge   laia-maria  laia-carlos
 (10.0.0.50)  (10.0.0.51)  (10.0.0.52)
```

## Crear la imagen base

### Paso 1 — Contenedor temporal

```bash
lxc launch ubuntu:22.04 laia-agent-base
```

### Paso 2 — Instalar runtime

```bash
lxc exec laia-agent-base -- apt update
lxc exec laia-agent-base -- apt install -y python3 python3-venv git curl
```

### Paso 3 — Instalar Hermes Agent

```bash
# Clonar el repositorio (solo el runtime, NO el código completo de LAIA)
lxc exec laia-agent-base -- git clone https://github.com/NousResearch/hermes-agent.git /opt/hermes

# Instalar en modo desarrollo (accesible para el agente)
lxc exec laia-agent-base -- bash -c "cd /opt/hermes && python3 -m venv venv && ./venv/bin/pip install -e ."

# Instalar herramientas base
lxc exec laia-agent-base -- /opt/hermes/venv/bin/pip install requests pyyaml
```

### Paso 4 — Configurar toolset-AGORA

```bash
# Script de configuración que aplica restricciones
cat << 'EOF' > /tmp/setup-agora.sh
#!/bin/bash
# Configurar toolset de empleado (restricciones)

mkdir -p /opt/data
mkdir -p /opt/hermes/config

cat > /opt/hermes/config/toolset-agora.yaml << 'YAML'
# Herramientas permitidas para empleados
allowed_tools:
  - terminal (solo comandos locales, sin sudo)
  - execute_code (Python, sin subprocess)
  - workspace_read (solo lectura)
  - web_search
  - web_extract
  - vision_analyze
  - text_to_speech
  - send_message
  - todo
  - delegate_task

# Herramientas BLOQUEADAS
blocked_tools:
  - workspace_write
  - workspace_upsert_node
  - execute_code (con subprocess/shell)
  - terminal (con sudo/apt系统性)
  - search_files
  - session_search

# Límites de red
network:
  outbound: true
  inbound: false
  internal_containers: false
YAML

echo "Toolset AGORA configurado"
EOF

lxc file push /tmp/setup-agora.sh laia-agent-base/tmp/
lxc exec laia-agent-base -- bash /tmp/setup-agora.sh
```

### Paso 5 — Publicar imagen

```bash
# Publicar como imagen con alias
lxc publish laia-agent-base --alias laia-agent:latest

# Versionado: crear también una versión con fecha
lxc publish laia-agent-base --alias laia-agent:2026-05

# Limpiar contenedor temporal
lxc delete laia-agent-base

# Ver imágenes disponibles
lxc image list
```

## Crear empleado nuevo

```bash
# Aprovisionar nuevo empleado
lxc launch laia-agent:latest laia-jorge

# Asignar IP estática
lxc config device add laia-jorge eth0 nic \
  name=eth0 \
  network=lxd-bridge \
  ipv4.address=10.0.0.50/24

# Configurar recursos
lxc config set laia-jorge limits.memory 8GB
lxc config set laia-jorge limits.cpu 4

# Habilitar nesting (si el empleado necesita Docker dentro)
lxc config set laia-jorge security.nesting true

# Ver que está corriendo
lxc list
lxc exec laia-jorge -- free -h
```

## Actualizar versión de LAIA para todos

### Flujo de actualización

```bash
# 1. Crear contenedor desde la imagen actual
lxc launch laia-agent:latest laia-update-v2

# 2. Instalar nueva versión de Hermes
lxc exec laia-update-v2 -- bash -c "cd /opt/hermes && git pull"
lxc exec laia-update-v2 -- /opt/hermes/venv/bin/pip install -e .

# 3. Publicar nueva imagen
lxc publish laia-update-v2 --alias laia-agent:v2
lxc delete laia-update-v2

# 4. Probar con un empleado (rollback fácil)
lxc stop laia-jorge
lxc launch laia-agent:v2 laia-jorge-test
lxc exec laia-jorge-test -- /opt/hermes/venv/bin/hermes --version

# 5. Si todo bien, recrear todos los empleados
for empleado in jorge maria carlos; do
  lxc stop laia-$empleado
  lxc launch laia-agent:v2 laia-$empleado
done

# 6. Rollback: usar imagen anterior si hay problema
lxc stop laia-jorge
lxc launch laia-agent:v1 laia-jorge
```

### Actualización automática (futuro)

Para actualizar todos los contenedores de forma incremental sin parar el servicio:

```bash
# Imagen azul-verde: crear nueva imagen, probar, conmutar
# Esto es lo que haría AGORA Coordinator cuando ARCH lo decida
```

## Snapshot antes de cambios arriesgados

```bash
# Antes de que empleado instale algo nuevo
lxc snapshot laia-jorge pre-experimento-nginx

# Si rompe algo:
lxc restore laia-jorge pre-experimento-nginx

# Ver todos los snapshots
lxc info laia-jorge --all-snapshots
```

## Notas importantes

- **El código base de LAIA solo está en el host.** El contenedor solo tiene el runtime de Hermes (copiado en /opt/hermes), no el código completo de ARCH/AGORA.
- **Imagen ligera de crear.** No se incluye código de usuario, solo el entorno de ejecución del agente.
- **Consistencia 100%.** Todos los empleados corren exactamente la misma versión del agente.
- **Rollback instantáneo.** Si una actualización falla, volver a la imagen anterior y recrear el contenedor.

## Estado

- **Estado:** CONCEPTUAL — pendiente de validar en servidor Dell 9020
- **Imagen base:** pendiente de crear y probar
- **Script de aprovisionamiento:** pendiente de desarrollar

> 📅 Documentado: 2026-05-12
