# Backend compartido ARCH + AGORA

## Metadata

- ID: `129`
- Slug: `backend-shared`
- Kind: `doc`
- Status: `active`
- Filename: `backend-shared.md`
- Parent: `workspace-ui-area`
- Source kind: `manual`
- Created at: `2026-05-08T10:26:00.848645+00:00`
- Updated at: `2026-05-19T11:13:52.676833`
- Aliases: `backend-shared`

## Summary

Backend FastAPI compartido para ARCH y AGORA con endpoints diferenciados

## Body

# Backend compartido para LAIA-ARCH y LAIA-AGORA

## Estructura

```
backend/
├── main.py              # Punto de entrada principal
├── requirements.txt     # Dependencias de Python
├── Dockerfile           # Configuración de Docker
├── config/              # Configuración
│   ├── __init__.py
│   └── settings.py      # Configuración de la aplicación
├── auth/                # Autenticación y autorización
│   ├── __init__.py
│   └── middleware.py     # Middleware de autenticación
├── api/                 # Endpoints de la API
│   ├── __init__.py
│   ├── endpoints/       # Endpoints comunes
│   │   ├── __init__.py
│   │   └── common.py    # Endpoints compartidos
│   ├── arch/            # Endpoints específicos de ARCH
│   │   ├── __init__.py
│   │   └── endpoints.py # Endpoints de administrador
│   └── agora/           # Endpoints específicos de AGORA
│       ├── __init__.py
│       └── endpoints.py # Endpoints de empleado
└── services/            # Servicios de negocio
```

## Endpoints comunes

### Workspaces
- `GET /api/common/workspaces` - Listar workspaces
- `GET /api/common/workspaces/{workspace}/nodes` - Listar nodos
- `GET /api/common/workspaces/{workspace}/nodes/{ref}` - Obtener nodo
- `POST /api/common/workspaces/{workspace}/nodes` - Crear nodo
- `PUT /api/common/workspaces/{workspace}/nodes/{ref}` - Actualizar nodo
- `DELETE /api/common/workspaces/{workspace}/nodes/{ref}` - Eliminar nodo

### Relaciones
- `GET /api/common/workspaces/{workspace}/edges` - Listar relaciones
- `POST /api/common/workspaces/{workspace}/edges` - Crear relación

### Eventos
- `GET /api/common/workspaces/{workspace}/events` - Listar eventos

### Búsqueda
- `POST /api/common/workspaces/{workspace}/search` - Buscar nodos

### Salud
- `GET /api/common/workspaces/{workspace}/health` - Health check

## Endpoints de ARCH

### Infraestructura
- `GET /api/arch/services` - Listar servicios
- `POST /api/arch/services/{service}/restart` - Reiniciar servicio

### Docker
- `GET /api/arch/docker/containers` - Listar contenedores
- `POST /api/arch/docker/containers/{container}/start` - Iniciar contenedor
- `POST /api/arch/docker/containers/{container}/stop` - Detener contenedor

### Logs
- `GET /api/arch/logs` - Obtener logs del sistema

### Usuarios
- `GET /api/arch/users` - Listar usuarios
- `POST /api/arch/users` - Crear usuario

### Configuración
- `GET /api/arch/config` - Obtener configuración
- `PUT /api/arch/config` - Actualizar configuración

### Migración
- `POST /api/arch/workspaces/{workspace}/migrate` - Migrar workspace
- `POST /api/arch/workspaces/{workspace}/export` - Exportar workspace

## Endpoints de AGORA

### Tareas
- `GET /api/agora/tasks` - Listar tareas
- `POST /api/agora/tasks` - Crear tarea
- `PUT /api/agora/tasks/{task_id}` - Actualizar tarea
- `DELETE /api/agora/tasks/{task_id}` - Eliminar tarea

### Chat
- `POST /api/agora/chat` - Chat con agente
- `GET /api/agora/chat/history` - Historial de chat

### Skills
- `GET /api/agora/skills` - Listar skills
- `POST /api/agora/skills/install` - Instalar skill
- `DELETE /api/agora/skills/{skill_name}` - Desinstalar skill

### Archivos
- `GET /api/agora/files` - Listar archivos
- `GET /api/agora/files/{filepath}` - Leer archivo
- `POST /api/agora/files` - Subir archivo
- `DELETE /api/agora/files/{filepath}` - Eliminar archivo

### Perfil
- `GET /api/agora/profile` - Obtener perfil
- `PUT /api/agora/profile` - Actualizar perfil

## Autenticación

El backend utiliza JWT para la autenticación. Los tokens incluyen:
- `medium`: "arch" o "agora"
- `role`: "admin" o "employee"
- `user_id`: ID del usuario

### Crear token
```python
from auth.middleware import create_token, Medium, UserRole

token = create_token(Medium.AGORA, UserRole.EMPLOYEE, "user123")
```

### Decodificar token
```python
from auth.middleware import decode_token

token_data = decode_token(token)
print(token_data.medium)  # Medium.AGORA
print(token_data.role)    # UserRole.EMPLOYEE
```

## Configuración

La configuración se encuentra en `config/settings.py` y se puede sobrescribir con variables de entorno:

- `HERMES_HOME`: Directorio de Hermes (default: ~/.hermes)
- `SECRET_KEY`: Clave secreta para JWT
- `DEBUG`: Modo debug
- `HOST`: Host del servidor
- `PORT`: Puerto del servidor

## Ejecución

### Desarrollo
```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
uvicorn main:app --host 0.0.0.0 --port 8077 --reload
```

