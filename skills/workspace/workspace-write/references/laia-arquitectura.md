# LAIA — Arquitectura del Proyecto

## Modelo: 3 medios de un mismo ser

```
LAIA (el ser / la IA)
├── ARCH   → control total sobre el sistema host, VPN only, sin dominio público
├── AGORA  → LAIA como coordinador de equipo, Docker, toolset coordinator, 24/7
└── AGENTE → copia de LAIA en Docker por usuario, UI pulida, tools limitadas, nombre personalizable
```

- ARCH, AGORA y AGENTE son **el mismo código base** (Hermes/LAIA), misma imagen Docker.
- AGORA y AGENTE difieren solo en configuración y tools activas.
- ARCH vive en el host nativo; AGORA y AGENTE en contenedores Docker.

## Repos y código

| Componente | Ruta física | Notes |
|---|---|---|
| ARCH (repo) | `/home/laia-arch/LAIA/.laia-arch/` | Repo principal con todas las herramientas |
| AGORA | `/home/laia-arch/LAIA/laia-agora/` | Docs de planificación + frontend (pendiente) |
| Hermes core | en ARCH | Subyace a todos los medios |

## Nomenclatura de workspaces

| Workspace | Qué contiene |
|---|---|
| `laia-ecosystem` | Documentación de todo el ecosistema LAIA (ARCH, AGORA, AGENTE, Hermes) — workspace maestro |
| `laia-arch` | Documentación técnica de Hermes (legacy, se migra a `laia-ecosystem`) |
| `arete`, `doyouwin`, `pixelcore`, `servidor-jmp` | Workspaces de proyectos independientes — NO se tocan |

## Conceptos clave

- **LAIA coordinator** = AGORA (son lo mismo; "LAIA coordinator" es el nombre antiguo)
- **Skill Marketplace** = sistema interno para que AGENTE publique skills → AGORA valida → compartido
- **Protección código** = .py se compila a .pyc y se elimina en imagen AGORA/AGENTE
- **toolset `agora`** = configuración restringida: sin command_center, sin cronjob, sin Docker socket, terminal solo local

## Docs de referencia

- `/home/laia-arch/LAIA/laia-agora/ARQUITECTURA_ECOSISTEMA.md` — visión completa del ecosistema
- `/home/laia-arch/LAIA/laia-agora/PLAN_IMPLEMENTACION.md` — plan de despliegue en 9 fases
- `/home/laia-arch/LAIA/laia-agora/plan.md` — resumen ejecutivo
