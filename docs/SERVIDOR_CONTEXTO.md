# Contexto para busqueda de servidor — Proyecto LAIA

## Resumen ejecutivo

LAIA es un ecosistema de agentes IA con un agente padre unico y agentes hijos por usuario. Se despliega sobre Ubuntu con servicios nativos + LXD para aislamiento de agentes + Docker solo para WordPress.

---

## 1. Que se va a ejecutar en el servidor

### A) Servicios nativos (systemd — corren directo en el host)

| Servicio | Puerto | Tecnologia | Proposito |
|---|---|---|---|
| **nginx** | 80 (interno) | nginx 1.24 | Reverse proxy unico. Recibe de cloudflared y enruta por dominio |
| **postgresql** | 5432 | PostgreSQL 16 | BD principal (arete + futuros) |
| **cloudflared** | — | Cloudflare Tunnel | Tunel cifrado al host. Sin puertos abiertos al exterior |
| **hermes** | host network | Python venv | Gateway multi-plataforma de Hermes (Telegram, Discord, WhatsApp, CLI) |
| **workspace-ui** | 8077 | FastAPI + React | UI admin interna de workspaces y contexto |
| **pm2-laia-arch** | 8000 (via PM2) | Node.js (PM2) | Backend de arete (API laiajmp.org, app.laiajmp.org) |
| **agora-backend** | 8088 | FastAPI + uvicorn | Backend de la plataforma AGORA (usuarios, agentes, tareas) |

### B) Docker (solo WordPress)

| Contenedor | Imagen | Puerto host | Proposito |
|---|---|---|---|
| tienda_wordpress | wordpress:latest | 9000 | Tienda online (tienda.laiajmp.org) |
| tienda_db | mysql:8.0 | interno | BD de WordPress |
| tienda_phpmyadmin | phpmyadmin | 9001 | Admin BD (interno) |

Volumenes Docker: `tienda_db_data`, `tienda_wordpress_data`

### C) LXD — System containers (agentes IA aislados)

**LXD es la tecnologia CORE del proyecto.** Cada usuario tiene su propio contenedor Ubuntu.

| Contenedor | Agente | CPU | RAM | IP | Proposito |
|---|---|---|---|---|---|
| `laia-agora` | LAIA AGORA (coordinador) | 2 | 4 GB | 10.99.0.10 | Monitoriza, asigna tareas, interactua con todos los usuarios |
| `laia-jorge` | "Nombrix" (ejemplo) | 2 | 4 GB | 10.99.0.50 | Agente personal de Jorge |
| `laia-maria` | "MariaBot" (ejemplo) | 2 | 4 GB | 10.99.0.51 | Agente personal de Maria |
| `laia-carlos` | "CarlosAI" (ejemplo) | 2 | 4 GB | 10.99.0.52 | Agente personal de Carlos |
| ... | ... | 2 | 4 GB | ... | Uno por empleado |

**Perfil por agente** (`laia-employee`):
- CPU: 2 cores
- RAM: 4 GB
- Unprivileged container (seguro)
- Nesting desactivado por defecto
- Red bridge `lxdbr0` con subred `10.99.0.0/24`

**Dentro de cada contenedor de agente personal** corre:
- `laia-agent.service` (systemd dentro del container)
- Runtime Python (`/opt/laia/runtime/venv`)
- WorkspaceStore personal (`/opt/laia/workspaces/personal/workspace.db`)
- Perfil editable (`/opt/laia/data/profile/`)
- Cola de tareas (`/opt/laia/data/tasks/`)

**El agente LAIA AGORA** (coordinador) es un caso especial: su contenedor `laia-agora` ejecuta una instancia de LAIA con permisos limitados. Todos los usuarios interactuan con el a traves de la plataforma AGORA.

---

## 2. Que se expone publicamente y como

### A) Tunel Cloudflare (sin puertos abiertos)

TODO el trafico entra via `cloudflared` (tunel cifrado Cloudflare). El servidor NO expone puertos directamente a Internet. Cloudflare maneja DNS, SSL y proteccion DDoS.

### B) Dominios y enrutamiento nginx

