# Scripts Index

Índice global de los scripts de Hermes. Se regenera automáticamente desde los
scripts globales de `$HERMES_HOME/scripts/` y `workspaces/{ws}/code/scripts/`.

## global

| Script | Descripción |
|--------|-------------|
| `scripts/_doc_context_engine.py` | Upsert full documentation for Context Engine nodes in laia_arch workspace. |
| `scripts/agent-documenter.py` | Sincroniza la documentacion agentica DB-first de los workspaces Hermes. |
| `scripts/agent-monitor.py` | Monitor legible de orquestacion agentica DB-first para Hermes. |
| `scripts/ai-orchestrator.py` | Orquestador multi-IA DB-first para Hermes. |
| `scripts/check-hardcoded-paths.py` | Detect hardcoded local paths that should come from environment variables. |
| `scripts/cleanup-sessions.py` | Archiva y elimina sesiones antiguas de Hermes. Soporta `sessions/` actual y `logs/sessions/` legacy. |
| `scripts/create-workspace.py` | Crea, repara y migra workspaces DB-only en Hermes. |
| `scripts/datasette-start.sh` | Lanza Datasette con todos los workspaces de Hermes en http://localhost:8076 |
| `scripts/delete-workspace.py` | Elimina un workspace de Hermes con confirmacion manual fuerte y backup previo. |
| `scripts/git-manager-web.py` | git-manager-web.py — Web UI para gestión de git/GitHub en workspaces LAIA. |
| `scripts/git-manager.py` | -*- coding: utf-8 -*- |
| `scripts/health-check.py` | Verifica el estado estructural y DB-only de los workspaces de Hermes. |
| `scripts/hermes-backup.py` | Crea backups rotativos de ~/.hermes en un SSD externo. |
| `scripts/index-scripts.py` | Regenera scripts/INDEX.md desde scripts globales y workspaces/{ws}/code/scripts/. |
| `scripts/init-workspace-git.sh` | Inicializa repos git en las carpetas code/ de todos los workspaces de LAIA. |
| `scripts/nightly-shutdown.py` | LAIA Nightly Shutdown |
| `scripts/show-injected.py` | Muestra qué nodos DB-only se inyectan al agente en cada sesión. |
| `scripts/start_mlx_servers.sh` | Script para que Hermes inicie los servidores MLX (visión + TTS) |
| `scripts/startup-report.py` | LAIA Startup Report |
| `scripts/sync-workspace-markdown.py` | Exporta `workspace.db` a Markdown bajo demanda: `context/` y `docs/db-export/`. |
| `scripts/sync-workspaces-github.sh` | Sube todos los proyectos git de workspaces de LAIA a sus propias repos de GitHub. |
| `scripts/workspace-daily-diagnostic.py` | Diagnóstico rápido del flujo DB-first esperado para preguntas reales. |
| `scripts/workspace-switch.py` | workspace-switch.py — activa, desactiva y consulta el workspace activo. |

## arete

| Script | Descripción |
|--------|-------------|
| `workspaces/arete/code/scripts/backend/src/assistant.ts` | assistant.ts |
| `workspaces/arete/code/scripts/backend/src/config.ts` | config.ts |
| `workspaces/arete/code/scripts/backend/src/db.ts` | db.ts |
| `workspaces/arete/code/scripts/backend/src/modes/index.ts` | index.ts |
| `workspaces/arete/code/scripts/backend/src/server.ts` | server.ts |
| `workspaces/arete/code/scripts/frontend/src/api/client.ts` | client.ts |
| `workspaces/arete/code/scripts/frontend/src/store/index.ts` | index.ts |
| `workspaces/arete/code/scripts/frontend/src/vite-env.d.ts` | vite-env.d.ts |
| `workspaces/arete/code/scripts/set-tunnel-token.sh` | Uso: ./set-tunnel-token.sh <NUEVO_TOKEN> |

## demo-completo

| Script | Descripción |
|--------|-------------|
| _(vacío — añadir scripts en code/scripts/)_ | |

## doyouwin

| Script | Descripción |
|--------|-------------|
| _(vacío — añadir scripts en code/scripts/)_ | |

## laia_arch

| Script | Descripción |
|--------|-------------|
| _(vacío — añadir scripts en code/scripts/)_ | |

## pixelcore

| Script | Descripción |
|--------|-------------|
| `workspaces/pixelcore/code/scripts/applecore-v5/script.js` | script.js |

## servidor_jmp

| Script | Descripción |
|--------|-------------|
| `workspaces/servidor_jmp/code/scripts/proyecto-wordpress/deploy.sh` | deploy.sh — Despliega la tienda WordPress en el Mac mini |
| `workspaces/servidor_jmp/code/scripts/server-scripts/combined.sh` | Combined Dashboard — runs sysinfo + dockerinfo + netinfo |
| `workspaces/servidor_jmp/code/scripts/server-scripts/docker_monitor.py` | Real-time Docker Monitor - Cyberpunk Edition v2.0 |
| `workspaces/servidor_jmp/code/scripts/server-scripts/dockerinfo.sh` | DOCKER INFO - Cyberpunk Dashboard |
| `workspaces/servidor_jmp/code/scripts/server-scripts/monitor.py` | Combined Real-time Monitor - ALL IN ONE |
| `workspaces/servidor_jmp/code/scripts/server-scripts/net_monitor.py` | Real-time Network Monitor - Cyberpunk Edition v2.0 |
| `workspaces/servidor_jmp/code/scripts/server-scripts/netinfo.sh` | NETINFO.SH — Cyberpunk Network Dashboard for macOS / Mac mini |
| `workspaces/servidor_jmp/code/scripts/server-scripts/sysinfo.sh` | ██████╗ ███████╗███████╗██╗   ██╗███████╗                    ║ |
| `workspaces/servidor_jmp/code/scripts/server-scripts/sysinfo_monitor.py` | ╔══════════════════════════════════════════════════════════════════════════════╗ |
| `workspaces/servidor_jmp/code/scripts/set-tunnel-token.sh` | Uso: ./set-tunnel-token.sh <NUEVO_TOKEN> |

---
*Regenerado con `python3 $HERMES_HOME/scripts/index-scripts.py`.*