### Docker
```bash
# Construir imagen
docker build -t laia-backend .

# Ejecutar contenedor
docker run -p 8077:8077 laia-backend
```

### Docker Compose
```bash
# Iniciar todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `workspace-ui-area` (Workspace UI) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Backend compartido ARCH + AGORA

# Backend compartido para LAIA-ARCH y LAIA-AGORA

## Estructura

```
backend/
├── main.py              # Punto de entrada principal
├── requirements.txt     # Dependencias de Python
├── Dockerfile           # Configuración de Docker
├── config/              # Configuración
│   ├── __init__.py
│   └── settings.py      # Configuración de la aplicación
├── auth/                # Autenticación y autorización
│   ├── __init__.py
│   └── middleware.py     # Middleware de autenticación
├── api/                 # Endpoints de la API
│   ├── __init__.py
│   ├── endpoints/       # Endpoints comunes
│   │   ├── __init__.py
│   │   └── common.py    # Endpoints compartidos
│   ├── arch/            # Endpoints específicos de ARCH
│   │   ├── __init__.py
│   │   └── endpoints.py # Endpoints de administrador
│   └── agora/           # Endpoints específicos de AGORA
│       ├── __init__.py
│       └── endpoints.py # Endpoints de empleado
└── services/            # Servicios de negocio
```

## Endpoints comunes

### Workspaces
- `GET /api/common/workspaces` - Listar workspaces
- `GET /api/common/workspaces/{workspace}/nodes` - Listar nodos
- `GET /api/common/workspaces/{workspace}/nodes/{ref}` - Obtener nodo
- `POST /api/common/workspaces/{workspace}/nodes` - Crear nodo
- `PUT /api/common/workspaces/{workspace}/nodes/{ref}` - Actualizar nodo
- `DELETE /api/common/workspaces/{workspace}/nodes/{ref}` - Eliminar nodo

### Relaciones
- `GET /api/common/workspaces/{workspace}/edges` - Listar relaciones
- `POST /api/common/workspaces/{workspace}/edges` - Crear relación

### Eventos
- `GET /api/common/workspaces/{workspace}/events` - Listar eventos

### Búsqueda
- `POST /api/common/workspaces/{workspace}/search` - Buscar nodos

### Salud
- `GET /api/common/workspaces/{workspace}/health` - Health check

## Endpoints de ARCH

### Infraestructura
- `GET /api/arch/services` - Listar servicios
- `POST /api/arch/services/{service}/restart` - Reiniciar servicio

### Docker
- `GET /api/arch/docker/containers` - Listar contenedores
- `POST /api/arch/docker/containers/{container}/start` - Iniciar contenedor
- `POST /api/arch/docker/containers/{container}/stop` - Detener contenedor

### Logs
- `GET /api/arch/logs` - Obtener logs del sistema

### Usuarios
- `GET /api/arch/users` - Listar usuarios
- `POST /api/arch/users` - Crear usuario

### Configuración
- `GET /api/arch/config` - Obtener configuración
- `PUT /api/arch/config` - Actualizar configuración

### Migración
- `POST /api/arch/workspaces/{workspace}/migrate` - Migrar workspace
- `POST /api/arch/workspaces/{workspace}/export` - Exportar workspace

## Endpoints de AGORA

### Tareas
- `GET /api/agora/tasks` - Listar tareas
- `POST /api/agora/tasks` - Crear tarea
- `PUT /api/agora/tasks/{task_id}` - Actualizar tarea
- `DELETE /api/agora/tasks/{task_id}` - Eliminar tarea

### Chat
- `POST /api/agora/chat` - Chat con agente
- `GET /api/agora/chat/history` - Historial de chat

### Skills
- `GET /api/agora/skills` - Listar skills
- `POST /api/agora/skills/install` - Instalar skill
- `DELETE /api/agora/skills/{skill_name}` - Desinstalar skill

### Archivos
- `GET /api/agora/files` - Listar archivos
- `GET /api/agora/files/{filepath}` - Leer archivo
- `POST /api/agora/files` - Subir archivo
- `DELETE /api/agora/files/{filepath}` - Eliminar archivo

### Perfil
- `GET /api/agora/profile` - Obtener perfil
- `PUT /api/agora/profile` - Actualizar perfil

## Autenticación

El backend utiliza JWT para la autenticación. Los tokens incluyen:
- `medium`: "arch" o "agora"
- `role`: "admin" o "employee"
- `user_id`: ID del usuario

### Crear token
```python
from auth.middleware import create_token, Medium, UserRole

token = create_token(Medium.AGORA, UserRole.EMPLOYEE, "user123")
```

### Decodificar token
```python
from auth.middleware import decode_token

token_data = decode_token(token)
print(token_data.medium)  # Medium.AGORA
print(token_data.role)    # UserRole.EMPLOYEE
```

## Configuración

La configuración se encuentra en `config/settings.py` y se puede sobrescribir con variables de entorno:

- `HERMES_HOME`: Directorio de Hermes (default: ~/.hermes)
- `SECRET_KEY`: Clave secreta para JWT
- `DEBUG`: Modo debug
- `HOST`: Host del servidor
- `PORT`: Puerto del servidor

## Ejecución

### Desarrollo
```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
uvicorn main:app --host 0.0.0.0 --port 8077 --reload
```

### Docker
```bash
# Construir imagen
docker build -t laia-backend .

# Ejecutar contenedor
docker run -p 8077:8077 laia-backend
```

### Docker Compose
```bash
# Iniciar todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down
```


> 📅 Documentado: 2026-05-08
