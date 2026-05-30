# `.github/workflows/` — CI de LAIA-ARCH

CI de integración continua para `JorgeMP-3/laia-arch`. Nació en el **Track B ·
slice B1** (Robustez/Ops): hasta entonces la suite solo se corría a mano y no
había nada que protegiera `main` en cada PR.

## `ci.yml`

**Disparador:** cada `pull_request` contra `main` (+ `workflow_dispatch` manual).
**Permisos:** `contents: read` (sin secrets, sin escritura). **Concurrencia:** un
PR con varios pushes seguidos cancela los runs anteriores.

### Qué corre (matriz de cobertura — *no silent cap*)

| Job | Qué ejecuta | Entorno | Estado verificado en local |
|---|---|---|---|
| `backend` (py3.11) | `pytest tests/` en `services/agora-backend` | `requirements.txt` + `pytest`, sin DB ni servicios (los aísla `conftest.py`) | 355 passed, 8 skipped |
| `backend` (py3.14) | idem, en la versión del dev | idem | 355 passed, 8 skipped |
| `installer` | `tests/installer/run_all.sh` | host-free (stubs de `lxc`/`lxd`/`snap`/`curl`) | 33/33, exit 0 |
| `skip-matrix` | imprime esta matriz como anotaciones del PR | — | informativo |

**Por qué la matriz de Python `3.11` + `3.14`:** `3.11` es el *floor* del proyecto
(`infra/installer/lib/install.sh` → `require_python_min 3.11`); `3.14` es la que
corre el dev. Probar el floor evita el clásico "funciona en mi máquina (3.14)
pero rompe en la mínima soportada". `fail-fast: false` para ver ambas aunque una
falle.

> Nota sobre los tests del installer: están diseñados para correr **sin root, sin
> LXD y sin GitHub** (ver `tests/installer/README.md`). En un *git worktree* fallan
> 4 (`test_flags`, `test_release_e2e`, `test_rollback`,
> `test_release_prune_and_auto_rollback`) porque `release.sh` exige que `.git` sea
> un **directorio** y en un worktree es un fichero. En CI no aplica: `actions/checkout`
> deja un `.git` normal → los 33 pasan.

### Qué NO corre, y por qué (skips por diseño)

Estos no son fallos silenciados: el job `skip-matrix` los reimprime como
anotaciones en cada PR, y aquí queda la razón.

| Suite | Por qué no en CI | Dónde se cubre |
|---|---|---|
| **D2** — `tests/integration/test_ecosystem_integrity.sh` | Requiere LXD + container `laia-agora` vivo + `/api/health` + `agora.db` real. Un runner de GitHub no tiene host LAIA. | A mano y en la VM `laia-dev`; en caliente vía el **monitor B2** (slice siguiente). |
| `tests/*.sh` top-level (`test_preflight.sh`, `test_smoke_scripts.sh`, `test_rebuild_state.sh`, …) | Fuera del alcance de B1; varios asumen host/servicios LAIA. | Manual / VM. **Candidatos a ampliación futura del CI** si se confirma que son host-free. |
| `tests/wizard/*.py` | Fuera del alcance de B1. | Manual / VM E2E. **Candidato claro a futura ampliación** (es pytest puro). |
| `tests/installer/vm-*.sh` (`vm-smoke.sh`, `vm-wizard-e2e.sh`) | No son `test_*.sh` → `run_all.sh` no los recoge; necesitan VM Multipass. | Fase E / VM. |

### Cómo reproducir el CI en local

```bash
# Backend (igual que el job, en el floor):
cd services/agora-backend
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests/ -q

# Installer host-free (igual que el job):
bash tests/installer/run_all.sh
```

### Ampliar el CI más adelante

Candidatos naturales para sumar (cuando se valide que corren host-free): la suite
`tests/wizard/*.py` y los `tests/*.py` top-level (`test_atlas.py`,
`test_clone_config_rewrite.py`, `test_plugin_extra_dirs.py`). Al añadir un job,
actualizar **esta tabla** y el job `skip-matrix` para no reintroducir un silent cap.