| Dominio | Destino | Puerto interno | Tipo |
|---|---|---|---|
| `laiajmp.org` | arete-backend (Node.js) + SPA estatica | 8000 | Publico |
| `app.laiajmp.org` | arete-backend API | 8000 | Publico |
| `tienda.laiajmp.org` | WordPress Docker | 9000 | Publico |
| `arch.laiajmp.org` | ARCH UI (admin) | pendiente | Solo VPN/Cloudflare Access |
| `agora.laiajmp.org` | AGORA frontend (React SPA) | 8090 (nginx) | Publico con login |
| `api.laiajmp.org` | AGORA backend `/api/*` | 8088 | Publico |

### C) Dominios para agentes personales (futuro)

Cada agente personal podria tener su propio subdominio para exponer servicios que el usuario levante dentro de su LXD:
- `jorge.laiajmp.org` → nginx proxy → IP del LXD `laia-jorge` (10.99.0.50)
- `maria.laiajmp.org` → nginx proxy → IP del LXD `laia-maria` (10.99.0.51)

Esto requiere configurar nginx como proxy inverso hacia la red LXD interna (ya documentado en `agentes-lxd.md`).

---

## 3. Flujo completo de una peticion

```
Usuario en Internet
      │
      ▼
Cloudflare (DNS + SSL + WAF)
      │ tunel cifrado
      ▼
cloudflared (host) → localhost:80
      │
      ▼
nginx (reverse proxy)
      │
      ├── laiajmp.org ──────────► arete-backend :8000 (Node/PM2)
      ├── app.laiajmp.org ──────► arete-backend :8000
      ├── tienda.laiajmp.org ───► WordPress Docker :9000
      └── agora.laiajmp.org ────► /srv/laia/agora/frontend/dist (SPA)
              │                     /api/* → agora-backend :8088
              │
              ▼
         AGORA backend (FastAPI)
              │
              ├── Gestiona usuarios, tareas, eventos
              ├── Coordinador (LAIA AGORA) → endpoint /api/coordinator/report
              └── Agentes LXD → via laiactl CLI o lxc exec (solo admin)
```

---

## 4. Stack tecnologico completo

| Capa | Tecnologia | Version |
|---|---|---|
| OS | Ubuntu 24.04 (o Linux Mint) | Noble |
| Reverse proxy | nginx | 1.24 |
| Tunel | cloudflared | 2026.3+ |
| BD relacional | PostgreSQL | 16 |
| BD agentes | SQLite (workspace.db por agente) | — |
| Contenedores sistema | LXD | >= 5.0 |
| Contenedores app | Docker | 29+ (solo WordPress) |
| Backend Node | PM2 + Express | Node 22 |
| Backend Python | FastAPI + uvicorn | Python 3.12+ |
| Frontend | React + Vite + TypeScript | pnpm monorepo |
| Runtime agentes | Python venv + systemd unit | Python 3.11+ |
| IaC/CLI | Python (laiactl) | Python 3.12+ |

---

## 5. Recursos estimados

### Basado en la configuracion actual (Dell 9020: i7, 16 GB RAM, SSD)

