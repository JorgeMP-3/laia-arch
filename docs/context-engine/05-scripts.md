# Scripts y Herramientas del Context Engine DB

Este documento cubre el ecosistema de scripts y herramientas que gestionan, mantienen y diagnostican el sistema DB-only del Hermes Context Engine. Todos los scripts viven en `~/.hermes/scripts/` y operan sobre workspaces en `~/.hermes/workspaces/`.

---

## 1. `create-workspace.py`

**Ruta:** `~/.hermes/scripts/create-workspace.py`

### Proposito y Capacidades

`create-workspace.py` es el punto de entrada principal para crear, editar, reparar y migrar workspaces DB-only en Hermes. Es un script polivalente que opera en varios modos segun los argumentos proporcionados.

### Argumentos de Linea de Comandos

| Argumento | Descripcion |
|-----------|-------------|
| `--name <nombre>` | Nombre del workspace sobre el que operar |
| `--edit` | Entrar en modo interactivo de edicion de un workspace existente |
| `--activate` | Activar el workspace como workspace activo en `config.yaml` tras crearlo |
| `--restart` | Reiniciar el gateway de Hermes (`launchctl kickstart`) tras los cambios |
| `--repair` | Reparar un workspace existente (estructura de carpetas + verificacion DB) |
| `--force-import` | Al reparar, ejecutar migracion legacy explícita en lugar de solo verificar |
| `--migrate-legacy` | Migrar estructura legacy a `workspace.db`, mover codigo a `code/` y archivar |
| `--no-archive` | No crear archivo comprimido al migrar legacy |
| `--keep-legacy` | No eliminar carpetas legacy tras verificar la migracion |
| `--backup-root <ruta>` | Directorio personalizado para guardar el archivo comprimido legacy |
| `--with-nodes` | Bandera de compatibilidad legacy; actualmente las areas siempre crean nodos |

### Modo Interactivo vs No-Interactivo

Sin argumentos adicionales, el script entra en modo interactivo:

1. Solicita el nombre del workspace (con validacion: solo minusculas, numeros, guiones y guiones bajos)
2. Si el workspace existe, pregunta si desea editarlo en lugar de crearlo
3. Solicita descripcion breve
4. Solicita areas principales (una por linea, linea vacia para terminar)
5. Pregunta si desea activar el workspace en `config.yaml`
6. Pregunta si desea reiniciar el gateway

**Ejemplo de uso no-interactivo:**
```bash
python3 ~/.hermes/scripts/create-workspace.py --name mi-proyecto --activate --restart
```

### Que Crea para un Nuevo Workspace

Cuando se crea un workspace nuevo, el script:

1. **Llama a `store.ensure_workspace_layout()`** - Crea la estructura de carpetas base:
   - `code/` - Para codigo y proyectos
   - `code/scripts/` - Para scripts especificos del workspace
   - `context/` - Para exports Markdown bajo demanda
   - `docs/` - Para documentacion exportada
   - `docs/db-export/` - Para exports organizados del workspace.db
   - `agents/` - Para logs de actividad del agente
   - `artifacts/` - Para artefactos externos referenciados

2. **Llama a `store.seed_workspace(description, areas)`** - Inicializa `workspace.db` con:
   - Nodo index (`00-index.md`)
   - Nodos tematicos para cada area especificada
   - Tablas schema del sistema

3. **Genera `agents/log.md`** - Archivo de registro de actividad del workspace

4. **Actualiza `config.yaml`** - Registra el workspace en la configuracion del plugin

### Modo Migracion Legacy (`--migrate-legacy`)

Cuando se ejecuta con `--migrate-legacy --name <workspace>`:

1. **Llama a `store.migrate_legacy_to_db()`** - Ejecuta la migracion completa:
   - Lee la estructura legacy de carpetas y archivos
   - Importa nodos existentes a `workspace.db`
   - Mueve archivos de codigo a `code/`
   - Genera backups comprimidos (`.tar.gz`)
   - Elimina la estructura legacy tras verificacion exitosa

2. **Llama a `run_index_scripts(name)`** - Regenera el indice de scripts del workspace

3. **Registra actividad en `agents/log.md`** - Documenta la migracion con archivos tocados y descripcion

### Registro de Actividad en `agents/log.md`

Cada operacion significativa escribe una entrada en `agents/log.md` con el formato:

