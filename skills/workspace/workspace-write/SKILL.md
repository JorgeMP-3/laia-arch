---
name: workspace-write
description: >
  Escritura, estructura, mantenimiento y refactor de workspaces LAIA DB-first.
  Define la taxonomia canonica, como esta creada la base de datos, cuando usar
  cada kind, como hacer cambios normales y como reorganizar muchos nodos con
  backup y validacion.
version: "7.0.0"
author: LAIA Agent
license: MIT
metadata:
  hermes:
    tags: [workspace, write, db-first, nodes, edges, refactor, migration]
    category: workspace
---

# Workspace — Escritura, Estructura Y Refactor

## Regla Principal

La fuente de verdad es `workspace.db`. Los exports Markdown son derivados.

Esta es la unica skill de escritura para workspaces LAIA. Tambien es la fuente
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

> **Pitfall — `active_workspaces` en config:** `workspace_create_workspace` y
> cualquier operacion de escritura fallan con "workspace X es de solo lectura"
> cuando el workspace no esta en `active_workspaces` dentro de la config del
> plugin `workspace-context`. El `hermes_home` no es `~/.hermes` en este
> entorno — la config vive en `/home/laia-arch/LAIA/config.yaml`. Añade el
> workspace a `plugins.workspace-context.active_workspaces` antes de escribir.

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

No uses `detail`, `agent-node` ni kinds plurales como `projects`, `topics`, `docs`, `references` o `scripts`.

## Pitfalls Frecuentes

- **NUNCA crees un nodo `topic` vacio.** Si un topic no tiene (ni va a tener) docs hijos reales, crea un `doc` en su lugar.
- **NUNCA uses nombres plurales para nodos** (ej. `docs`, `references`, `scripts`). El kind ya indica la categoria.
- **Antes de escribir en un workspace, verifica que es editable** con `workspace_list_workspaces`. Si no esta en `active_workspaces` del plugin, la escritura fallara. Actualizar `~/.hermes/config.yaml` si es necesario.
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

## SQL Directo Para Operaciones Complejas

Para operaciones estructurales bulk, **preferir SQL directo via `execute_code`** sobre muchas llamadas a `workspace_upsert_node`:

- Deteccion y eliminacion de duplicados (varios nodos a la vez)
- Re-categorizacion masiva de `kind` (ej: `topic` -> `doc`)
- Reparacion de `parent_id` en lote
- Sincronizacion de `parent_id` + edge `contains` en una sola transaccion

Patron seguro:

```python
import sqlite3, shutil, datetime

db = "/path/to/workspace.db"
backup = f"{db}.bak-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(db, backup)

conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("BEGIN TRANSACTION")
# tus UPDATEs o DELETEs aqui
cur.execute("COMMIT")
conn.close()
```

Nota: toda escritura en DB real requiere `verification_code` en las tools de escritura. EI SQL directo no tiene verificacion automatica — usa backup previo y valida con `workspace_list_all_nodes` despues.

## Modo Escritura Normal

1. Leer orientacion:
   ```
   workspace_get_node("index")
   workspace_search_nodes("concepto", limit=8)
   ```

2. Comprobar si ya existe:
   ```
   workspace_search_nodes("titulo o slug probable")
   ```

3. Elegir `kind` por proposito.

4. Escribir con padre real:
   ```
   workspace_upsert_node(..., parent="slug-padre-real")
   ```

5. Si creas un `topic`, crea o enlaza al menos un hijo real.

6. Verificar:
   ```
   workspace_get_node("slug")
   workspace_list_edges()
   ```

## Documentar Una Implementacion Nueva En La BD

Cuando se implementa codigo nuevo (plugin, backend, frontend, script) y toca documentarlo
en la BD:

**Paso 0 — Leer la BD existente antes de做任何 cosa:**
```
workspace_get_node("nombre-del-proyecto-o-area")
workspace_search_nodes("feature area nombre", limit=8)
```
El usuario se ha negado a aprobar planes generados sin verificar primero la documentacion
existente. Leer siempre la BD primero, aunque creas conocer el area. No generes el plan
de documentacion hasta haber confirmado que los nodos existentes no cubren la feature.