| Recurso | Uso estimado | Notas |
|---|---|---|
| **CPU host** | 2-4 cores (OS + nginx + BD + Hermes + arete) | El i7 actual sobra |
| **RAM host** | 4-6 GB (OS + servicios nativos) | PostgreSQL consume ~1-2 GB segun datos |
| **RAM Docker** | 1-2 GB (MySQL + WordPress + phpMyAdmin) | |
| **RAM por agente LXD** | 4 GB max (20-30 MB idle real) | LXD comparte kernel, RAM dinamica |
| **Disco host** | 50-80 GB (OS + servicios + codigo) | |
| **Disco /srv/laia/** | 100+ GB (datos productivos, backups, workspaces, BD agentes) | Crece con el numero de agentes |
| **Disco por agente LXD** | ~500 MB base + workspaces + datos | Depende del uso del agente |

### Para N agentes personales

| Componente | Formula |
|---|---|
| RAM minima | 8 GB (host) + N × 4 GB (limite) — uso real mucho menor |
| CPU | 4 cores (host) + N × 2 cores (limite LXD) — LXD comparte cores |
| Almacenamiento | 100 GB base + N × 5-10 GB |

---

## 6. Estructura de directorios en el servidor

```
/home/laia-hermes/LAIA/           # Repositorio principal del proyecto
├── .laia-arch/                   # Hermes core + herramientas admin
├── laia-ui/                      # UI monorepo (ARCH + AGORA)
├── services/
│   ├── agora-backend/            # Backend FastAPI de AGORA
│   └── laia-runtime/       # Runtime que se despliega en cada LXD
├── infra/
│   ├── laiactl                   # CLI de gestion de agentes
│   ├── orchestrator/             # Modulo Python del orquestador
│   ├── nginx/                    # Configs nginx
│   ├── systemd/                  # Archivos .service
│   ├── lxd/                      # Scripts y perfiles LXD
│   └── docker/                   # Configs Docker (WordPress)
├── plugins/
│   └── workspace-context/        # Plugin de memoria (solo host)
└── workspaces/                   # Bases de conocimiento

/srv/laia/                        # Datos productivos (fuera del repo)
├── agora/
│   ├── app-data/
│   └── frontend/dist/            # Build de AGORA para nginx
├── arch/
│   └── state/
├── agents/
│   └── registry.json             # Registro de agentes
├── state/
│   └── agents.json               # Estado del orquestador LXD
└── backups/
```

---

## 7. Que hay nuevo (no existente en el servidor actual)

Estas son las piezas NUEVAS que necesita este proyecto respecto al servidor Dell 9020 actual:

| Componente | Estado | Notas |
|---|---|---|
| **LXD** | Instalar y configurar | No esta en el server actual. Requiere `snap install lxd` + init |
| **Contenedor `laia-agora`** | Crear | Coordinador, 2 CPU, 4 GB |
| **Contenedores `laia-{usuario}`** | Crear N unidades | Uno por empleado |
| **agora-backend.service** | Instalar (systemd) | Ya existe el archivo en `infra/systemd/` |
| **agora-backend .venv** | Crear | `pip install -r requirements.txt` |
| **AGORA frontend build** | Build y desplegar | `pnpm build:agora` → copiar a `/srv/laia/agora/frontend/dist` |
| **nginx agora.conf** | Activar | Ya existe el archivo en `infra/nginx/agora.conf` |
| **Dominio `agora.laiajmp.org`** | Configurar en Cloudflare | Nuevo subdominio |
| **Directorio `/srv/laia/`** | Crear estructura | Datos productivos |
| **Firewall NAT LXD** | Configurar | `fix-egress-root.sh` para salida a Internet de LXD |

### Lo que YA existe y se mantiene:
- nginx, postgresql, cloudflared, hermes, workspace-ui, pm2/arete-backend
- WordPress Docker (tienda)
- Dominios: laiajmp.org, app.laiajmp.org, tienda.laiajmp.org

---

## 8. Requisitos para el nuevo servidor

### Minimo viable (1-3 agentes personales)
- CPU: 8 cores
- RAM: 32 GB
- Disco: 256 GB SSD
- OS: Ubuntu 24.04 LTS
- Red: IP publica no necesaria (Cloudflare Tunnel)
- Soporte para LXD (kernel Linux con user namespaces)

### Recomendado (5-10 agentes personales)
- CPU: 12-16 cores
- RAM: 64 GB
- Disco: 512 GB NVMe SSD
- OS: Ubuntu 24.04 LTS
- Backup: disco secundario o NAS

### No necesita
- GPU (no se usa inferencia local, se usan APIs externas)
- IP publica estatica (todo va por Cloudflare Tunnel)
- Puertos abiertos en el router
- Panel de control (se gestiona por CLI y systemd)

---

## 9. Checklist de despliegue (orden)

1. Ubuntu 24.04 instalado, usuario `laia-hermes` creado
2. `snap install lxd` → `lxd init` → crear perfil `laia-employee`, red `lxdbr0`
3. Instalar paquetes: nginx, postgresql, python3-venv, python3-pip, node (nvm), git, curl
4. Instalar cloudflared y configurar tunel
5. Clonar repositorio `~/LAIA/`
6. Configurar nginx (copiar confs de `infra/nginx/`)
7. Instalar systemd units (hermes, workspace-ui, agora-backend)
8. Configurar Docker + WordPress
9. Build imagen LXD base: `infra/laiactl build-agent-image`
10. Crear contenedores: `infra/laiactl create-agent {slug}`
11. Instalar runtime: `infra/laiactl install-agent-runtime {slug}`
12. Inicializar workspace: `infra/laiactl init-agent-workspace {slug}`
13. Inicializar perfil: `infra/laiactl init-agent-profile {slug}`
14. Build frontend AGORA: `cd laia-ui && pnpm build:agora`
15. Desplegar frontend: `./infra/scripts/deploy-agora-frontend.sh`
16. Verificar todo: `infra/laiactl doctor && infra/laiactl verify`
