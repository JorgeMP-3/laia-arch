# Workspace UI

## Metadata

- ID: `118`
- Slug: `workspace-ui-area`
- Kind: `topic`
- Status: `active`
- Filename: `workspace-ui-area.md`
- Parent: `arch`
- Source kind: `manual`
- Created at: `2026-05-08T08:49:11.352768+00:00`
- Updated at: `2026-05-08T09:03:49.123306+00:00`
- Aliases: `workspace-ui-area`

## Summary

Interfaz web FastAPI + React para gestión de workspaces

## Body

# Workspace UI

## Descripción

Interfaz web para el sistema de memoria DB-first de Hermes. Permite navegar, editar y visualizar nodos del workspace.

## Stack tecnológico

- **Backend**: Python + FastAPI
- **Frontend**: React 18 + TypeScript + Vite
- **Tema**: Amber/Gold con fondo neural
- **Puerto**: 8077

## Características principales

### Backend (FastAPI)
- 60+ endpoints REST
- WebSocket para updates en tiempo real
- JSON-RPC bridge a hermes-agent
- Gestión de workspaces activos

### Frontend (React)
- Landing page con estadísticas
- Navegador de nodos
- Visualización de grafo
- Editor de nodos
- Panel de chat con agente

## Acceso

- **URL**: http://localhost:8077
- **Desarrollo**: http://localhost:5173 (Vite)

## Documentos incluidos

- **workspace-ui-overview**: Visión general de la UI
- **workspace-ui-backend**: Backend FastAPI (endpoints, WebSocket)
- **workspace-ui-frontend**: Frontend React (componentes, tema)
- **workspace-ui-general**: Documentación general
- **workspace-ui-detail**: Documentación detallada

## Estado actual

- Estado: ACTIVO y funcional
- Código: ~/LAIA/workspace-ui/
- Tema: Amber/Gold con fondo neural


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- `contains` → `arquitectura-monorepo` (Arquitectura Monorepo AGORA + ARCH) [peso=1.00]
- `contains` → `backend-shared` (Backend compartido ARCH + AGORA) [peso=1.00]
- `contains` → `workspace-ui-detail` (Workspace UI (Detailed)) [peso=1.00]
- `contains` → `workspace-ui-backend` (Workspace UI Backend (FastAPI)) [peso=1.00]
- `contains` → `workspace-ui-frontend` (Workspace UI Frontend (React)) [peso=1.00]
- `contains` → `workspace-ui-overview` (Workspace UI Overview) [peso=1.00]
- `contains` → `workspace-ui-general` (Workspace UI — General) [peso=1.00]

## Relaciones entrantes

- `contains` ← `arch` (ARCH — Contexto admin de LAIA) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Workspace UI

# Workspace UI

## Descripción

Interfaz web para el sistema de memoria DB-first de Hermes. Permite navegar, editar y visualizar nodos del workspace.

## Stack tecnológico

- **Backend**: Python + FastAPI
- **Frontend**: React 18 + TypeScript + Vite
- **Tema**: Amber/Gold con fondo neural
- **Puerto**: 8077

## Características principales

### Backend (FastAPI)
- 60+ endpoints REST
- WebSocket para updates en tiempo real
- JSON-RPC bridge a hermes-agent
- Gestión de workspaces activos

### Frontend (React)
- Landing page con estadísticas
- Navegador de nodos
- Visualización de grafo
- Editor de nodos
- Panel de chat con agente

## Acceso

- **URL**: http://localhost:8077
- **Desarrollo**: http://localhost:5173 (Vite)

## Documentos incluidos

- **workspace-ui-overview**: Visión general de la UI
- **workspace-ui-backend**: Backend FastAPI (endpoints, WebSocket)
- **workspace-ui-frontend**: Frontend React (componentes, tema)
- **workspace-ui-general**: Documentación general
- **workspace-ui-detail**: Documentación detallada

## Estado actual

- Estado: ACTIVO y funcional
- Código: ~/LAIA/workspace-ui/
- Tema: Amber/Gold con fondo neural


> 📅 Documentado: 2026-05-08

→ Arquitectura Monorepo AGORA + ARCH: `arquitectura-monorepo.md`
→ Backend compartido ARCH + AGORA: `backend-shared.md`
→ Workspace UI (Detailed): `workspace-ui-detail.md`
→ Workspace UI Backend (FastAPI): `workspace-ui-backend.md`
→ Workspace UI Frontend (React): `workspace-ui-frontend.md`
→ Workspace UI Overview: `workspace-ui-overview.md`
→ Workspace UI — General: `workspace-ui-general.md`