**Paso 1 — Investigar el codigo:**
- Leer los archivos fuente relevantes directamente (`read_file` con offset/limit)
- No asumir que lo que dice el issue/PR/plan es lo que realmente se implemento
- Verificar constantes, funciones, endpoints, campos de config, errores y logs reales

**Paso 2 — Generar plan de documentacion:**
Presentar al usuario un plan de integracion con:
- Que nodos existententes de la BD estan desactualizados o incompletos
- Que nodos hay que crear o reescribir
- Distribucion de trabajo por agente si es multi-agente
- Criterios de verificacion posteriores

**Paso 3 — Aprobacion del usuario antes de ejecutar.**

**Paso 4 — Ejecutar solo lo aprobado.**

## Restructuracion Mayor: SQL Directo

Para reorganizar muchos nodos a la vez (cambiar padres, corregir edges, convertir kinds), las tools individuales son lentas. Usa SQL directo via terminal con Python.

**Paso 1 — DB path:** `hermes_home` NO es `~/.hermes`. En este entorno es `/home/laia-arch/LAIA`. Descúbrelo con:

```python
import sys; sys.path.insert(0, '/home/laia-arch/LAIA/.laia-arch')
from hermes_constants import get_hermes_home
db_path = str(get_hermes_home() / 'workspaces' / 'NOMBRE' / 'workspace.db')
```

**Paso 2 — Inventario previo:**
```python
cur.execute("SELECT id, slug, kind, parent_id FROM nodes ORDER BY id")
cur.execute("SELECT id, edge_type, from_node_id, to_node_id FROM edges ORDER BY id")
```

**Paso 3 — Reparent:** `UPDATE nodes SET parent_id = ? WHERE id = ?`

**Paso 4 — Sync edges:** `UPDATE edges SET from_node_id = ? WHERE id = ?`

**Paso 5 — Borrar huérfanos:** `DELETE FROM edges WHERE id = ?`

**Paso 6 — Convertir topics vacíos:** topics sin hijos (`kind=topic` con `parent_id` que no aparece como `from_node_id` en ninguna edge) deben convertirse a `doc`:
```python
cur.execute("UPDATE nodes SET kind='doc', slug=? WHERE id=? AND kind='topic'")
```

**Siempre:** hacer todo en una sola transacción (`conn.commit()`), verificar antes y después con `workspace_list_edges()`.

**ATENCION:** `workspace_create_project` si recibe un slug que ya existe como topic, lo convierte a project silenciosamente. Verifica edges después.

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

## Docs de referencia

- `references/laia-arquitectura.md` — contexto completo del proyecto LAIA (ARCH, AGORA, AGENTE, nomenclatura)
- Seccion `## Ejemplos Correctos` mas abajo para patrones de creacion de nodos.

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

## Config Y Estructura De Procesos

### Archivos de config

| Componente | HERMES_HOME | Config.yaml |
|---|---|---|
| LAIA gateway (hermes.service) | configurable | `HERMES_HOME/config.yaml` |
| TUI gateway (proceso hijo de tui) | configurable | `HERMES_HOME/config.yaml` |
| Backend workspace-ui | configurable | `HERMES_HOME/config.yaml` |
| Terminal shell (python3 scripts) | `HERMES_HOME` env var | `HERMES_HOME/config.yaml` |

Todos leen el mismo archivo pero lo cachean en memoria al arrancar. El plugin
`workspace-context` tiene `_refresh_config_if_changed()` que relee por mtime,
pero ese metodo solo funciona dentr del mismo proceso.

**Implicacion critica**: si cambias `active_workspaces` en `config.yaml` y la
session activa del agente dice que no es editable (pero el archivo si lo dice),
el proceso del gateway tiene stale config cacheada. La unica solucion es
reiniciar el proceso gateway. El backend workspace-ui puede tener una config
distinta porque es un proceso separado.

