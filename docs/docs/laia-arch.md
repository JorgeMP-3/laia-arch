# LAIA Arch — Hermes y Workspace-UI

## Estructura de directorios

```
~/laia-arch/              ← repo git: github.com/JorgeMP-3/laia-infra (rama: main)
  ├── hermes-agent/       ← repo git independiente (tiene su propio .git)
  ├── workspace-ui/       ← repo git independiente (tiene su propio .git)
  ├── hermes-config/      ← skills, memorias, scripts (sincronizado por gsave)
  ├── bin/                ← scripts (gsave, clone-laia, etc.)
  ├── dotfiles/           ← starship.toml
  └── SOUL.md

~/.hermes/                ← runtime de Hermes (NO en git)
  ├── hermes-agent → ~/laia-arch/hermes-agent  (symlink)
  ├── workspace-ui → ~/laia-arch/workspace-ui  (symlink)
  ├── auth.json           ← credenciales (secreto)
  ├── config.yaml         ← configuración principal
  ├── state.db            ← base de datos de estado
  ├── memories/           ← memorias de Hermes
  ├── skills/             ← skills instalados
  └── sessions/           ← sesiones activas

~/bin/                    ← scripts del sistema
  ├── gsave               ← guardar proyectos en GitHub
  ├── clone-laia          ← clonar el stack completo en una máquina nueva
  ├── hermes-start        ← arrancar hermes + workspace-ui manualmente
  └── sclaude             ← wrapper de Claude

~/servidor/               ← configuración del servidor
  ├── arete/              ← código fuente de Arete
  ├── tienda/             ← docker-compose de WordPress
  └── nginx/              ← config nginx (fuente de verdad)
```

---

## Repos en GitHub

| Repo local | GitHub | Rama activa |
|---|---|---|
| `~/laia-arch/` | JorgeMP-3/laia-infra | main |
| `~/laia-arch/hermes-agent/` | JorgeMP-3/hermes-agent | local-customizations |
| `~/laia-arch/workspace-ui/` | JorgeMP-3/workspace-ui | master |

### Remotes de hermes-agent

```
origin   → https://github.com/JorgeMP-3/hermes-agent.git   (fork propio)
upstream → https://github.com/NousResearch/hermes-agent.git (fuente oficial)
```

Para recibir actualizaciones de NousResearch:
```bash
cd ~/laia-arch/hermes-agent
git fetch upstream
git checkout main && git merge upstream/main
git push origin main
git checkout local-customizations && git rebase main
git push origin local-customizations --force-with-lease
```

---

## Hermes Gateway

**Servicio:** `/etc/systemd/system/hermes.service`  
**Binario:** `~/laia-arch/hermes-agent/venv/bin/hermes`  
**Versión:** Laia Arch v0.11.0 (2026.4.23)  
**Python:** 3.12.3  

```bash
sudo systemctl status hermes
sudo systemctl restart hermes
journalctl -u hermes -f
```

El venv está en `~/laia-arch/hermes-agent/venv/`.  
Si se pierde el venv (e.g. tras un `git clean`):
```bash
cd ~/laia-arch/hermes-agent
python3 -m venv venv
source venv/bin/activate
pip install -e .
pip install -r ~/laia-arch/workspace-ui/backend/requirements.txt
```

---

## Workspace-UI

**Servicio:** `/etc/systemd/system/workspace-ui.service`  
**Framework:** FastAPI + uvicorn  
**Puerto:** 8077  
**Working dir:** `~/laia-arch/workspace-ui/backend/`  
**Binario uvicorn:** `~/laia-arch/hermes-agent/venv/bin/uvicorn`

```bash
sudo systemctl status workspace-ui
sudo systemctl restart workspace-ui
curl http://localhost:8077/
```

Acceso local directo: http://localhost:8077  
No está expuesto en internet (nginx no tiene regla para workspace-ui).

---

## gsave — Guardar cambios en GitHub

Script en `~/bin/gsave` (zsh). Guarda los tres proyectos:

```bash
gsave   # lanza menú interactivo
```

Opciones:
- `1` — workspace-ui → origin/master
- `2` — hermes-agent → origin/local-customizations
- `3` — los dos + sincroniza laia-infra
- `q` — salir

El script sincroniza skills, memorias y scripts desde `~/.hermes/` a `~/laia-arch/hermes-config/` antes de commitear laia-infra.

---

## Starship (prompt)

Config en: `~/.config/starship.toml` (copiada de `~/laia-arch/dotfiles/starship.toml`)  
Inicializado en `~/.bashrc`: `eval "$(starship init bash)"`