```markdown
### 2026-04-24 10:30 — create-workspace.py — Crear workspace
- Archivos tocados: agents/, code/, workspace.db
- Qué se hizo: Workspace 'mi-proyecto' creado con source of truth DB-only, activado
```

### Funciones Internas Principales

| Funcion | Proposito |
|---------|-----------|
| `ensure_schema()` | Verifica/crea el esquema de `workspace.db` |
| `seed_workspace(desc, areas)` | Inserta nodos iniciales (index + areas) en la DB |
| `generate_claude_md()` | Genera documentacion del workspace |
| `generate_workspace_doc()` | Genera documentacion general del workspace |
| `append_agent_log()` | Registra actividad en `agents/log.md` |
| `update_config()` | Actualiza `config.yaml` con el workspace activo |

---

## 2. `health-check.py`

**Ruta:** `~/.hermes/scripts/health-check.py`

### Proposito

`health-check.py` verifica el estado estructural y la integridad DB de todos los workspaces (o uno especifico) en Hermes. Detecta problemas de estructura de carpetas, consistencia de la DB y exports Markdown.

### Que Verifica

1. **Estructura de Carpetas** - Confirma que existen las carpetas base definidas en `STANDARD_FOLDERS`:
   - `code/`
   - `code/scripts/`
   - `context/`
   - `docs/`
   - `agents/`
   - `artifacts/`

2. **Auditoria de DB** - Ejecuta `store.audit()` que verifica:
   - Integridad referencial de nodos y relaciones
   - Consistencia de artifacts
   - Nodos huerfanos o relaciones rotas
   - Estadisticas de nodos, relaciones y artifacts

3. **Exports Markdown** - Indica que los exports son bajo demanda (no verifica su contenido)

### Problemas que Detecta

- `FALTA: carpeta <nombre>/` - Estructura incompleta
- `ERROR: <mensaje>` - Problemas de integridad en la DB
- `WARNING: <mensaje>` - Inconsistencias menores
- `INFO: <mensaje>` - Estado informativo

### Bandera `--fix`

Cuando se usa `--fix`:

1. Importa dinamicamente `create-workspace.py` como modulo
2. Llama a `repair_workspace(name, interactive=False, force_import=False)`
3. **Crea carpetas faltantes** - Ejecuta `ensure_workspace_layout()`
4. **Verifica/crea el schema DB** - Ejecuta `ensure_schema()`
5. **Escanea artifacts** - Ejecuta `scan_artifacts()`
6. Si la DB no existe, la inicializa con `seed_workspace()`

```bash
# Verificar todos los workspaces
python3 ~/.hermes/scripts/health-check.py

# Verificar un workspace especifico
python3 ~/.hermes/scripts/health-check.py --workspace mi-proyecto

# Verificar y reparar automaticamente
python3 ~/.hermes/scripts/health-check.py --workspace mi-proyecto --fix
```

### Formato de Salida y Niveles de Severidad

```
workspace: mi-proyecto [ACTIVO]
  ✓ OK — sin problemas detectados
  → nodes=12 edges=34 artifacts=5
  → exports_markdown=bajo demanda
```

Con problemas:
```
workspace: mi-proyecto
  ✗ FALTA: carpeta code/
  ✗ ERROR: Nodo huerfano encontrado: 03b-metodo-doyouwin
  → FIX aplicado: code/
  → FIX aplicado: workspace.db inicializado
  → nodes=12 edges=34 artifacts=5
```

### Determinacion del Workspace Activo

Lee `config.yaml` buscando la clave:
```yaml
plugins:
  workspace-context:
    workspace: mi-proyecto
```

---

## 3. `show-injected.py`

**Ruta:** `~/.hermes/scripts/show-injected.py`

### Proposito

`show-injected.py` simula y visualiza exactamente que nodos, instrucciones y contenido se inyectan automaticamente al agente en cada sesion de ChatGPT. Es una herramienta de transparencia y debugging.

### Argumentos de Linea de Comandos

| Argumento | Descripcion |
|-----------|-------------|
| `--workspace <nombre>` | Workspace a inspeccionar (por defecto: el activo en `config.yaml`) |
| `--query <texto>` | Simula prefetch para esta query y muestra que nodos cargaria |
| `--full` | Muestra contenido completo sin truncar la vista previa |

### Secciones de Salida

#### Seccion 1: Auto-Inyectado al Inicio de Cada Sesion

Muestra segun el `inject_mode` configurado:

