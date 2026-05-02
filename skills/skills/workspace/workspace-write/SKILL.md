---
name: workspace-write
description: >
  Escritura, estructura, mantenimiento y refactor de workspaces Hermes DB-first.
  Define la taxonomia canonica, como esta creada la base de datos, cuando usar
  cada kind, como hacer cambios normales y como reorganizar muchos nodos con
  backup y validacion.
version: "7.0.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [workspace, write, db-first, nodes, edges, refactor, migration]
    category: workspace
---

# Workspace — Escritura, Estructura Y Refactor

## Regla Principal

La fuente de verdad es `workspace.db`. Los exports Markdown son derivados.

Esta es la unica skill de escritura para workspaces Hermes. Tambien es la fuente
para reorganizaciones grandes, migraciones, reparaciones y cambios de taxonomia.

Antes de escribir:

```text
workspace_get_node("index")
workspace_search_nodes("area o proyecto relevante")
workspace_search_nodes("riesgos errores decisiones", kind="important")
```

## Codigos De Verificacion

Toda herramienta que modifique `workspace.db` exige `verification_code`.

Los codigos existen para obligar al agente a leer la seccion correcta antes de
escribir. No son seguridad criptografica; son un guardrail de procedimiento. Si
una tool rechaza la llamada por `verification_code invalido o ausente`, vuelve a
leer esta skill y usa el codigo del grupo correcto.

## Cuando Usar Esta Skill

Usa escritura normal para:

- crear o actualizar pocos nodos;
- enlazar nodos;
- crear un proyecto;
- anadir docs, references, scripts o important.

Usa modo refactor/migracion para:

- organizar un workspace completo;
- mover muchos nodos;
- corregir kinds, slugs, padres o edges;
- limpiar legacy `detail` o `agent-node`;
- fusionar duplicados;
- reparar `parent_id` y `contains`;
- aplicar cambios a varios workspaces.

## Como Esta Creada La DB

SQLite: `~/.hermes/workspaces/{workspace}/workspace.db`.

Tablas principales:

| Tabla | Uso |
|---|---|
| `nodes` | Nodos canonicos: slug, title, kind, summary, body, status, parent_id, source_kind. |
| `aliases` | Alias de busqueda asociados a nodos. |
| `edges` | Relaciones explicitas: `contains`, `references`, `depends_on`, `related_to`. |
| `artifacts` | Archivos reales bajo `code/` vinculados a nodos. |
| `events` | Eventos agenticos y actividad historica. |
| `workspace_meta` | Metadatos del workspace. |
| `node_fts` | Indice FTS5 para busqueda por title, slug, summary, body y aliases. |

Regla de consistencia:

- La jerarquia vive en `nodes.parent_id`.
- La misma jerarquia debe existir como edge `contains`.
- Si cambias padres, sincroniza ambos.

## Taxonomia Canonica

| Kind | Cuando usarlo | Proposito |
|---|---|---|
| `index` | Siempre existe uno por workspace. | Punto de entrada. Explica de que va el workspace y orienta a nodos reales principales. |
| `project` | Area de trabajo propia: producto, app, cliente, modulo grande o iniciativa con varios nodos. | Fusion de mini-index y topic local. Resume el proyecto, enumera hijos y guia como trabajar dentro. |
| `topic` | Solo si existen o se planean varios docs sobre un mismo tema. | Mapa de conocimiento. Debe tener hijos. No es doc largo ni carpeta vacia. |
| `important` | Si ignorarlo puede romper algo, repetir errores o causar malas decisiones. | Riesgos, errores pasados, soluciones, advertencias y decisiones criticas. |
| `doc` | Informacion desarrollada sobre un tema concreto. | Documentacion normal, specs, guias, explicaciones y handoffs no agenticos. |
| `script` | Automatizacion, comando o proceso ejecutable reutilizable. | Como ejecutar, mantener o entender scripts/procesos. |
| `reference` | Fuente externa o material de apoyo. | URLs, APIs, bibliografia, documentos externos. |
| `agent-note` | Comportamiento/equipo estable de agentes. | Solo `agent-behavior` y `agent-team` salvo excepcion muy justificada. |
| `agent-plan` | Plan persistente de agentes. | Requests, tasks, planes y handoffs operativos. Vive bajo `agent-team`. |
| `agent-log` | Historial agentico. | `agent-log` global o logs hijos de un `agent-plan`. |

No uses `detail`, `agent-node` ni kinds plurales como `projects`, `topics`,
`docs`, `references` o `scripts`.

## Estructura Correcta

No crees nodos carpeta. La estructura es plana por nodos reales y `kind`:

```text
index                                  kind=index
├── jrvalle-web                        kind=project
│   ├── jrvalle-web-mapa               kind=topic
│   │   ├── requisitos                 kind=doc
│   │   └── referencias-ui             kind=doc
│   ├── jrvalle-web-riesgos            kind=important
│   ├── deploy-jrvalle                 kind=script
│   └── grupo-sala                     kind=reference
├── arquitectura                       kind=topic
│   ├── api                            kind=doc
│   └── base-datos                     kind=doc
├── errores-globales                   kind=important
├── readme                             kind=doc
├── agent-behavior                     kind=agent-note
├── agent-team                         kind=agent-note
│   └── agent-plan-home                kind=agent-plan
│       └── agent-log-home             kind=agent-log
└── agent-log                          kind=agent-log
```

