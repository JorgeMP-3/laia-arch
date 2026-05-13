# AGORA Backend

Backend oficial de AGORA — plataforma de agentes personales del ecosistema LAIA.

Estado: Produccion-ready (7 fases completadas). 69 tests.

## Responsabilidades

- Auth con JWT (access + refresh tokens) y passwords hasheadas (pbkdf2_hmac)
- Usuarios, roles y ownership usuario -> agente personal
- Perfil editable del agente personal (persona, instrucciones, skills, preferencias)
- Tareas del agente y tareas globales asignadas por LAIA AGORA
- Eventos auditables
- Workspace personal del usuario
- Coordinador LAIA AGORA: report de estado y asignacion de tareas globales

## Limites

Este backend no es el plano de control global.

- No debe listar todos los agentes del sistema para usuarios normales (solo admin)
- No debe crear ni borrar contenedores LXD para no-admin
- No debe exponer operaciones administrativas de `laiactl` a no-admin
- No debe permitir acceso al agente de otro usuario
- No debe exponer plugins del host

El control global de agentes, contenedores, snapshots y runtime pertenece a LAIA ARCH.

## Desarrollo

```bash
cd /home/laia-hermes/LAIA/services/agora-backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload
```

Tests:

```bash
.venv/bin/python -m pytest tests/ -v
```

## Variables de entorno

| Variable | Default | Uso |
|---|---|---|
| `LAIA_ROOT` | `/home/laia-hermes/LAIA` | Raiz del repo |
| `AGORA_ENV` | `dev` | Entorno (`dev` o `prod`) |
| `AGORA_DATA_DIR` | `/srv/laia/agora` | Datos productivos |
| `AGORA_DEV_DATA_DIR` | `./data` | Fallback dev |
| `AGORA_JWT_SECRET` | random | Secreto para firmar JWT (generado al arrancar si no se configura) |
| `AGORA_ACCESS_MINUTES` | `30` | Duracion del access token en minutos |
| `AGORA_REFRESH_DAYS` | `7` | Duracion del refresh token en dias |
| `LAIA_STATE_ROOT` | `/srv/laia/state` | Estado del orquestador LXD |
| `LAIACTL_PATH` | `~/LAIA/infra/laiactl` | Path al CLI de gestion LXD |

## Endpoints

### Auth

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `POST` | `/api/login` | — | Login. Devuelve `access_token` + `refresh_token` + user |
| `POST` | `/api/refresh` | — | Renovar access token con refresh token |
| `GET` | `/api/me` | JWT | Datos del usuario autenticado |
| `POST` | `/api/me/password` | JWT | Cambiar contraseña (pide old + new) |

### Agente personal (usuario autenticado)

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `GET` | `/api/agent/profile` | JWT | Leer perfil completo (persona, instrucciones, skills, preferencias) |
| `PATCH` | `/api/agent/profile` | JWT | Actualizar perfil (campos opcionales) |
| `GET` | `/api/agent/status` | JWT | Estado del runtime dentro del contenedor LXD |
| `GET` | `/api/agent/tasks` | JWT | Cola de tareas del agente (inbox/done/failed) |
| `PATCH` | `/api/agent` | JWT | Cambiar nombre visible del agente |

### Tareas

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `GET` | `/api/tasks` | JWT | Listar tareas. Admin: todas. User: solo las suyas |
| `POST` | `/api/tasks` | JWT | Crear tarea |
| `PATCH` | `/api/tasks/{id}` | JWT | Actualizar tarea (estado, prioridad, asignado) |