- **`index`** (por defecto): Solo el nodo index del workspace activo
- **`full`**: Todos los nodos del workspace activo
- **`all-indexes`**: Nodos index de TODOS los workspaces disponibles

Incluye la **instruccion del sistema** generada por `build_instruction()` que replica exactamente el texto que genera el plugin en `system_prompt_block()`.

**Ejemplo de instruccion para modo `index`:**
```
[WORKSPACE ACTIVO: mi-proyecto]
Tienes cargado el nodo index del workspace desde `workspace.db`: te orienta, pero no basta para detalles.
La fuente de verdad es SQLite; `context/` y `docs/db-export/` solo existen si se exportan bajo demanda.
Orden obligatorio: `workspace_search_nodes` -> `workspace_get_node` -> 
`workspace_list_folder`/`workspace_read_workspace_file` si necesitas artefactos reales -> 
`workspace_read_file` solo como compatibilidad.
Ejemplo: si te preguntan por un detalle del workspace, busca con `workspace_search_nodes` y luego
abre el nodo con `workspace_get_node`. No uses `session_search`, `search_files` ni leas exports
Markdown como primer recurso.
```

#### Seccion 2: Nodos Disponibles para Prefetch

Lista todos los nodos disponibles para cada workspace (excluyendo el index) con su tipo (`kind`). Muestra hasta 12 nodos por workspace.

#### Seccion 3: Simulacion de Prefetch (con `--query`)

Cuando se especifica `--query`, el script:

1. **Tokeniza la query** usando `_tokenize_query()`
2. **Busca en todos los workspaces** (modo `all-indexes`) o solo el activo
3. **Aplica factores de correccion**:
   - `mention_boost = 1.5` si tokens de la query coinciden con nombre del workspace
   - `active_boost = 1.1` para el workspace activo vs otros
4. **Ranking cruzado** - Combina resultados de todos los workspaces con puntuaciones normalizadas
5. **Muestra el flujo ideal** de tools para la query

**Ejemplo de salida con query:**
```
--- 3. SIMULACIÓN DE PREFETCH  query: "infraestructura pixelcore" ---

  CARGARÍA: [pixelcore] 40-infraestructura  score=0.8912
  CARGARÍA: [pixelcore] 41-configuracion  score=0.7234

  Flujo ideal para esta query:
  1. workspace_search_nodes(query='infraestructura pixelcore')
  2. workspace_get_node(ref='40-infraestructura', workspace='pixelcore')
  3. Solo si falta contexto: workspace_list_folder / workspace_read_workspace_file
  4. Evitar como primer recurso: session_search, search_files, docs/db-export/, context/*.md
```

#### Seccion 4: Codigo del Workspace

Lista el contenido de `code/` y `code/scripts/` con conteo de archivos.

#### Seccion 5: Export Markdown Bajo Demanda

Muestra el estado de los exports organizados:
- Indica si `docs/db-export/` existe
- Muestra si esta sincronizado o desactualizado
- Explica que la ausencia de exports no es un problema (workspace.db es la fuente)

---

## 4. `sync-workspace-markdown.py`

**Ruta:** `~/.hermes/scripts/sync-workspace-markdown.py`

### Proposito

`sync-workspace-markdown.py` exporta bajo demanda el contenido de `workspace.db` a archivos Markdown, generando tanto la vista plana (`context/`) como la vista organizada (`docs/db-export/`).

### Argumentos de Linea de Comandos

| Argumento | Descripcion |
|-----------|-------------|
| `--workspace <nombre>` | Sincronizar solo este workspace |
| `--all` | Sincronizar todos los workspaces |
| `--watch` | Activar modo observador (file watching loop) |
| `--interval <seg>` | Intervalo de verificacion en segundos (por defecto: 2.0) |
| `--output-dir <ruta>` | Ruta para el snapshot organizado (por defecto: `docs/db-export`) |

### Dual Export: `context/` y `docs/db-export/`

El script exporta a dos destinos simultaneamente:

1. **`context/`** - Vista plana con archivos individuales:
   - `00-index.md` - Nodo index
   - `XX-slug-title.md` - Nodos tematicos
   - Un archivo por nodo en la DB

2. **`docs/db-export/`** - Vista organizada jerarquicamente:
   - Estructura de carpetas que refleja la taxonomia del workspace
   - `00-index.md` - Indice principal
   - Subcarpetas por area/tema

