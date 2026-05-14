---
name: workspace-git
description: "Gestiona git y GitHub para los workspaces LAIA: estado, init, push, pull y configuración de repos."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [git, GitHub, workspaces, LAIA, sync, repos]
    related_skills: [github-auth, github-repo-management]
---

# Workspace Git Manager

Gestión completa de git y GitHub para los workspaces LAIA en `~/LAIA/workspaces/`.

## Archivos clave

| Archivo | Descripción |
|---------|-------------|
| `~/LAIA/scripts/git-manager.py` | Módulo Python + CLI + TUI |
| `~/LAIA/scripts/git-manager-web.py` | Web UI en Flask (puerto 5055) |
| `workspace.db → workspace_meta` | Config persistente por workspace (`git.github_repo`, etc.) |

## Reglas importantes

- **`laia-arch` está excluido** — su código vive en `/home/laia-arch/LAIA` directamente, no en `workspaces/laia-arch/code/`. Nunca ejecutes operaciones git sobre él desde este gestor.
- La config de GitHub (nombre del repo, visibilidad) se guarda en `workspace_meta` de cada `workspace.db`.
- Requiere `gh` CLI autenticado para crear repos o hacer push.

## Uso como módulo Python (recomendado para agentes)

```python
import sys
sys.path.insert(0, '/home/laia-arch/LAIA/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location(
    "git_manager",
    "/home/laia-arch/LAIA/scripts/git-manager.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
WorkspaceGitManager = mod.WorkspaceGitManager

mgr = WorkspaceGitManager()
```

## Operaciones principales

### Ver estado de todos los workspaces

```python
workspaces = mgr.list_all()
for ws in workspaces:
    if ws['excluded']:
        continue  # laia-arch — ignorar
    print(f"{ws['workspace']}: {ws['topology']} — {len(ws['repos'])} repos")
```

Topologías posibles: `none` (sin git) · `root` (code/.git) · `subprojects` (subdirs con .git) · `mixed`

### Ver estado de un workspace concreto

```python
status = mgr.get_status("arete")
# {
#   "ok": True,
#   "workspace": "arete",
#   "topology": "subprojects",
#   "repos": [
#     {
#       "name": "Arete",
#       "rel_path": "code/Arete/",
#       "git": {
#         "branch": "main", "clean": False,
#         "staged": 1, "unstaged": 6, "untracked": 2,
#         "has_remote": False, "ahead": 0, "behind": 0
#       },
#       "github_repo": "Arete",
#       "visibility": "private",
#       "last_sync": None
#     }
#   ]
# }
```

### Inicializar git en un workspace sin git

```python
result = mgr.init_git("servidor-jmp")
# Inicializa code/ con git init, .gitignore y commit inicial
# Si ya existe git, no hace nada (idempotente)
```

### Configurar nombre del repo en GitHub

```python
# Cambiar nombre del repo antes de hacer push por primera vez
result = mgr.configure_repo(
    "arete",
    repo_name="proyecto-arete-ios",   # nombre en GitHub
    visibility="private",              # "private" | "public"
    target_repo="Arete"               # subproyecto específico (si hay varios)
)
```

Claves guardadas en `workspace_meta`:
- `git.github_repo` — nombre global del workspace
- `git.github_repo.Arete` — nombre para el subproyecto "Arete"
- `git.visibility` / `git.visibility.Arete`
- `git.remote_url` / `git.remote_url.Arete`
- `git.last_sync` / `git.last_sync.Arete`

### Push a GitHub

```python
# Push de todos los repos del workspace
result = mgr.push_to_github("arete")

# Push solo de un subproyecto específico
result = mgr.push_to_github("arete", target_repo_name="Arete")

# Push con mensaje de commit personalizado
result = mgr.push_to_github("arete", commit_message="feat: nueva funcionalidad")

# Resultado:
# {
#   "ok": True,
#   "message": "Push completado: 1/1 repos",
#   "repos": [{"ok": True, "name": "Arete", "action": "pushed"}]
# }
```

El push:
1. Hace `git add -A && git commit` si hay cambios pendientes
2. Asegura que la rama se llama `main` (renombra `master` si es necesario)
3. Si no hay remote: crea el repo en GitHub (privado por defecto) y conecta el remote
4. Hace `git push -u origin main`
5. Guarda timestamp en `git.last_sync`

### Pull desde GitHub

```python
result = mgr.pull_from_github("arete")
result = mgr.pull_from_github("arete", target_repo_name="Arete")
```

## Uso como CLI (desde terminal)

```bash
# Estado de todos los workspaces (JSON)
python3 ~/LAIA/scripts/git-manager.py --list

# Estado de un workspace
python3 ~/LAIA/scripts/git-manager.py --status arete

# Init git
python3 ~/LAIA/scripts/git-manager.py --init servidor-jmp

# Push
python3 ~/LAIA/scripts/git-manager.py --push arete
python3 ~/LAIA/scripts/git-manager.py --push arete --message "feat: nueva feature"
python3 ~/LAIA/scripts/git-manager.py --push arete --target-repo Arete

# Configurar
python3 ~/LAIA/scripts/git-manager.py --configure arete \
    --repo-name "proyecto-arete-ios" \
    --visibility private

# TUI interactiva
python3 ~/LAIA/scripts/git-manager.py
```

## Web UI

La web UI está disponible en `http://100.95.125.76:5055` (accesible desde la VPN Tailscale).

Para levantarla:
```bash
python3 ~/LAIA/scripts/git-manager-web.py --host 0.0.0.0 --port 5055
```

La web UI permite:
- Ver tabla de todos los workspaces con estado, repos y último sync
- Init git, push, pull y configurar repos con formularios visuales
- Logs en tiempo real durante el push (Server-Sent Events)

## Flujo típico para un workspace nuevo

```python
# 1. Verificar estado
status = mgr.get_status("doyouwin")
# → topology: "none"

# 2. Inicializar git
mgr.init_git("doyouwin")

# 3. Configurar nombre del repo en GitHub (opcional, default = nombre del workspace)
mgr.configure_repo("doyouwin", repo_name="doyouwin-app", visibility="private")

# 4. Push (crea el repo en GitHub automáticamente si no existe)
mgr.push_to_github("doyouwin", commit_message="feat: initial commit")
```

## Manejo de errores

Todos los métodos devuelven `{"ok": bool, "message": str, ...}`. Nunca lanzan excepciones al llamante.

```python
result = mgr.push_to_github("arete")
if not result["ok"]:
    print(f"Error: {result['message']}")
    # Causas comunes:
    # - "gh CLI no autenticado" → ejecutar: gh auth login
    # - "No hay repos git" → ejecutar: mgr.init_git("arete")
    # - Error de red o permisos de GitHub
```
