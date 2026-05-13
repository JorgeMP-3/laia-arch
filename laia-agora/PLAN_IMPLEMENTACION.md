# LAIA-AGORA — Plan de Implementación

## Objetivo

Desplegar un ecosistema donde:
- **laia-arch** (admin/Jorge): control total del host, acceso solo por VPN
- **laia-agora** (10 empleados): contenedor Docker aislado por usuario, acceso vía laiajmp.org

Servidor: Intel Xeon + 32GB RAM. Todo en `~/LAIA/laia-agora/`.

---

## Arquitectura final

```
[Servidor]
│
├── laia-arch (host nativo, VPN only)          RAM: ~8-10GB
│   └── Todas las herramientas, Docker socket, acceso total
│
├── LAIA coordinador (contenedor)              RAM: ~2GB
│   └── toolset: coordinator, opera 24/7
│
└── Docker (red bridge interna)
    ├── agora-emp1   :9200   /opt/agora/emp1   RAM: ~1.5GB
    ├── agora-emp2   :9201   /opt/agora/emp2   RAM: ~1.5GB
    ├── ...
    └── agora-emp10  :9209   /opt/agora/emp10  RAM: ~1.5GB

Cloudflare Tunnel → nginx (laiajmp.org)
    → login + AGORA React app
    → /api/{user}/ → proxy al contenedor del usuario
```

Total estimado: ~28GB RAM dentro de los 32GB disponibles.

---

## Fases

### FASE 0 — Migrar app actual de laiajmp.org

**Prerequisito antes de todo lo demás.**

La app actual en laiajmp.org necesita moverse a un subdominio (ej. `apps.laiajmp.org` o similar) para liberar el dominio raíz para AGORA.

---

### FASE 1 — Definir el toolset `agora`

**Archivo:** `~/.laia-arch/toolsets.py`

Añadir entrada `agora` al diccionario `TOOLSETS` existente.

**Permitidas:**
- `web_tools` (web_search, web_extract)
- `file_operations` — solo dentro de `/opt/data/`
- `code_execution_tool` — sandbox Python dentro del contenedor
- `browser_tool`
- `vision_tools`
- `memory_tool`, `session_search_tool`
- `workspace` tools (su propio workspace)
- `terminal` — solo backend `local` dentro del contenedor
- `delegate_tool` — con `max_spawn_depth=1`

**Bloqueadas:**
- `command_center_tool`
- `cronjob_tools`
- `mcp_tool` con servidores de host
- Terminal backends: `ssh`, `docker`, `singularity`, `modal`, `daytona`
- Cualquier tool que use Docker socket

**Config base de cada contenedor** (`laia-agora/config/agora.yaml`):
```yaml
toolsets:
  enabled: [web, file, code, browser, vision, memory, workspace, terminal]
  terminal_backends: [local]
  disabled_tools: [command_center, cronjob, mcp_host]
```

> ⚠️ Verificar si `toolsets.py` ya soporta restringir backends de terminal por toolset, o si hay que añadirlo.

---

### FASE 2 — Dockerfile para laia-agora

**Archivo:** `~/LAIA/laia-agora/Dockerfile`

```dockerfile
FROM laia-arch:latest AS agora

ENV HERMES_TOOLSET=agora
ENV HERMES_USER_MODE=restricted

# Compilar fuentes a .pyc y eliminar .py (protección del código base)
RUN find /opt/hermes -name "*.py" -exec python -m py_compile {} \; && \
    find /opt/hermes -name "*.py" -delete

USER hermes   # UID 10001, no root, sin gosu

ENTRYPOINT ["tini", "--", "python", "-m", "hermes_cli"]
```

Diferencias clave respecto al Dockerfile de laia-arch:
- Usuario fijo no-root (sin remapping dinámico)
- Sin Docker socket montado
- `HERMES_TOOLSET=agora` por defecto
- Código fuente Python compilado y eliminado

---

### FASE 3 — docker-compose.agora.yml

**Archivo:** `~/LAIA/laia-agora/docker-compose.agora.yml`