### Modo `--watch`

El modo observador funciona asi:

1. Lee el timestamp de modificacion (`mtime`) de `workspace.db`
2. Cada `interval` segundos, verifica si el `mtime` ha cambiado
3. Si detecto cambios, re-exporta automaticamente
4. Presiona `Ctrl+C` para salir

```bash
# Sincronizar un workspace especifico
python3 ~/.hermes/scripts/sync-workspace-markdown.py --workspace mi-proyecto

# Sincronizar todos los workspaces
python3 ~/.hermes/scripts/sync-workspace-markdown.py --all

# Observar cambios en un workspace (re-exporta automaticamente)
python3 ~/.hermes/scripts/sync-workspace-markdown.py --workspace mi-proyecto --watch

# Observar todos con intervalo de 5 segundos
python3 ~/.hermes/scripts/sync-workspace-markdown.py --all --watch --interval 5
```

### Valor de Retorno

El script retorna (imprime) un diccionario con:
- `workspace` - Nombre del workspace
- `context_written` - Cantidad de archivos escritos en `context/`
- `organized_written` - Cantidad de archivos escritos en `docs/db-export/`
- `context_removed` - Archivos eliminados de `context/` (obsoletos)
- `organized_removed` - Archivos eliminados de `docs/db-export/` (obsoletos)
- `db_mtime` - Timestamp de modificacion de la DB

---

## 5. `workspace-daily-diagnostic.py`

**Ruta:** `~/.hermes/scripts/workspace-daily-diagnostic.py`

### Proposito

`workspace-daily-diagnostic.py` es una herramienta de validacion que verifica que el flujo DB-first funciona correctamente para preguntas reales del dia a dia. Define casos de prueba que representan queries comunes.

### Casos de Prueba Definidos

| ID | Pregunta | Query | Workspace | Nodo Esperado |
|----|----------|-------|-----------|---------------|
| `metodo-doyouwin` | ¿Cuáles son las 3 fases del Método DoYouWin? | `metodo doyouwin fases` | `doyouwin` | `02b-metodo-doyouwin` |
| `pixelcore-infra` | Explícame la infraestructura de PixelCore | `infraestructura pixelcore` | `pixelcore` | `40-infraestructura` |
| `laia-arch-honesty` | ¿Qué sabe laia-arch y qué no sabe todavía? | `arquitectura laia` | `laia-arch` | `00-index` |
| `pixelcore-servidor` | Relaciona PixelCore con Servidor_JMP | `pixelcore servidor infraestructura` | `pixelcore` | `40-infraestructura` |

### Que Valida Cada Caso

Para cada caso, el diagnostico:

1. **Ejecuta `workspace_search_nodes`** con la query definida
2. **Verifica que nodos se encuentran** (si hay resultados)
3. **Muestra el ranking de nodos candidatos** con scores
4. **Compara con el nodo esperado** (`expected_ref`)
5. **Lista tools que NO deberian aparecer primero** (`forbidden`):
   - `session_search` - Busqueda de sesiones
   - `search_files` - Busqueda de archivos del sistema
   - `docs/db-export como primer recurso` - Exports Markdown
   - `inventar contenido` - Alucinacion

### Salida de Diagnostico

```
=== metodo-doyouwin ===
Pregunta: ¿Cuáles son las 3 fases del Método DoYouWin?
Tools esperadas:
  1. workspace_search_nodes
  2. workspace_get_node
  3. workspace_list_folder / workspace_read_workspace_file solo si faltan artefactos reales
Tools que no deberían aparecer primero:
  - session_search
  - search_files
  - docs/db-export como primer recurso
Nodos candidatos encontrados:
  - [doyouwin] 02b-metodo-doyouwin (topic) score=0.9541
  - [doyouwin] 02a-introduccion (topic) score=0.8234
Flujo ideal:
  workspace_search_nodes(query='metodo doyouwin fases')
  workspace_get_node(ref='02b-metodo-doyouwin')
Criterio de fallo:
  - empieza por session_search o search_files
  - lee docs/db-export o context/*.md como primer recurso
  - responde detalles sin haber pasado por búsqueda nodal
```

### Ejecucion

```bash
# Ejecutar todos los casos de prueba
python3 ~/.hermes/scripts/workspace-daily-diagnostic.py

# Ejecutar un solo caso
python3 ~/.hermes/scripts/workspace-daily-diagnostic.py --case metodo-doyouwin
```

