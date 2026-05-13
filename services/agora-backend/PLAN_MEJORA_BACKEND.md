# Plan de mejora — AGORA Backend

Fecha: 2026-05-12

**Estado: COMPLETADO — 7/7 fases implementadas, 69 tests.**

---

## Fase 1: Auth de produccion ✅ COMPLETADA 2026-05-12
**Prioridad:** CRITICA — sin esto no se puede exponer a Internet

### 1.1 Contraseñas hasheadas con bcrypt
- `app/security.py`: funciones `hash_password()` y `verify_password()`
- Migrar `users.json` existente: hashear passwords existentes al arrancar si detecta `_hashed: false`
- Eliminar comparacion en plano de `auth.py:authenticate()`

### 1.2 Tokens JWT con expiracion
- `app/security.py`: `create_token(user, expiry)`, `verify_token(token)` usando `python-jose` + `PyJWT`
- Config: secret en config.yaml/env, no hardcodeado
- Endpoint `POST /api/login` devuelve `access_token` (30min) + `refresh_token` (7 dias)
- Endpoint `POST /api/refresh` para renovar sin pedir contraseña

### 1.3 Dependencia current_user con JWT
- Refactorizar `auth.py:current_user()` para verificar JWT en lugar de lookup por token plano
- Mantener compatibilidad con tokens legacy hasta migrar

### 1.4 Rate limiting en login
- `slowapi` o middleware simple: 5 intentos/ventana por IP
- Proteger contra fuerza bruta

**Impacto en archivos:** `auth.py`, nuevo `security.py`, `config.py`, `main.py`, `requirements.txt`

---

## Fase 2: Persistencia en SQLite ✅ COMPLETADA 2026-05-12
**Prioridad:** ALTA — elimina corrupcion de datos y permite queries

### 2.1 Nuevo storage: SQLite
- `app/database.py`: conexion SQLite con context manager, migraciones automaticas
- Schema: tablas `users`, `tasks`, `agents`, `events`, `tokens`
- Migrar datos desde JSON → SQLite al arrancar (una sola vez)

### 2.2 Refactor AgoraStore
- `app/storage.py` → `app/store.py`: mismas interfaces pero con SQL
- `user_by_token()`, `user_by_id()`, `tasks()`, `save_tasks()`, etc.
- Queries parametrizadas, sin SQL injection

### 2.3 Backup automatico
- Antes de cada escritura masiva, copiar `workspace.db` a `backups/`
- Comando `POST /api/admin/backup` para backup manual

### 2.4 Migracion de datos existentes
- Script que lee JSON actuales → inserta en SQLite
- Flag `STORAGE_BACKEND=sqlite` para cambiar de backend en runtime

**Impacto en archivos:** nuevo `database.py`, refactor `storage.py` → `store.py`, `config.py`, `main.py`

---

## Fase 3: API completa de usuarios ✅ COMPLETADA 2026-05-12
**Prioridad:** ALTA — necesario para gestionar empleados

### 3.1 CRUD de usuarios
- `GET /api/users` — ya existe, añadir paginacion y filtros
- `GET /api/users/{id}` — ver un usuario con su agente asociado
- `POST /api/users` — crear empleado (admin only). Genera password temporal
- `PATCH /api/users/{id}` — actualizar display_name, role
- `DELETE /api/users/{id}` — desactivar (soft delete), no borrar

### 3.2 Endpoint cambio de contraseña
- `POST /api/me/password` — cambiar su propia contraseña (pide old + new)
- `POST /api/users/{id}/reset-password` — admin resetea contraseña de empleado

### 3.3 Rol `employee` mejorado
- El rol `employee` solo ve sus tareas y su agente
- No puede ver `/api/agents` (fleet), solo `/api/agent/*` (suyo)
- No puede crear usuarios ni tareas globales

### 3.4 Rol `agent` para LAIA AGORA
- Nuevo rol: ni admin ni empleado, es el coordinador
- Puede ver TODAS las tareas y agentes (lectura)
- Puede asignar tareas globales (`POST /api/coordinator/assign`)
- NO puede modificar perfiles, crear usuarios ni gestionar LXD

**Impacto en archivos:** `models.py`, `main.py`, `auth.py`, `store.py`

---

## Fase 4: Coordinador real (LAIA AGORA) ✅ COMPLETADA 2026-05-12
**Prioridad:** MEDIA — esencial para el ecosistema pero no urgente

### 4.1 Motor de monitorizacion
- `app/coordinator.py`: clase `Coordinator` con loop interno
- Cada N segundos: comprobar estado de todos los agentes via `GET /api/agent/status`
- Si agente inactivo X tiempo → generar evento de alerta
- Si tarea bloqueada Y tiempo → notificar