```yaml
services:
  agora-emp1:
    image: laia-agora:latest
    container_name: agora-emp1
    network_mode: bridge
    ports:
      - "127.0.0.1:9200:9000"
    volumes:
      - /opt/agora/emp1:/opt/data
    environment:
      - AGORA_USER=emp1
      - WORKSPACE=agora_e1
      - HERMES_TOOLSET=agora
    restart: unless-stopped

  # emp2 → :9201, emp3 → :9202 ... emp10 → :9209
  # mismo patrón, puerto +1 por empleado

  laia-coordinator:
    image: laia-agora:latest
    container_name: laia-coordinator
    network_mode: bridge
    ports:
      - "127.0.0.1:9210:9000"
    volumes:
      - /opt/agora/coordinator:/opt/data
    environment:
      - AGORA_USER=coordinator
      - HERMES_TOOLSET=coordinator
    restart: unless-stopped
```

---

### FASE 4 — Script de gestión

**Archivo:** `~/LAIA/laia-agora/agora-manager.sh`

```bash
#!/bin/bash
# Uso: ./agora-manager.sh [add|remove|list|status] [nombre]

add()    → mkdir /opt/agora/$USER, asignar puerto, añadir al compose, docker compose up -d
remove() → docker compose stop/rm (datos en /opt/agora/$USER conservados)
list()   → docker compose ps
status() → docker stats agora-* --no-stream
```

---

### FASE 5 — nginx routing

**Añadir a** `/etc/nginx/sites-available/laiajmp.org`:

```nginx
# Mapa usuario → puerto interno
map $agora_user $agora_port {
    emp1  9200;
    emp2  9201;
    # ...
    emp10 9209;
}

# Auth + proxy al contenedor del usuario
location /api/ {
    auth_basic "LAIA Agora";
    auth_basic_user_file /etc/nginx/agora_htpasswd;

    # Extraer usuario del header o cookie de sesión
    # proxy_pass al puerto correspondiente
    proxy_pass http://127.0.0.1:$agora_port/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

# Servir AGORA React app para todas las demás rutas
location / {
    root /opt/agora/frontend/dist;
    try_files $uri $uri/ /index.html;
}
```

---

### FASE 6 — Frontend AGORA

**Directorio:** `~/LAIA/laia-agora/frontend/`

- Proyecto React + Vite nuevo (no fork de workspace-ui)
- Mismas áreas funcionales que workspace-ui actual
- Diseño más limpio, orientado a usuarios no técnicos
- Responsive (funciona en móvil desde el navegador)
- Pantalla de login (usuario + contraseña) como punto de entrada
- Tras login: conecta a `/api/` que nginx enruta al contenedor del usuario

**Tauri (cliente de escritorio):**
- Mismo proyecto React empaquetado con Tauri
- Siempre conecta al servidor remoto (laiajmp.org)
- `src-tauri/` dentro del mismo directorio frontend

---

## Orden de ejecución

| Paso | Acción | Tiempo estimado |
|------|--------|----------------|
| 0 | Migrar app actual de laiajmp.org | 30 min |
| 1 | Verificar/añadir toolset `agora` en toolsets.py | 30 min |
| 2 | Construir Dockerfile agora y testear | 45 min |
| 3 | Crear docker-compose.agora.yml con los 10 servicios | 20 min |
| 4 | Crear volúmenes y arrancar contenedores | 15 min |
| 5 | Configurar nginx y htpasswd | 20 min |
| 6 | Crear agora-manager.sh | 20 min |
| 7 | Desarrollar frontend AGORA (React + login) | variable |
| 8 | Empaquetar con Tauri | 1-2h |
| 9 | Test con 1 usuario, luego roll-out al resto | 30 min |

---

## Verificación final

1. Contenedor agora: `terminal` solo funciona dentro del contenedor
2. Contenedor agora: acceder a `/home/laia-arch` → denegado
3. Contenedor agora: herramientas de host (`command_center`, `cronjob`) → no disponibles
4. nginx: `https://laiajmp.org` → login → conecta al contenedor correcto
5. nginx: usuario A no puede acceder a los datos de usuario B
6. Reinicio del servidor: todos los contenedores vuelven (`restart: unless-stopped`)
7. App Tauri: instalar, login, verificar que conecta al servidor remoto correctamente

---

## Notas

- Los datos de cada empleado en `/opt/agora/{usuario}` sobreviven reinicios y rebuilds de imagen
- Actualizar LAIA para todos = `docker compose pull && docker compose up -d` (~30 segundos)
- La imagen base se almacena una sola vez; Docker hace el sharing automático de capas
- Añadir empleado nuevo = `./agora-manager.sh add {nombre}`
- laia-arch no está expuesto en ningún dominio público — solo accesible por VPN al host
