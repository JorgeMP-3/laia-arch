# Arquitectura Monorepo AGORA + ARCH

## Metadata

- ID: `128`
- Slug: `arquitectura-monorepo`
- Kind: `doc`
- Status: `active`
- Filename: `arquitectura-monorepo.md`
- Parent: `workspace-ui-area`
- Source kind: `manual`
- Created at: `2026-05-08T10:01:49.597632+00:00`
- Updated at: `2026-05-19T11:13:52.676780`
- Aliases: `arquitectura-monorepo`

## Summary

Arquitectura compartida para UI de ARCH y AGORA con aislamiento Docker

## Body

# LAIA Workspace UI - Monorepo

Arquitectura compartida para la interfaz de LAIA-ARCH y LAIA-AGORA. AGORA se ejecuta en Docker para aislamiento.

## Estructura

```
monorepo/
├── packages/
│   ├── backend/      ← FastAPI (compartido)
│   ├── shared/       ← Componentes compartidos
│   ├── ui-arch/      ← Frontend ARCH (admin)
│   └── ui-agora/     ← Frontend AGORA (empleados, Docker)
├── config/           ← Configuración
└── scripts/          ← Scripts de desarrollo
```

## Desarrollo

### Instalar dependencias
```bash
npm install
```

### Desarrollo local
```bash
# Todos los servicios
npm run dev

# Solo ARCH
npm run dev:arch

# Solo AGORA
npm run dev:agora

# Solo backend
npm run dev:backend
```

### Build
```bash
# Build completo
npm run build

# Build solo ARCH
npm run build:arch

# Build solo AGORA
npm run build:agora
```

## Herramientas

Las herramientas se habilitan/deshabilitan según el medio. AGORA se ejecuta en Docker, por lo que tiene acceso aislado al sistema.

### Workspace
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| workspace_search | ✅ | ✅ |
| workspace_read | ✅ | ✅ |
| workspace_write | ✅ | ✅ |
| workspace_delete | ✅ | ✅ |
| workspace_list | ✅ | ✅ |
| workspace_edges | ✅ | ✅ |
| workspace_events | ✅ | ✅ |
| workspace_export | ✅ | ✅ |
| workspace_migrate | ✅ | ❌ |
| workspace_scan | ✅ | ✅ |
| workspace_config | ✅ | ✅ |
| workspace_health | ✅ | ✅ |

### Comunicación
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| chat_agent | ✅ | ✅ |

### Productividad
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| task_manager | ✅ | ✅ |

### Marketplace
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| skills_marketplace | ✅ | ✅ |

### Filesystem
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| file_manager | ✅ | ✅ |

### Visualización
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| graph_view | ✅ | ✅ |
| node_editor | ✅ | ✅ |

### Sistema
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| context_engine | ✅ | ✅ |
| command_center | ✅ | ✅ |
| terminal | ✅ | ✅ |

### Infraestructura
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| docker_manager | ✅ | ❌ |
| service_control | ✅ | ❌ |
| system_logs | ✅ | ❌ |

### Admin
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| user_management | ✅ | ❌ |
| system_settings | ✅ | ❌ |

## Permisos

- **ARCH**: Administrador, acceso completo al host
- **AGORA**: Empleado, acceso aislado en Docker

## Aislamiento de AGORA

AGORA se ejecuta en un contenedor Docker con las siguientes restricciones:

- **Aislamiento**: Docker proporciona aislamiento del host
- **Terminal**: Acceso al terminal del contenedor (no del host)
- **Filesystem**: Acceso limitado al volumen del contenedor
- **Red**: Sin acceso a servicios internos del host
- **Permisos**: Solo sudo está bloqueado

## Restricciones de AGORA

- ❌ Sin gestión de usuarios del sistema
- ❌ Sin configuración del sistema host
- ❌ Sin acceso a Docker del host
- ❌ Sin control de servicios del host
- ❌ Sin logs del sistema host
- ❌ Sin migrar workspaces

## Puertos

- Backend: `:8077`
- UI ARCH: `:5173`
- UI AGORA: `:5174`

## Despliegue

### LAIA-ARCH (host)
```
arch.laiajmp.org → nginx → ui-arch (:5173)
api.laiajmp.org → nginx → backend (:8077)
```

### AGORA (Docker)
```
laiajmp.org → nginx → ui-agora (:5174)
api.laiajmp.org → nginx → backend (:8077)
```