### 4.2 Endpoint de estado del coordinador
- `GET /api/coordinator/health` — heartbeat del coordinador
- `GET /api/coordinator/alerts` — alertas activas
- `PATCH /api/coordinator/alerts/{id}` — ack/dismiss alerta

### 4.3 Cola de tareas priorizada
- Las tareas asignadas por el coordinador tienen prioridad
- Endpoint `GET /api/coordinator/backlog` — vista kanban (todo/in progress/done)
- Reordenar tareas `PATCH /api/coordinator/tasks/{id}/priority`

### 4.4 Notificaciones via WebSocket (depende de Fase 6)
- Cuando el coordinador asigna tarea → push a los usuarios afectados
- Cuando un usuario completa tarea → push al coordinador

**Impacto en archivos:** nuevo `coordinator.py`, `main.py`, `models.py`

---

## Fase 5: Observabilidad ✅ COMPLETADA 2026-05-12
**Prioridad:** MEDIA — imprescindible para debug en produccion

### 5.1 Structured logging
- `app/logging.py`: formateo JSON, niveles, timestamps UTC
- Usar `structlog` o `logging` con JSONFormatter
- Campos: request_id, user_id, endpoint, status, duration_ms

### 5.2 Healthcheck mejorado
- `GET /api/health` ya existe, añadir:
  - Estado del orchestrator (laiactl reachable)
  - Estado de LXD (lxc version responde)
  - Estado de la DB
  - Version del backend

### 5.3 Endpoint de metricas
- `GET /api/metrics`: contadores de requests, errores, latencias
- Sin dependencia externa (prometheus opcional)
- Contadores por endpoint, por status code

### 5.4 Recovery y graceful shutdown
- Capturar SIGTERM/SIGINT: cerrar DB, parar coordinador, loggear
- Healthcheck devuelve 503 durante shutdown

**Impacto en archivos:** nuevo `logging.py`, `main.py`, `config.py`

---

## Fase 6: WebSocket para tiempo real ✅ COMPLETADA 2026-05-12
**Prioridad:** BAJA — mejora UX pero no bloquea funcionalidad

### 6.1 Endpoint WebSocket
- `ws://host/ws` con auth via token en query param
- Al conectar: registrar usuario, empezar a enviar eventos

### 6.2 Eventos push
- `agent_status_change` — cuando un LXD cambia de estado
- `task_assigned` — cuando LAIA AGORA asigna tarea al usuario
- `task_completed` — cuando una tarea cambia a done
- `coordinator_alert` — cuando el coordinador genera alerta

### 6.3 Connection manager
- `app/websocket.py`: clase `ConnectionManager`
- Mantiene mapa user_id → websocket
- Broadcast a roles especificos (admin, coordinador, usuario)

**Impacto en archivos:** nuevo `websocket.py`, `main.py`, `coordinator.py`

---

## Fase 7: Tests y documentacion ✅ COMPLETADA 2026-05-12
**Prioridad:** MEDIA — asegura calidad a largo plazo

### 7.1 Tests de integracion
- `tests/test_integration.py`: tests contra backend real (no mockeado)
- Test completo: crear usuario → login → crear agente → leer perfil → actualizar → verificar
- Test de coordinador: asignar tarea → empleado la ve → empleado la completa → coordinador la ve done

### 7.2 Fixtures reutilizables
- `tests/conftest.py`: fixtures para cliente autenticado, seed data, etc.
- Limpiar data de test automaticamente (temp db en cada test)

### 7.3 OpenAPI/Swagger
- Ya existe en `/docs` (FastAPI automatico). Añadir descripciones, tags, ejemplos
- Exportar `openapi.json` para generar cliente frontend

### 7.4 README del backend
- Como instalar, configurar, ejecutar, testear
- Variables de entorno documentadas
- Diagrama de arquitectura de endpoints

**Impacto en archivos:** `tests/`, `README.md`

---

## Orden de ejecucion

```
Fase 1: Auth (critico) ──────────────────────► 1-2 dias
Fase 2: SQLite (alta) ───────────────────────► 1-2 dias
Fase 3: CRUD usuarios (alta) ────────────────► 1 dia
Fase 4: Coordinador (media) ─────────────────► 2 dias
Fase 5: Observabilidad (media) ──────────────► 1 dia
Fase 6: WebSocket (baja) ───────────────────► 2 dias
Fase 7: Tests + docs (media) ────────────────► 1 dia
```

## Dependencias entre fases

```
F1 ──► F3 ──► F4
 │
 └──► F2 ──► F3 ──► F6
       │
       └──► F5
              │
              └──► F7 (en paralelo con todas)
```

F1 y F2 son independientes. F3 necesita F2. F4 necesita F3. F6 necesita F4. F5 y F7 son independientes.
