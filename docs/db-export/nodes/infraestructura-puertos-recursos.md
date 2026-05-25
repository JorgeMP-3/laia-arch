# Infraestructura, puertos y recursos

## Metadata

- ID: `49`
- Slug: `infraestructura-puertos-recursos`
- Kind: `doc`
- Status: `active`
- Filename: `infraestructura-puertos-recursos.md`
- Parent: `servidores-red`
- Source kind: `manual`
- Created at: `2026-05-08T08:04:28.049852+00:00`
- Updated at: `2026-05-08T08:04:28.049852+00:00`
- Aliases: `infraestructura-puertos-recursos`

## Summary

Mapa de puertos y recursos del sistema

## Body

# Infraestructura, puertos y recursos

## Puertos en uso

| Servicio | Puerto | Protocolo | Descripción |
|---|---|---|---|
| Workspace UI | 8077 | HTTP | Interfaz web |
| TUI Gateway | - | Unix socket | Terminal UI |
| nginx | 80/443 | HTTP/HTTPS | Proxy inverso |
| PostgreSQL | 5432 | TCP | Base de datos AGORA |
| Redis | 6379 | TCP | Cache AGORA |

## Recursos del sistema

| Recurso | Total | Uso actual | Disponible |
|---|---|---|---|
| CPU | 8 cores | ~20% | ~80% |
| RAM | 16GB | ~6GB | ~10GB |
| Disco | 500GB | ~100GB | ~400GB |

## Monitoreo
- Logs en ~/LAIA/logs/
- Métricas con health-check.py
- Alertas por Telegram


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `servidores-red` (Servidores y Red) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Infraestructura, puertos y recursos

# Infraestructura, puertos y recursos

## Puertos en uso

| Servicio | Puerto | Protocolo | Descripción |
|---|---|---|---|
| Workspace UI | 8077 | HTTP | Interfaz web |
| TUI Gateway | - | Unix socket | Terminal UI |
| nginx | 80/443 | HTTP/HTTPS | Proxy inverso |
| PostgreSQL | 5432 | TCP | Base de datos AGORA |
| Redis | 6379 | TCP | Cache AGORA |

## Recursos del sistema

| Recurso | Total | Uso actual | Disponible |
|---|---|---|---|
| CPU | 8 cores | ~20% | ~80% |
| RAM | 16GB | ~6GB | ~10GB |
| Disco | 500GB | ~100GB | ~400GB |

## Monitoreo
- Logs en ~/LAIA/logs/
- Métricas con health-check.py
- Alertas por Telegram


> 📅 Documentado: 2026-05-08
