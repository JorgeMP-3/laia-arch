# LAIA Ecosystem — Documento Definitivo v1.0

## Metadata

- ID: `224`
- Slug: `laia-ecosystem-doc`
- Kind: `doc`
- Status: `active`
- Filename: `laia-ecosystem-doc.md`
- Parent: `index`
- Source kind: `manual`
- Created at: `2026-05-19T11:30:41.043804+00:00`
- Updated at: `2026-05-21T12:09:07.978355+00:00`
- Aliases: `laia-ecosystem-doc`

## Summary

Documento raiz del proyecto. Define la vision, arquitectura, 14 reglas, roles (Empleado, LAIA-AGORA, Admin LAIA-ARCH), componentes y roadmap. Nomenclatura: LAIA-ARCH, LAIA-AGORA, PA-AGORA.

## Body

# LAIA Ecosystem — Documento Definitivo

## Nomenclatura

| Interno (devs) | Usuario ve | Descripcion |
|----------------|------------|-------------|
| LAIA-ARCH | (invisible) | Administrador del host. Solo Jorge |
| LAIA-AGORA | "LAIA" | Plataforma multi-usuario. El coordinador |
| PA-AGORA | "Mi agente" / "Nombrix" | PA-AGORA de cada usuario |

## Arquitectura

LAIA-AGORA (cerebro en laia-agora) → HTTP → PA-AGORA (executors en agent-{slug})
LAIA-ARCH en host, invisible a usuarios, 380+ herramientas, ve todo.

## 14 reglas duras

Propiedad (①-④) | Separacion (⑤-⑧) | Naming usuario (⑨-⑪) | Coordinador (⑫-⑭)

## Numeros reales (auditados 2026-05-19)

- 119 endpoints REST
- 351 backend tests + 53 executor + 25 forwarder = 420+ total
- 20 tablas en agora.db
- 380+ herramientas en .laia-core
- 22 endpoints en laia-executor (no herramientas — endpoints de ejecucion)

## Archivo

`/home/laia-hermes/LAIA/LAIA_ECOSYSTEM.md` (365 lineas)

> 📅 2026-05-19

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `index` (LAIA — Ecosistema v2.6) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA Ecosystem — Documento Definitivo v1.0

# LAIA Ecosystem — Documento Definitivo

## Nomenclatura

| Interno (devs) | Usuario ve | Descripcion |
|----------------|------------|-------------|
| LAIA-ARCH | (invisible) | Administrador del host. Solo Jorge |
| LAIA-AGORA | "LAIA" | Plataforma multi-usuario. El coordinador |
| PA-AGORA | "Mi agente" / "Nombrix" | PA-AGORA de cada usuario |

## Arquitectura

LAIA-AGORA (cerebro en laia-agora) → HTTP → PA-AGORA (executors en agent-{slug})
LAIA-ARCH en host, invisible a usuarios, 380+ herramientas, ve todo.

## 14 reglas duras

Propiedad (①-④) | Separacion (⑤-⑧) | Naming usuario (⑨-⑪) | Coordinador (⑫-⑭)

## Numeros reales (auditados 2026-05-19)

- 119 endpoints REST
- 351 backend tests + 53 executor + 25 forwarder = 420+ total
- 20 tablas en agora.db
- 380+ herramientas en .laia-core
- 22 endpoints en laia-executor (no herramientas — endpoints de ejecucion)

## Archivo

`/home/laia-hermes/LAIA/LAIA_ECOSYSTEM.md` (365 lineas)

> 📅 2026-05-19