Reglas:

- `index` es el unico nodo obligatorio.
- Los hijos directos del `index` son nodos reales.
- Un `project` vive bajo `index` y puede tener hijos reales.
- No antepongas `project-` al slug de un proyecto; el kind ya lo dice.
- Un `topic` vive bajo `index` o bajo un `project`.
- Un `topic` debe tener hijos; si no tendra hijos, crea un `doc`.
- Un `topic` no puede contener otro `topic`.
- Si un tema necesita desarrollo largo, crea `doc` hijos del topic.
- `important` global vive bajo `index`; `important` especifico vive bajo su `project`.
- `agent-plan` vive bajo `agent-team`; logs de plan viven bajo su plan.

## Como Decidir El Kind

- Raiz del workspace -> `index`.
- Area de trabajo con entidad propia y varios subnodos -> `project`.
- Mapa/guia de varios docs sobre un tema -> `topic`.
- Explicacion concreta y desarrollada -> `doc`.
- Informacion que evita errores, roturas o malas decisiones -> `important`.
- Fuente externa o enlace -> `reference`.
- Automatizacion/comando/proceso ejecutable -> `script`.
- `agent-behavior` o `agent-team` -> `agent-note`.
- Plan/request/task agentico persistente -> `agent-plan`.
- Historial de ejecucion o seguimiento -> `agent-log`.

## Padres Correctos

| Nuevo nodo | Padre correcto |
|---|---|
| `project` | `index` |
| topic global | `index`, solo si tendra docs hijos |
| topic de proyecto | proyecto real, solo si tendra docs hijos |
| doc global | `index` o topic real |
| doc de proyecto | proyecto real o topic real del proyecto |
| important global | `index` |
| important de proyecto | proyecto real |
| script/reference | `index`, proyecto real o topic real |
| `agent-note` | `index` o proyecto relevante, normalmente solo `agent-behavior`/`agent-team` |
| `agent-plan` | `agent-team` |
| `agent-log` global | `index` |
| `agent-log` de plan | `agent-plan` |

Si no sabes el padre, lee el `index` y busca primero. No inventes una carpeta.

## Herramientas De Escritura

### Grupo: Nodos Y Enlaces

Codigo:

```text
verification_code="brujula-cobre-17"
```

Usa este grupo para crear o mantener nodos reales y relaciones directas:

| Tool | Uso |
|---|---|
| `workspace_upsert_node` | Crear o actualizar nodos reales. |
| `workspace_link_nodes` | Enlazar con `contains`, `references`, `depends_on` o `related_to`. |
| `workspace_create_project` | Crear `code/{name}` y nodo `kind=project`. |

### Grupo: Refactor Y Reparacion

Codigo:

```text
verification_code="mapa-lima-42"
```

Usa este grupo para operaciones amplias, estructurales o semiautomaticas:

| Tool | Uso |
|---|---|
| `workspace_ensure_structure` | Reparar estructura plana, legacy y consistencia basica. |
| `workspace_migrate_legacy` | Migrar carpetas legacy a SQLite. |
| `workspace_scan_artifacts` | Escanear archivos reales bajo `code/` y actualizar artifacts. |

### Grupo: Coordinacion Agentica

Codigo:

```text
verification_code="bitacora-nube-8"
```

Usa este grupo para eventos, tareas y sincronizacion de documentos agenticos:

| Tool | Uso |
|---|---|
| `workspace_record_agent_event` | Registrar un evento agentico estructurado. |
| `workspace_claim_task` | Registrar que un agente toma una tarea. |
| `workspace_complete_task` | Registrar que una tarea agentica termino. |
| `workspace_sync_agent_docs` | Actualizar `agent-team` y `agent-log` desde events. |

Tools de lectura/auditoria como `workspace_get_node`, `workspace_search_nodes`,
`workspace_list_all_nodes`, `workspace_list_edges`,
`workspace_verify_db_completeness`, `workspace_list_events` y
`workspace_agent_status` no requieren codigo.

## Modo Escritura Normal

1. Leer orientacion:
   ```text
   workspace_get_node("index")
   workspace_search_nodes("concepto", limit=8)
   ```

2. Comprobar si ya existe:
   ```text
   workspace_search_nodes("titulo o slug probable")
   ```

3. Elegir `kind` por proposito.

4. Escribir con padre real:
   ```text
   workspace_upsert_node(..., parent="slug-padre-real")
   ```

5. Si creas un `topic`, crea o enlaza al menos un hijo real.

6. Verificar:
   ```text
   workspace_get_node("slug")
   workspace_list_edges()
   ```

## Modo Refactor Y Migracion

### Flujo Obligatorio

