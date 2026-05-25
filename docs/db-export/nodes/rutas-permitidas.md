# Rutas permitidas en AGORA

## Metadata

- ID: `53`
- Slug: `rutas-permitidas`
- Kind: `doc`
- Status: `active`
- Filename: `rutas-permitidas.md`
- Parent: `seguridad`
- Source kind: `manual`
- Created at: `2026-05-08T08:04:28.992548+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `rutas-permitidas`

## Summary

Rutas del filesystem accesibles y protegidas

## Body

# Rutas permitidas en AGORA

## Lo que AGORA puede leer
- ~/LAIA/workspaces/{su_workspace}/ — su propio workspace
- ~/LAIA/laia-agora/ — código de AGORA
- Directorios propios del empleado

## Lo que AGORA NO puede leer
- ~/.laia/ — config, auth, state (sensible)
- ~/servidor/ — configs de producción
- ~/.laia-arch/ — herramientas internas de administración
- ~/LAIA/workspaces/{otro_workspace}/ — workspaces de otros

## Filesystem editable
El filesystem editable del usuario vive bajo /opt/data/

## Path traversal protection
```python
def _sanitize_rel_path(rel_path):
    rel_path = rel_path.strip().strip("/")
    if not rel_path or rel_path.startswith("/") or ".." in Path(rel_path).parts:
        return None
    return rel_path
```


## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `seguridad` (Seguridad y aislamiento) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Rutas permitidas en AGORA

# Rutas permitidas en AGORA

## Lo que AGORA puede leer
- ~/LAIA/workspaces/{su_workspace}/ — su propio workspace
- ~/LAIA/laia-agora/ — código de AGORA
- Directorios propios del empleado

## Lo que AGORA NO puede leer
- ~/.laia/ — config, auth, state (sensible)
- ~/servidor/ — configs de producción
- ~/.laia-arch/ — herramientas internas de administración
- ~/LAIA/workspaces/{otro_workspace}/ — workspaces de otros

## Filesystem editable
El filesystem editable del usuario vive bajo /opt/data/

## Path traversal protection
```python
def _sanitize_rel_path(rel_path):
    rel_path = rel_path.strip().strip("/")
    if not rel_path or rel_path.startswith("/") or ".." in Path(rel_path).parts:
        return None
    return rel_path
```