→ Procedimiento de diagnostico: `references/stale-config-diagnosis.md`

### Sintomas de stale config

```
# El archivo dice una cosa
grep active_workspaces $HERMES_HOME/config.yaml
# -> ['pixelcore', 'laia-arch']

# Pero las workspace tools dicen otra
workspace_list_workspaces()
# -> active_workspaces: ["pixelcore"]
```

### Diagnostico rapido

1. Verificar que dice el archivo:
   ```
   python3 -c "
   import yaml
   cfg = yaml.safe_load(open('$HERMES_HOME/config.yaml'))
   ws = cfg.get('plugins', {}).get('workspace-context', {})
   print('archivo:', ws.get('active_workspaces'))
   "
   ```

2. Verificar que ve el backend (API):
   ```
   curl -s http://localhost:8077/api/context-engine/injected | python3 -c "
   import sys, json; d = json.load(sys.stdin)
   print('backend ve:', sorted(d.get('nodes_by_workspace', {}).keys()))
   "
   ```

3. Si discrepan: el proceso gateway necesita reinicio.

4. Si coincide pero la tool sigue devolviendo stale: la session del agente
   tiene caches internas que no se resetean sin reiniciar sesion.

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
- [ ] Si `active_workspaces` no coincide entre archivo y tool, reinicia el proceso gateway antes de asumir que hay un bug.
- [ ] Si actualizo un workspace de servidor, verifique que index y docs describen el HARDWARE y SERVICIOS REALES (no un servidor anterior, no un stack diferente).
- [ ] Tras cambiar el index, verifique CLAUDE.md del workspace — puede contener texto desfasado no derivado de la DB.
- [ ] Tras cambios bulk, exporte el workspace (`workspace_export_markdown`).

## Orden De Update Cuando Se Audita Un Workspace Completo

Cuando un usuario pide auditar o actualizar "todo" un workspace:

1. **Index primero** — es lo que se ve en pantalla. Si describe hardware, stack o servicios, debe estar correcto antes que nada.
2. **Docs globales** (`readme`, `doc-00`, `doc-01`, etc.) — suelen tener vision general y tambien describen hardware/stack.
3. **Topics** — suelen tener contenido sustancial ya desarrollado.
4. **Hijos de topics** — puede que sean redundantes si el topic padre ya tiene todo el contenido. En ese caso, eliminar los hijos tras verificar.
5. **Exportar** — `workspace_export_markdown` al terminar.

## Bloqueo De Verificacion Para Contenido De Servidor

Cuando trabajes en un workspace que documenta un servidor fisico (hardware, servicios, Docker, red):

> **PITFALL: No confies ciegamente en el contenido existente de la DB.**
> Un index puede describir "Mac mini M4 con NPM en Docker" cuando el servidor real es un Dell OptiPlex 9020 con nginx nativo y cloudflared nativo. Si el usuario se queja de que el contenido "esta como el puto culo" o esta "sin actualizar", verifica contra los archivos fuente reales (`docs/` o `code/`) antes de asumir que la DB es correcta.

Pasos al auditar un workspace de servidor:
1. Leer los archivos fuente reales (Markdown en `docs/`, archivos de configuracion en `code/`)
2. Listar todos los nodos de la DB (`workspace_list_all_nodes`)
3. Comparar — si la DB describe hardware, OS, software o arquitectura diferente a los archivos fuente, la DB es la que esta mal
4. Corregir en orden: index → global docs → topics → topic children
5. Eliminar nodos hijos de topics que sean redundantes o desfasados
6. Exportar y actualizar CLAUDE.md

> **PITFALL: Cuando el usuario dice que algo esta "desfasado" o "sin actualizar", no hagas un fix parcial.** Significa que quiere que revises TODO el workspace. Si dice "esta como el puto culo", haz auditoria completa: index, todos los docs, todos los topics y sus hijos, y exporta al terminar. Partial fixes frustrate him more than doing nothing.