1. Inventario:
   ```text
   workspace_get_node("index")
   workspace_list_all_nodes()
   workspace_list_edges()
   python3 ~/.hermes/scripts/health-check.py --workspace NOMBRE
   ```

2. Clasificacion:

   | Caso | Accion |
   |---|---|
   | contenedor artificial vacio | borrar tras backup |
   | contenedor artificial con hijos | reparentar hijos al padre real y borrar contenedor |
   | project con prefijo `project-` | renombrar quitando prefijo si no hay conflicto |
   | falso project index | convertir a `doc` hijo del project real |
   | falso important | convertir a `doc` salvo que sea riesgo real |
   | topic sin hijos | convertir a `doc` o crear/enlazar docs hijos reales |
   | subtopic | convertir a `doc` o mover al `index`/`project` |
   | `agent-node` legacy | convertir a `agent-note`, `agent-plan`, `agent-log` o `doc` segun proposito |
   | duplicado real | fusionar solo si el contenido es claramente el mismo |

3. Backup antes de modificar DB reales:
   ```text
   cp ~/.hermes/workspaces/NOMBRE/workspace.db ~/.hermes/workspaces/NOMBRE/workspace.db.bak-YYYYMMDD-HHMMSS
   ```

4. Ejecucion segura:
   - preferir tools `workspace_*`;
   - usar SQL directo solo si la tool no puede expresar el cambio;
   - no borrar antes de reparentar;
   - sincronizar `parent_id` y edge `contains`;
   - no fusionar contenido ambiguo automaticamente.

5. Validacion final:
   ```text
   python3 ~/.hermes/scripts/health-check.py --workspace NOMBRE
   workspace_list_all_nodes()
   workspace_list_edges()
   ```

### Criterios De Exito

- un solo `index`;
- cero contenedores artificiales;
- cero projects con slug `project-*`;
- cero `agent-node`;
- cero topics sin hijos;
- cero subtopics;
- todo `parent_id` tiene edge `contains`;
- el `index` describe la estructura real.

## Ejemplos Correctos

Crear proyecto:

```text
workspace_create_project(
  name="jrvalle-web",
  description="Web de Jrvalle. Actua como mini-index del proyecto.",
  verification_code="brujula-cobre-17"
)
```

Crear topic global con docs hijos:

```text
workspace_upsert_node(
  slug="empresa",
  title="DoYouWin — Empresa",
  kind="topic",
  summary="Mapa del area empresa.",
  body="# Empresa\n\nMapa breve: MyHelpCar, Fidelity y relacion comercial.",
  parent="index",
  verification_code="brujula-cobre-17"
)
workspace_upsert_node(
  slug="myhelpcar",
  title="MyHelpCar SL",
  kind="doc",
  summary="Detalle de MyHelpCar.",
  body="# MyHelpCar SL\n\nContenido...",
  parent="empresa",
  verification_code="brujula-cobre-17"
)
```

Crear important de proyecto:

```text
workspace_upsert_node(
  slug="jrvalle-web-riesgos",
  title="Jrvalle Web — Riesgos y Errores Conocidos",
  kind="important",
  summary="Cosas que hay que saber para no romper el proyecto.",
  body="# Riesgos\n\n- No cambiar...",
  parent="jrvalle-web",
  verification_code="brujula-cobre-17"
)
```

Crear plan agentico:

```text
workspace_upsert_node(
  slug="agent-plan-jrvalle-home",
  title="Plan — Jrvalle Home",
  kind="agent-plan",
  summary="Plan de trabajo para la home.",
  body="# Plan\n\n...",
  parent="agent-team",
  verification_code="brujula-cobre-17"
)
workspace_upsert_node(
  slug="agent-log-jrvalle-home",
  title="Log — Jrvalle Home",
  kind="agent-log",
  summary="Historial del plan Jrvalle Home.",
  body="# Log\n\n...",
  parent="agent-plan-jrvalle-home",
  verification_code="brujula-cobre-17"
)
```

## Borrado De Workspaces

No existe tool agentica para borrar workspaces. El usuario debe ejecutar
manualmente:

```text
python3 ~/.hermes/scripts/delete-workspace.py --workspace NOMBRE
```

Nunca ejecutes `delete-workspace.py --execute`.

## Checklist Final

- [ ] Lei `index` y busque nodos existentes antes de escribir.
- [ ] No cree nodos carpeta artificiales.
- [ ] No use prefijo `project-` en proyectos nuevos.
- [ ] Use `project` solo para areas de trabajo reales.
- [ ] Use `topic` solo si tiene o tendra hijos.
- [ ] No cree subtopics.
- [ ] Use `agent-note`, `agent-plan` y `agent-log`; no `agent-node`.
- [ ] El padre es un nodo real.
- [ ] Use `important` solo para riesgos, errores, advertencias y decisiones criticas.
- [ ] Inclui el `verification_code` del grupo correcto en toda tool que modifica DB.
- [ ] Verifique con `workspace_get_node` y `workspace_list_edges`.
