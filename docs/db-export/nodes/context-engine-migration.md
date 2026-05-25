# Migration System (Legacy to DB)

## Metadata

- ID: `83`
- Slug: `context-engine-migration`
- Kind: `doc`
- Status: `active`
- Filename: `context-engine-migration.md`
- Parent: `context-engine-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:33:58.317232+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `context-engine-migration`

## Summary

**Método principal:** `WorkspaceStore.migrate_legacy_to_db()`

## Body

# Migration System — Legacy to DB

# Sistema de Migración — Legacy a DB-First

**Método principal:** `WorkspaceStore.migrate_legacy_to_db()`
**Script helper:** `create-workspace.py --migrate-legacy`
**Tool plugin:** `workspace_migrate_legacy`

---

## 1. Modelo Legacy vs DB-First

| Aspecto | Legacy | DB-First |
|---------|--------|----------|
| Fuente de verdad | Archivos Markdown | `workspace.db` (SQLite) |
| Buscar | `context/*.md` | FTS5 en SQLite |
| Relaciones | Indicadores `→` en MD | Tabla `edges` con tipos |
| Código | Raíz disperso | Centralizado en `code/` |
| Coordenación | Archivos en `agents/` | Tabla `events` |
| Exporte | Manual | Bajo demanda |

---

## 2. Paths Legacy Recognizados

```python
legacy_paths = [
    "README.md",
    "context/",
    "agents/",
    "docs/",
    "projects/",
    "scripts/",
]
```

---

## 3. Proceso de Migración Completo

### Paso 1: Backup

```python
backup_dir = "~/.laia/backups/legacy-workspaces/"
archive = f"{workspace}-{timestamp}.tar.gz"
```

Todos los paths se comprimen ANTES de tocar nada.

---

### Paso 2: Import de README.md

- Nodo `kind='doc'`, `slug='readme'`
- Título desde primer `# heading`
- Body completo
- Enlaza al index con `references`

---

### Paso 3: Import de context/

Para cada `*.md` en `context/`:
1. Lee contenido, extrae título desde `# heading`
2. Infiere `kind` desde nombre de archivo:
   - `00-index.md` → `index`
   - `NN-name.md` → `topic`
   - `NN[a-z]-name.md` → `detail`
   - `project-*.md` → `project`
3. Crea nodo con `source_kind='legacy-context'`
4. Resuelve indicadores `→ Target: slug.md` → edges `details`
5. Si no es `index`, enlaza al index con `details`

---

### Paso 4: Import de agents/

Para cada `*.md` en `agents/` recursivo:
- `kind='agent-note'`
- Slug: `agent-{path_relativo_slugified}`
- `source_kind='legacy-agents'`
- Enlaza al index con `contains`

---

### Paso 5: Import de docs/

Archivos en `docs/` → nodos `kind='doc'` o `kind='reference'`. Excluye `docs/db-export/`.

---

### Paso 6: Import de projects/

Para cada directorio en `projects/`:
1. Busca info: `info.md`, `README.md`, o `00-index.md`
2. Crea nodo `kind='project'`, slug `project-{name}`
3. Enlaza al index con `project_of`
4. Archivos `.md` internos → nodos `doc` hijos con `contains`
5. Archivos no-MD → movidos a `code/{project_name}/`

---

### Paso 7: Import de scripts/

- `.md` en scripts/ → nodos `kind='script'`, `source_kind='legacy-scripts'`
- Otros archivos → movidos a `code/scripts/`

---

### Paso 8: Mover Código a code/

Archivos no-MD de projects/scripts se mueven a `code/`.

---

### Paso 9: Verificación

```python
verification = store.verify_db_completeness()
# Verifica: node_count > 0, index_count > 0, body_count > 0
```

---

### Paso 10: Limpieza (opcional)

Si `remove_legacy=True` Y `verified=True`: borra originals.
Si `verified=False`: no borra nada, registra `legacy_migration_failed`.

---

## 4. Método: migrate_from_markdown

Solo importa desde `context/` y `projects/` (no toca agents/docs/scripts):

```python
def migrate_from_markdown(self, *, force: bool = False) -> dict
```

---

## 5. Bootstrap de Workspace Nuevo

```python
def seed_workspace(self, description: str, areas: Iterable[str]) -> dict
```

1. Crea nodo `index` con descripción
2. Crea un nodo `topic` por cada área
3. Enlaza topics al index con `details`
4. Escanea artifacts en `code/`
5. Genera `workspace-doc.md` y `CLAUDE.md`

---

## 6. Scripts Relacionados

### create-workspace.py

```bash
# Crear workspace nuevo
python3 ~/.laia/scripts/create-workspace.py --name mi-workspace --bootstrap "Descripción"

# Migrar estructura legacy
python3 ~/.laia/scripts/create-workspace.py --name mi-workspace --migrate-legacy

# Reparar workspace
python3 ~/.laia/scripts/create-workspace.py --name mi-workspace --repair
```

### health-check.py

Verifica que migración está completa.

---

## 7. Estructura Post-Migración

```
workspace/
├── workspace.db          # Fuente de verdad
├── code/                 # Código (migrado o nuevo)
│   ├── scripts/
│   └── {projects}/
├── context/              # [vacío o regenerado bajo demanda]
├── docs/
│   └── db-export/        # [vacío o regenerado bajo demanda]
└── (legacy paths)         # [eliminados tras verificación]
```

---

## 8. Notas sobre Backups

- Ubicación: `~/.laia/backups/legacy-workspaces/`
- Formato: `workspace-YYYYMMDDTHHMMSSZ.tar.gz`
- Se crean ANTES de cualquier modificación
- Nunca se borran automáticamente

---

## 9. Casos de Fallo

| Problema | Comportamiento |
|----------|----------------|
| DB ya tiene nodos | `migrate_from_markdown` refuse `force=False` |
| Verificación fails | No borra legacy, registra `failed` |
| Archivo destino ya existe | Skip (no sobreescribe) |
| Path no existe | Omite silenciosamente |


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `context-engine-area` (Context Engine) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Migration System (Legacy to DB)

# Migration System — Legacy to DB

# Sistema de Migración — Legacy a DB-First

**Método principal:** `WorkspaceStore.migrate_legacy_to_db()`
**Script helper:** `create-workspace.py --migrate-legacy`
**Tool plugin:** `workspace_migrate_legacy`

---

## 1. Modelo Legacy vs DB-First

| Aspecto | Legacy | DB-First |
|---------|--------|----------|
| Fuente de verdad | Archivos Markdown | `workspace.db` (SQLite) |
| Buscar | `context/*.md` | FTS5 en SQLite |
| Relaciones | Indicadores `→` en MD | Tabla `edges` con tipos |
| Código | Raíz disperso | Centralizado en `code/` |
| Coordenación | Archivos en `agents/` | Tabla `events` |
| Exporte | Manual | Bajo demanda |

---

## 2. Paths Legacy Recognizados

```python
legacy_paths = [
    "README.md",
    "context/",
    "agents/",
    "docs/",
    "projects/",
    "scripts/",
]
```

---

## 3. Proceso de Migración Completo

### Paso 1: Backup

```python
backup_dir = "~/.laia/backups/legacy-workspaces/"
archive = f"{workspace}-{timestamp}.tar.gz"
```

Todos los paths se comprimen ANTES de tocar nada.

---

### Paso 2: Import de README.md

- Nodo `kind='doc'`, `slug='readme'`
- Título desde primer `# heading`
- Body completo
- Enlaza al index con `references`

---

### Paso 3: Import de context/

Para cada `*.md` en `context/`:
1. Lee contenido, extrae título desde `# heading`
2. Infiere `kind` desde nombre de archivo:
   - `00-index.md` → `index`
   - `NN-name.md` → `topic`
   - `NN[a-z]-name.md` → `detail`
   - `project-*.md` → `project`
3. Crea nodo con `source_kind='legacy-context'`
4. Resuelve indicadores `→ Target: slug.md` → edges `details`
5. Si no es `index`, enlaza al index con `details`

---

### Paso 4: Import de agents/

Para cada `*.md` en `agents/` recursivo:
- `kind='agent-note'`
- Slug: `agent-{path_relativo_slugified}`
- `source_kind='legacy-agents'`
- Enlaza al index con `contains`

---

### Paso 5: Import de docs/

Archivos en `docs/` → nodos `kind='doc'` o `kind='reference'`. Excluye `docs/db-export/`.

---

### Paso 6: Import de projects/

Para cada directorio en `projects/`:
1. Busca info: `info.md`, `README.md`, o `00-index.md`
2. Crea nodo `kind='project'`, slug `project-{name}`
3. Enlaza al index con `project_of`
4. Archivos `.md` internos → nodos `doc` hijos con `contains`
5. Archivos no-MD → movidos a `code/{project_name}/`

---

### Paso 7: Import de scripts/

- `.md` en scripts/ → nodos `kind='script'`, `source_kind='legacy-scripts'`
- Otros archivos → movidos a `code/scripts/`

---

### Paso 8: Mover Código a code/

Archivos no-MD de projects/scripts se mueven a `code/`.

---

### Paso 9: Verificación

```python
verification = store.verify_db_completeness()
# Verifica: node_count > 0, index_count > 0, body_count > 0
```

---

### Paso 10: Limpieza (opcional)

Si `remove_legacy=True` Y `verified=True`: borra originals.
Si `verified=False`: no borra nada, registra `legacy_migration_failed`.

---

## 4. Método: migrate_from_markdown

Solo importa desde `context/` y `projects/` (no toca agents/docs/scripts):

```python
def migrate_from_markdown(self, *, force: bool = False) -> dict
```

---

## 5. Bootstrap de Workspace Nuevo

```python
def seed_workspace(self, description: str, areas: Iterable[str]) -> dict
```

1. Crea nodo `index` con descripción
2. Crea un nodo `topic` por cada área
3. Enlaza topics al index con `details`
4. Escanea artifacts en `code/`
5. Genera `workspace-doc.md` y `CLAUDE.md`

---

## 6. Scripts Relacionados

### create-workspace.py

```bash
# Crear workspace nuevo
python3 ~/.laia/scripts/create-workspace.py --name mi-workspace --bootstrap "Descripción"

# Migrar estructura legacy
python3 ~/.laia/scripts/create-workspace.py --name mi-workspace --migrate-legacy

# Reparar workspace
python3 ~/.laia/scripts/create-workspace.py --name mi-workspace --repair
```

### health-check.py

Verifica que migración está completa.

---

## 7. Estructura Post-Migración

```
workspace/
├── workspace.db          # Fuente de verdad
├── code/                 # Código (migrado o nuevo)
│   ├── scripts/
│   └── {projects}/
├── context/              # [vacío o regenerado bajo demanda]
├── docs/
│   └── db-export/        # [vacío o regenerado bajo demanda]
└── (legacy paths)         # [eliminados tras verificación]
```

---

## 8. Notas sobre Backups

- Ubicación: `~/.laia/backups/legacy-workspaces/`
- Formato: `workspace-YYYYMMDDTHHMMSSZ.tar.gz`
- Se crean ANTES de cualquier modificación
- Nunca se borran automáticamente

---

## 9. Casos de Fallo

| Problema | Comportamiento |
|----------|----------------|
| DB ya tiene nodos | `migrate_from_markdown` refuse `force=False` |
| Verificación fails | No borra legacy, registra `failed` |
| Archivo destino ya existe | Skip (no sobreescribe) |
| Path no existe | Omite silenciosamente |


> 📅 Documentado: 2026-05-08