### Docker Compose
```yaml
version: '3.8'
services:
  agora-ui:
    build: ./packages/ui-agora
    ports:
      - "5174:5174"
    volumes:
      - agora-data:/app/data
    networks:
      - agora-network

  agora-backend:
    build: ./packages/backend
    ports:
      - "8077:8077"
    volumes:
      - agora-data:/app/data
    networks:
      - agora-network

networks:
  agora-network:
    driver: bridge

volumes:
  agora-data:
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `workspace-ui-area` (Workspace UI) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Arquitectura Monorepo AGORA + ARCH

# LAIA Workspace UI - Monorepo

Arquitectura compartida para la interfaz de LAIA-ARCH y LAIA-AGORA. AGORA se ejecuta en Docker para aislamiento.

## Estructura

```
monorepo/
├── packages/
│   ├── backend/      ← FastAPI (compartido)
│   ├── shared/       ← Componentes compartidos
│   ├── ui-arch/      ← Frontend ARCH (admin)
│   └── ui-agora/     ← Frontend AGORA (empleados, Docker)
├── config/           ← Configuración
└── scripts/          ← Scripts de desarrollo
```

## Desarrollo

### Instalar dependencias
```bash
npm install
```

### Desarrollo local
```bash
# Todos los servicios
npm run dev

# Solo ARCH
npm run dev:arch

# Solo AGORA
npm run dev:agora

# Solo backend
npm run dev:backend
```

### Build
```bash
# Build completo
npm run build

# Build solo ARCH
npm run build:arch

# Build solo AGORA
npm run build:agora
```

## Herramientas

Las herramientas se habilitan/deshabilitan según el medio. AGORA se ejecuta en Docker, por lo que tiene acceso aislado al sistema.

### Workspace
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| workspace_search | ✅ | ✅ |
| workspace_read | ✅ | ✅ |
| workspace_write | ✅ | ✅ |
| workspace_delete | ✅ | ✅ |
| workspace_list | ✅ | ✅ |
| workspace_edges | ✅ | ✅ |
| workspace_events | ✅ | ✅ |
| workspace_export | ✅ | ✅ |
| workspace_migrate | ✅ | ❌ |
| workspace_scan | ✅ | ✅ |
| workspace_config | ✅ | ✅ |
| workspace_health | ✅ | ✅ |

### Comunicación
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| chat_agent | ✅ | ✅ |

### Productividad
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| task_manager | ✅ | ✅ |

### Marketplace
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| skills_marketplace | ✅ | ✅ |

### Filesystem
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| file_manager | ✅ | ✅ |

### Visualización
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| graph_view | ✅ | ✅ |
| node_editor | ✅ | ✅ |

### Sistema
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| context_engine | ✅ | ✅ |
| command_center | ✅ | ✅ |
| terminal | ✅ | ✅ |

### Infraestructura
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| docker_manager | ✅ | ❌ |
| service_control | ✅ | ❌ |
| system_logs | ✅ | ❌ |

### Admin
| Herramienta | ARCH | AGORA (Docker) |
|---|---|---|
| user_management | ✅ | ❌ |
| system_settings | ✅ | ❌ |

## Permisos

- **ARCH**: Administrador, acceso completo al host
- **AGORA**: Empleado, acceso aislado en Docker

## Aislamiento de AGORA

AGORA se ejecuta en un contenedor Docker con las siguientes restricciones:

- **Aislamiento**: Docker proporciona aislamiento del host
- **Terminal**: Acceso al terminal del contenedor (no del host)
- **Filesystem**: Acceso limitado al volumen del contenedor
- **Red**: Sin acceso a servicios internos del host
- **Permisos**: Solo sudo está bloqueado

## Restricciones de AGORA

- ❌ Sin gestión de usuarios del sistema
- ❌ Sin configuración del sistema host
- ❌ Sin acceso a Docker del host
- ❌ Sin control de servicios del host
- ❌ Sin logs del sistema host
- ❌ Sin migrar workspaces

## Puertos

- Backend: `:8077`
- UI ARCH: `:5173`
- UI AGORA: `:5174`

## Despliegue

### LAIA-ARCH (host)
```
arch.laiajmp.org → nginx → ui-arch (:5173)
api.laiajmp.org → nginx → backend (:8077)
```

### AGORA (Docker)
```
laiajmp.org → nginx → ui-agora (:5174)
api.laiajmp.org → nginx → backend (:8077)
```

### Docker Compose
```yaml
version: '3.8'
services:
  agora-ui:
    build: ./packages/ui-agora
    ports:
      - "5174:5174"
    volumes:
      - agora-data:/app/data
    networks:
      - agora-network

  agora-backend:
    build: ./packages/backend
    ports:
      - "8077:8077"
    volumes:
      - agora-data:/app/data
    networks:
      - agora-network

networks:
  agora-network:
    driver: bridge

volumes:
  agora-data:
```


> 📅 Documentado: 2026-05-08