---

## 6. `index-scripts.py`

**Ruta:** `~/.hermes/scripts/index-scripts.py`

### Proposito

`index-scripts.py` escanea todos los scripts disponibles en Hermes (globales y por workspace) y genera/actualiza `scripts/INDEX.md` con un indice completo y descripciones extraidas automaticamente.

### Lo que Escanea

1. **Scripts Globales** - `~/.hermes/scripts/`:
   - Archivos con extension `.py`, `.sh`, `.js`, `.ts`
   - Excluye `INDEX.md` y archivos ocultos
   - Extrae descripcion del docstring o comentarios

2. **Scripts de Workspace** - `workspaces/{ws}/code/scripts/`:
   - Recursive en subdirectorios
   - Misma logica de extraccion de descripcion
   - Genera rutas relativas `workspaces/{ws}/code/scripts/...`

### Extraccion de Descripciones

El script extrae descripciones en orden de prioridad:

1. **Docstring multilinea** - Primeras lineas entre `"""` o `'''`
2. **Docstring inline** - Contenido en una misma linea
3. **Comentarios de una linea** - Lineas que empiezan con `#` (pero no separadores como `----`)
4. **Comentarios estilo JS** - Lineas que empiezan con `//`
5. **Nombre del archivo** - Si no encuentra nada anterior

### Formato del INDEX.md Generado

```markdown
# Scripts Index

Índice global de los scripts de Hermes. Se regenera automáticamente desde los
scripts globales de `~/.hermes/scripts/` y `workspaces/{ws}/code/scripts/`.

## global

| Script | Descripción |
|--------|-------------|
| `scripts/create-workspace.py` | Crea, repara y migra workspaces DB-only en Hermes. |
| `scripts/health-check.py` | Verifica el estado DB-only de los workspaces de Hermes. |

## mi-proyecto

| Script | Descripción |
|--------|-------------|
| `scripts/mi-script.py` | Descripcion del script |

---
*Regenerado con `python3 ~/.hermes/scripts/index-scripts.py`.*
```

### Argumentos de Linea de Comandos

| Argumento | Descripcion |
|-----------|-------------|
| `--workspace <nombre>` | Limitar secciones de workspace a uno concreto |
| `--dry-run` | Mostrar si INDEX.md cambiaria sin escribirlo |

```bash
# Regenerar indice completo
python3 ~/.hermes/scripts/index-scripts.py

# Solo verificar si cambiaria
python3 ~/.hermes/scripts/index-scripts.py --dry-run

# Solo regenerar seccion de un workspace
python3 ~/.hermes/scripts/index-scripts.py --workspace mi-proyecto
```

---

## 7. `cleanup-sessions.py`

**Ruta:** `~/.hermes/scripts/cleanup-sessions.py`

### Proposito

`cleanup-sessions.py` archiva y elimina sesiones antiguas de Hermes para liberar espacio en disco. Soporta tanto el directorio de sesiones actual (`sessions/`) como el legacy (`logs/sessions/`).

### Directorios que Gestiona

| Tipo | Directorio Primario | Directorio de Archivo |
|------|---------------------|----------------------|
| Primario | `~/.hermes/sessions/` | `~/.hermes/sessions/archive/` |
| Legacy | `~/.hermes/logs/sessions/` | `~/.hermes/logs/archive/` |

### Argumentos de Linea de Comandos

| Argumento | Descripcion |
|-----------|-------------|
| `--execute` | Aplicar cambios; por defecto solo muestra el plan (dry-run) |
| `--keep-days <N>` | Conservar sesiones recientes de los ultimos N dias (por defecto: 30) |
| `--archive-days <N>` | Archivar sesiones entre `keep-days` y N dias (por defecto: 90) |
| `--archive-all` | Nunca eliminar; archivar tambien las mas antiguas que `archive-days` |
| `--legacy` | Usar rutas legacy `logs/sessions` y `logs/archive` |

### Logica de Clasificacion de Sesiones

```
Sesiones clasificadas en 3 categorias:

1. CONSERVAR (< keep-days, por defecto 30 dias)
   - Acceso reciente, no se tocan

2. ARCHIVAR (entre keep-days y archive-days, por defecto 30-90 dias)
   - Se comprimen en .tar.gz organizados por mes
   - Archivo: sessions-YYYY-MM.tar.gz

3. ELIMINAR (> archive-days, por defecto >90 dias)
   - Solo si no se usa --archive-all
   - Se borran definitivamente
```