### Agentes LXD (admin)

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `GET` | `/api/agents` | JWT | Listar agentes. Admin: todos + estado LXD. User: solo el suyo |
| `GET` | `/api/agents/{slug}` | Admin | Detalle de un agente |
| `POST` | `/api/agents` | Admin | Crear agente (contenedor LXD + runtime + workspace) |
| `POST` | `/api/agents/{slug}/start` | Admin | Arrancar agente |
| `POST` | `/api/agents/{slug}/stop` | Admin | Parar agente |
| `POST` | `/api/agents/{slug}/restart` | Admin | Reiniciar agente |
| `POST` | `/api/agents/{slug}/snapshot` | Admin | Crear snapshot LXD |
| `GET` | `/api/agents/{slug}/logs` | Admin | Ver logs del agente |
| `POST` | `/api/agents/{slug}/tasks` | Admin | Enviar tarea a la cola del agente |
| `GET` | `/api/agents/{slug}/tasks/{id}` | Admin | Leer resultado de tarea |
| `POST` | `/api/agents/{slug}/install-runtime` | Admin | Instalar/actualizar runtime |
| `DELETE` | `/api/agents/{slug}` | Admin | Eliminar agente |

### Coordinador LAIA AGORA (admin)

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `GET` | `/api/coordinator/report` | Admin | Reporte completo: tareas, agentes, alertas |
| `POST` | `/api/coordinator/assign` | Admin | Asignar tarea global (visible para todos) |
| `GET` | `/api/coordinator/health` | — | Estado del coordinador (running, last_check) |
| `POST` | `/api/coordinator/check` | Admin | Forzar chequeo manual de todos los agentes |
| `GET` | `/api/coordinator/alerts` | Admin | Listar alertas activas |

### Usuarios (admin)

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `GET` | `/api/users` | Admin | Listar usuarios activos |
| `GET` | `/api/users/{id}` | Admin | Detalle de usuario + agentes asociados |
| `POST` | `/api/users` | Admin | Crear empleado (opcional: crear agente LXD) |
| `PATCH` | `/api/users/{id}` | Admin | Actualizar display_name o role |
| `DELETE` | `/api/users/{id}` | Admin | Desactivar usuario (soft delete) |
| `POST` | `/api/users/{id}/reset-password` | Admin | Resetear contraseña |

### Observabilidad

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `GET` | `/api/health` | — | Healthcheck completo (DB, LXD, laiactl, coordinador) |
| `GET` | `/api/metrics` | Admin | Metricas: requests, latencias, errores |

### Workspace y eventos

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| `GET` | `/api/workspace/nodes` | JWT | Listar/buscar nodos del workspace colectivo |
| `GET` | `/api/workspace/nodes/{slug}` | JWT | Leer un nodo |
| `POST` | `/api/workspace/nodes` | JWT | Crear/actualizar nodo |
| `GET` | `/api/events` | Admin | Listar eventos (ultimos 100) |
| `POST` | `/api/events` | JWT | Registrar evento |
| `GET` | `/api/health` | — | Healthcheck |
| `GET` | `/` | — | SPA frontend (index.html) |

## Auth

### Sistema de tokens

- **Access token**: JWT HS256, 30 minutos de validez, contiene `sub` (user_id) y `role`
- **Refresh token**: JWT HS256, 7 dias de validez, contiene `sub` y `type: refresh`
- **Secret**: generado aleatoriamente al arrancar. Configurable via `AGORA_JWT_SECRET`
- **Fallback legacy**: si el JWT falla, intenta validar contra el token estatico `user.token` (solo para migracion)

### Password hashing

- Algoritmo: PBKDF2-HMAC-SHA256 con 600,000 iteraciones y salt de 16 bytes
- Formato: `$pbkdf2${salt_hex}${dk_hex}`
- Migracion automatica: al hacer login con contraseña en plano, se hashea y se guarda

### Auto-refresh en el frontend

El frontend detecta 401, intenta refresh con el refresh token, y si funciona reintenta la peticion original. Si falla, cierra sesion.

## Usuario semilla

```text
username: jorge
password: dev-admin
role: agora_admin
```

La contraseña se hashea automaticamente en el primer login.

## Seguridad

- No montar `.hermes`, `~/LAIA` ni Docker socket en produccion
- `AGORA_JWT_SECRET` debe configurarse en produccion (no usar el random de dev)
- Los agentes personales no tienen acceso a plugins del host