### Proceso de Archivado

1. **Agrupacion por mes** - Agrupa sesiones por `YYYY-MM` segun su `mtime`
2. **Creacion de tar.gz** - Un archivo por mes: `sessions-YYYY-MM.tar.gz`
3. **Manejo de duplicados** - Si ya existe, anade timestamp: `sessions-YYYY-MM-YYYYMMDDHHMMSS.tar.gz`
4. **Eliminacion post-archivo** - Borra los archivos originales tras comprimir

### Tamaños y Edades

- **Edad** - Determinada por `mtime` (fecha de ultima modificacion) del archivo/carpeta de sesion
- **Tamano** - Calculado recursivamente para carpetas; directo para archivos

### Ejecucion

```bash
# Ver plan sin aplicar (dry-run por defecto)
python3 ~/.hermes/scripts/cleanup-sessions.py

# Aplicar cambios
python3 ~/.hermes/scripts/cleanup-sessions.py --execute

# Conservar ultimos 7 dias, archivar hasta 30, eliminar el resto
python3 ~/.hermes/scripts/cleanup-sessions.py --keep-days 7 --archive-days 30 --execute

# Archivar todo sin eliminar (incluso sesiones muy antiguas)
python3 ~/.hermes/scripts/cleanup-sessions.py --archive-all --execute

# Usar rutas legacy
python3 ~/.hermes/scripts/cleanup-sessions.py --legacy --execute
```

### Salida de Ejemplo

```
Sesiones: ~/.hermes/sessions
Archivo:  ~/.hermes/sessions/archive
Total:    47 sesiones (1.2 GB)
  Conservar (< 30 días): 12 (340.5 MB)
  Archivar (30-90 días): 23 (682.3 MB)
  Eliminar (> 90 días): 12 (201.7 MB)
  Meses a archivar: 2025-10, 2025-11, 2025-12

Espacio a liberar: ~201.7 MB

DRY RUN — usa --execute para aplicar cambios
```

---

## 8. Scripts del Directorio Global

El directorio `~/.hermes/scripts/` contiene scripts globales (no especificos de workspace) adicionales:

### `datasette-start.sh`

**Proposito:** Lanza Datasette con todos los workspaces de Hermes como bases de datos consultables.

**Uso:**
```bash
bash ~/.hermes/scripts/datasette-start.sh
```

**Lo que hace:**
1. Crea symlinks de todos los `workspace.db` en `~/.hermes/cache/datasette-dbs/`
2. Mata cualquier instancia previa de Datasette en puerto 8076
3. Lanza Datasette sirviendo todos los archivos `.db` en `http://localhost:8076`

### `start_mlx_servers.sh`

**Proposito:** Inicia los servidores MLX de vision y TTS para Hermes.

**Uso:**
```bash
bash ~/.hermes/scripts/start_mlx_servers.sh
```

**Lo que hace:**
1. Verifica que el entorno MLX existe en `~/.hermes/mlx-servers/.venv`
2. Comprueba si el servidor de vision ya esta corriendo en puerto 8080
3. Si no esta corriendo, inicia `mlx_vlm.server` con el modelo `Qwen2.5-VL-3B-Instruct-4bit`
4. Comprueba si el servidor TTS ya esta corriendo en puerto 8081
5. Si no esta corriendo, inicia `mlx_audio.server`
6. Escribe logs a `~/.hermes/mlx-servers/logs/`

---

## Resumen de Scripts Disponibles

| Script | Funcion Principal |
|--------|-------------------|
| `create-workspace.py` | Crear, editar, reparar, migrar workspaces |
| `health-check.py` | Verificar estado estructural y DB de workspaces |
| `show-injected.py` | Mostrar que se inyecta al agente en cada sesion |
| `sync-workspace-markdown.py` | Exportar workspace.db a Markdown bajo demanda |
| `workspace-daily-diagnostic.py` | Diagnosticar flujo DB-first con casos de prueba |
| `index-scripts.py` | Generar indice de todos los scripts en INDEX.md |
| `cleanup-sessions.py` | Archivar y eliminar sesiones antiguas |
| `datasette-start.sh` | Lanzar Datasette para exploracion visual de DBs |
| `start_mlx_servers.sh` | Iniciar servidores MLX (vision + TTS) |
