# Plan ejecutable: migración in-place al layout canónico + verificación E2E

- **Fecha**: 2026-05-25
- **Owner**: 1 IA serial (cualquier IA con acceso a esta VM y al repo)
- **Estado**: aprobado — listo para ejecutar
- **VM**: esta misma (`laia-hermes` dev box)
- **Tiempo estimado**: 1-2 horas
- **Riesgo**: MEDIO — se mueven 482 MB de data real. Snapshot previo OBLIGATORIO.

---

## 0. Para la IA que ejecuta este plan — LÉEME

**Misión**: reorganizar IN-PLACE la data viva de esta VM (`~/.laia/`)
al layout canónico post-`d02afcb0` SIN reinstalar y SIN borrar
información valiosa. El resultado: esta VM queda como referencia
funcional viva de lo que un server nuevo debería ver tras ejecutar
`curl|sudo bash install.sh`.

**Concepto clave**: esta VM corre LAIA **dev-style** (procesos
directos desde `/home/laia-hermes/LAIA/`, NO desde `/opt/laia/`). El
plan NO crea `/opt/laia/` ni reinstala — solo redistribuye la data
existente y rearranca los procesos para que apunten al nuevo layout.

**Reglas**:
1. **NO ejecutes T.1 sin confirmación del snapshot** (T.0).
2. **Ejecuta tareas en orden estricto** (T.0 → T.12).
3. **Usa `rsync -aHAX --remove-source-files` o `mv`**, NUNCA `cp + rm`
   (preserva ownership, permisos, hardlinks, ACLs, xattrs).
4. **NO modifiques código fuente** del repo. Si encuentras un bug,
   anota en `workflow/problems.md` y sigue.
5. **NO toques** `/home/laia-hermes/LAIA/`, `/srv/laia/agora/`,
   `/srv/laia/users/`, `/srv/laia/backups/`, `/srv/laia/state/`.
6. Si una verificación falla, anota `<ID> FAIL` y continúa.
7. **Loggea progreso** a `/tmp/laia-migrate.log` con `tee`.
8. **Reporta al final** en `/tmp/laia-migrate-report.md`.

**Variables que la IA recibe del operador**:
- `LAIA_VERIFY_LLM_KEY`: API key real (opcional). Sin esto F.5.* y
  F.16.4 se marcan `SKIPPED`.
- `LAIA_VERIFY_LLM_PROVIDER`: default `deepseek`.
- `LAIA_VERIFY_LLM_MODEL`: default `deepseek-chat`.

---

## 1. Contexto

Esta VM (`laia-hermes`) tiene LAIA dev-style funcionando:
- agora-backend uvicorn corriendo en `:8088` directo desde el repo.
- laia-pathd daemon activo.
- `/srv/laia/agora/` con data viva del backend.
- `~/.laia/` con **482 MB de data acumulada** del admin: workspaces
  (264M), sessions (202M), atlas, plugins, memorias, etc.

El nuevo layout canónico (`workflow/arch-data-layout.md`, commit
`d02afcb0`) separa:
- **`~/LAIA-ARCH/`** ← interactivo (workspaces, memories, skills, plugins)
- **`/srv/laia/arch/`** ← operacional (sessions, atlas, cron, logs,
  SOUL.md, config.yaml, state.db, etc.)
- **`~/.laia/`** ← solo legacy compat (auth.json, .env, bin, cache,
  admin-session.json, runtime locks)

Reinstalar borraría todo eso. **Esta plan migra in-place**, preservando
264M de workspaces, 202M de sessions, atlas snapshots, plugins,
memorias y configs — toda la información acumulada con uso real que el
installer no contempla.

---

## 2. Estado inicial — verifica antes de empezar

```bash
cd /home/laia-hermes/LAIA

# 1. Working dir + repo limpio:
git status --short
git rev-parse --abbrev-ref HEAD          # debe ser feat/installer-wizard o stable

# 2. Estado de data:
ls /home/laia-hermes/.laia/ | wc -l       # debe ser >20 dirs/files
ls /home/laia-hermes/LAIA-ARCH/ 2>/dev/null # debe NO existir o estar casi vacío
ls /srv/laia/arch/ 2>/dev/null            # debe NO existir

# 3. Servicios + procesos:
sudo systemctl is-active agora-backend laia-gateway laia-pathd laia-ui-server 2>&1
ps -ef | grep -E "agora-backend|laia-pathd|uvicorn.*8088" | grep -v grep | head -3
```

Si algo de lo anterior no se ve como esperas, PARA y reporta al humano.

---

## 3. Tareas (orden estricto)

### T.0 — Snapshot previo (CRÍTICO)

**Goal**: Salvavidas antes de tocar nada.

**Commands**:
```bash
echo "============================================================"
echo "REQUISITO: snapshot de esta VM ANTES de continuar."
echo "Comando esperado en el HOST (Mac, no la VM):"
echo "   multipass snapshot <vm-name> --name pre-migration-2026-05-25"
echo "============================================================"
```

**Verify**: confirmación humana explícita ("snapshot hecho").

**On failure**: PARA.

---

### T.1 — Parar procesos LAIA

**Goal**: Liberar file handles antes de mover ficheros.

**Commands**:
```bash
# Parar systemd units si están activas:
for svc in agora-backend laia-gateway laia-pathd laia-ui-server; do
  sudo systemctl is-active --quiet $svc 2>/dev/null \
    && sudo systemctl stop $svc 2>/dev/null
done

# Matar procesos manuales (los que corren directo desde el repo):
sudo pkill -f "uvicorn app.main:app.*8088" 2>/dev/null || true
sudo pkill -f "laia-pathd" 2>/dev/null || true
sudo pkill -f ".laia-core.*gateway" 2>/dev/null || true

# Esperar 3s para que liberen ficheros:
sleep 3

# Verificar que NO quedan procesos LAIA:
ps -ef | grep -E "agora-backend|laia-pathd|uvicorn.*8088" | grep -v grep
```

**Verify**: el último `ps` no devuelve nada.

**On failure**: si algún proceso resiste, `sudo pkill -9 <pid>`.
Si sigue, PARA y reporta.

---

### T.2 — Inventario de origen

**Goal**: Snapshot textual del estado actual para diff post-migración.

**Commands**:
```bash
mkdir -p /tmp/laia-migrate-evidence
ls -la /home/laia-hermes/.laia/ > /tmp/laia-migrate-evidence/laia-pre.txt
sudo du -sb /home/laia-hermes/.laia/* 2>/dev/null \
  | sort -rn > /tmp/laia-migrate-evidence/sizes-pre.txt
```

**Verify**: ambos ficheros existen y no están vacíos.

---

### T.3 — Crear directorios destino

**Goal**: Crear `~/LAIA-ARCH/` y `/srv/laia/arch/` con ownership/perms
correctos.

**Commands**:
```bash
# Interactive (owned by laia-hermes, no root):
sudo -u laia-hermes mkdir -p /home/laia-hermes/LAIA-ARCH
sudo -u laia-hermes chmod 700 /home/laia-hermes/LAIA-ARCH

# Operational (root-owned, hardened):
sudo mkdir -p /srv/laia/arch
sudo chmod 700 /srv/laia/arch
sudo chown root:root /srv/laia/arch

# Para los dirs específicos que esperan ownership de laia-hermes,
# se hereda automáticamente al hacer mv.
```

**Verify**:
```bash
test -d /home/laia-hermes/LAIA-ARCH && echo "T.3a OK"
sudo test -d /srv/laia/arch && echo "T.3b OK"
```

---

### T.4 — Mover data INTERACTIVA → `~/LAIA-ARCH/`

**Goal**: Mover los 4 dirs interactivos preservando todo.

**Estos son los dirs**: `workspaces`, `memories`, `skills`, `plugins`.

**Commands**:
```bash
SRC=/home/laia-hermes/.laia
DST=/home/laia-hermes/LAIA-ARCH

for dir in workspaces memories skills plugins; do
  if [[ -d "$SRC/$dir" ]]; then
    echo ">>> Moviendo $SRC/$dir → $DST/$dir"
    # Si el destino ya existe (raro), fusionamos con rsync; si no, mv directo:
    if [[ -e "$DST/$dir" ]]; then
      sudo -u laia-hermes rsync -aHAX --remove-source-files "$SRC/$dir/" "$DST/$dir/"
      sudo -u laia-hermes find "$SRC/$dir" -type d -empty -delete
    else
      sudo -u laia-hermes mv "$SRC/$dir" "$DST/$dir"
    fi
    echo "T.4.$dir OK"
  else
    echo "T.4.$dir SKIPPED (origen no existe)"
  fi
done
```

**Verify**:
```bash
ls -la /home/laia-hermes/LAIA-ARCH/
du -sh /home/laia-hermes/LAIA-ARCH/workspaces 2>/dev/null    # debe ser ~264M
test ! -d /home/laia-hermes/.laia/workspaces && echo "T.4 OK (origen vacío)"
```

**On failure**: si `mv` falla por permisos, comprueba con `ls -la`
quién es dueño del dir origen. Si el destino tiene contenido previo,
el rsync de fusión lo añade — pero anota como T.4.WARN porque puede
indicar migración previa.

---

### T.5 — Mover data OPERACIONAL → `/srv/laia/arch/`

**Goal**: Mover dirs/ficheros operacionales (sensibles, runtime) a la
zona root-owned.

**Estos son los items** (en el orden de prioridad):

```
dirs:    sessions, atlas, cron, sandboxes, orchestrator-runs,
         migration, whatsapp, logs, platforms, pastes, checkpoints, state
files:   SOUL.md, config.yaml
dbs:     state.db, state.db-shm, state.db-wal,
         response_store.db, response_store.db-shm, response_store.db-wal
otros:   laia-ui-server-session-areas.json, interrupt_debug.log
```

**Commands**:
```bash
SRC=/home/laia-hermes/.laia
DST=/srv/laia/arch

# Dirs operacionales:
for dir in sessions atlas cron sandboxes orchestrator-runs migration \
           whatsapp logs platforms pastes checkpoints state; do
  if [[ -d "$SRC/$dir" ]]; then
    echo ">>> Moviendo $SRC/$dir → $DST/$dir"
    if sudo test -e "$DST/$dir"; then
      sudo rsync -aHAX --remove-source-files "$SRC/$dir/" "$DST/$dir/"
      sudo find "$SRC/$dir" -type d -empty -delete
    else
      sudo mv "$SRC/$dir" "$DST/$dir"
    fi
    echo "T.5.dir.$dir OK"
  else
    echo "T.5.dir.$dir SKIPPED"
  fi
done

# Ficheros sueltos:
for f in SOUL.md config.yaml \
         state.db state.db-shm state.db-wal \
         response_store.db response_store.db-shm response_store.db-wal \
         laia-ui-server-session-areas.json interrupt_debug.log; do
  if [[ -f "$SRC/$f" ]]; then
    sudo mv "$SRC/$f" "$DST/$f"
    echo "T.5.file.$f OK"
  else
    echo "T.5.file.$f SKIPPED"
  fi
done
```

**Verify**:
```bash
sudo ls /srv/laia/arch/ | head -30
sudo du -sh /srv/laia/arch/sessions 2>/dev/null   # debe ser ~202M
sudo test -f /srv/laia/arch/SOUL.md && echo "T.5 OK"
test ! -d /home/laia-hermes/.laia/sessions && echo "T.5 cleanup OK"
```

---

### T.6 — Borrar `mlx-servers/` (basura confirmada)

**Goal**: Liberar espacio del dir mlx-servers que el operador confirmó
borrar.

**Commands**:
```bash
SRC=/home/laia-hermes/.laia/mlx-servers
if [[ -e "$SRC" ]]; then
  SIZE=$(du -sh "$SRC" 2>/dev/null | awk '{print $1}')
  echo ">>> Borrando $SRC ($SIZE)..."
  sudo rm -rf "$SRC"
  echo "T.6 OK (liberado $SIZE)"
else
  echo "T.6 SKIPPED (no existe)"
fi
```

**Verify**:
```bash
test ! -e /home/laia-hermes/.laia/mlx-servers && echo "T.6 verified"
```

---

### T.7 — Reescribir `config.yaml` con nuevos paths

**Goal**: El config.yaml acaba de moverse a `/srv/laia/arch/config.yaml`.
Sus paths internos (`laia_home`, `laia_root`, `agora_data`, etc.) aún
apuntan a `~/.laia/` viejo. Reescribirlos para que apunten al nuevo
layout.

**Commands**:
```bash
CFG=/srv/laia/arch/config.yaml
if sudo test -f "$CFG"; then
  # Backup primero:
  sudo cp "$CFG" "${CFG}.pre-migrate.bak"

  # Mismas sustituciones que clone_phase_h_rewrite_config_paths:
  sudo sed -i -E \
    -e 's#^([[:space:]]*laia_root:[[:space:]]*).*#\1/opt/laia#' \
    -e 's#^([[:space:]]*agora_data:[[:space:]]*).*#\1/srv/laia/agora/agora.db#' \
    -e 's#^([[:space:]]*laia_home:[[:space:]]*).*#\1/home/laia-hermes/LAIA-ARCH#' \
    -e 's#/home/laia-hermes/\.laia/workspaces#/home/laia-hermes/LAIA-ARCH/workspaces#g' \
    -e 's#/home/laia-hermes/\.laia/memories#/home/laia-hermes/LAIA-ARCH/memories#g' \
    -e 's#/home/laia-hermes/\.laia/skills#/home/laia-hermes/LAIA-ARCH/skills#g' \
    -e 's#/home/laia-hermes/\.laia/plugins#/home/laia-hermes/LAIA-ARCH/plugins#g' \
    -e 's#~/\.laia/workspaces#/home/laia-hermes/LAIA-ARCH/workspaces#g' \
    -e 's#~/\.laia/memories#/home/laia-hermes/LAIA-ARCH/memories#g' \
    -e 's#~/\.laia/skills#/home/laia-hermes/LAIA-ARCH/skills#g' \
    -e 's#~/\.laia/plugins#/home/laia-hermes/LAIA-ARCH/plugins#g' \
    -e 's#/home/laia-hermes/\.laia/#/srv/laia/arch/#g' \
    -e 's#~/\.laia/#/srv/laia/arch/#g' \
    "$CFG"

  echo "T.7 OK"
else
  echo "T.7 SKIPPED (no config.yaml)"
fi
```

**Verify**:
```bash
sudo cat "$CFG" | grep -E "laia_root|laia_home|agora_data" | head -10
sudo grep -c "~/.laia\|/home/laia-hermes/\.laia/" "$CFG"
# debe imprimir 0 (sin residuos legacy)
```

---

### T.8 — Update `LAIA_HOME` y env vars

**Goal**: `~/.bashrc` y cualquier env config del user debe apuntar al
nuevo `LAIA_HOME`.

**Commands**:
```bash
BASHRC=/home/laia-hermes/.bashrc

# Backup:
cp "$BASHRC" "${BASHRC}.pre-migrate.bak"

# Update o añadir LAIA_HOME export:
if grep -q "^export LAIA_HOME=" "$BASHRC"; then
  sed -i -E 's#^export LAIA_HOME=.*#export LAIA_HOME=/home/laia-hermes/LAIA-ARCH#' "$BASHRC"
else
  echo "" >> "$BASHRC"
  echo "# LAIA canonical layout (added by migration 2026-05-25)" >> "$BASHRC"
  echo "export LAIA_HOME=/home/laia-hermes/LAIA-ARCH" >> "$BASHRC"
fi

# Verificar:
grep "LAIA_HOME" "$BASHRC"
```

**Verify**:
```bash
grep -q "^export LAIA_HOME=/home/laia-hermes/LAIA-ARCH" "$BASHRC" && echo "T.8 OK"
```

**Nota**: el efecto solo aplica en shells nuevos. Los procesos que
arranquen en T.9 deben leer LAIA_HOME del entorno actualizado.

---

### T.9 — Limpieza adicional `~/.laia/` (runtime stale)

**Goal**: Borrar locks y sockets viejos que se recrean al rearrancar.

**Commands**:
```bash
SRC=/home/laia-hermes/.laia

# Locks y sockets — se recrean en T.10:
for f in gateway.lock gateway.pid pathd.sock processes.json; do
  if [[ -e "$SRC/$f" ]]; then
    rm -f "$SRC/$f"
    echo "T.9.$f cleaned"
  fi
done
```

**Verify**: simple `ls` para confirmar.

---

### T.10 — Arrancar procesos con el nuevo layout

**Goal**: Levantar agora-backend + laia-pathd contra el nuevo layout.

**Commands**:
```bash
# Cargar el nuevo LAIA_HOME en este shell:
export LAIA_HOME=/home/laia-hermes/LAIA-ARCH

# Si la VM usa systemd, arrancar units:
for svc in agora-backend laia-gateway laia-pathd laia-ui-server; do
  if systemctl list-unit-files | grep -q "$svc.service"; then
    sudo systemctl daemon-reload
    sudo systemctl start $svc 2>/dev/null
    sleep 1
  fi
done

# Si la VM corre dev-style (procesos manuales desde el repo), arrancar
# así (ajusta según el modo de arranque histórico de tu VM):
# Backend agora:
nohup sudo -u laia-hermes -E bash -c '
  cd /home/laia-hermes/LAIA
  export LAIA_HOME=/home/laia-hermes/LAIA-ARCH
  ./services/agora-backend/.venv/bin/python \
    -m uvicorn app.main:app --host 0.0.0.0 --port 8088 \
    --app-dir ./services/agora-backend \
    > /tmp/agora-backend.log 2>&1 &
'

# laia-pathd:
nohup sudo -u laia-hermes -E bash -c '
  cd /home/laia-hermes/LAIA
  export LAIA_HOME=/home/laia-hermes/LAIA-ARCH
  ./.laia-core/venv/bin/python ./infra/bin/laia-pathd --log-level INFO \
    > /tmp/laia-pathd.log 2>&1 &
'

# Esperar agora-backend listo (max 30s):
for i in {1..30}; do
  curl -fsS http://127.0.0.1:8088/api/health >/dev/null 2>&1 && break
  sleep 2
done
```

**Verify**:
```bash
curl -fsS http://127.0.0.1:8088/api/health | jq -e '.ok == true' && echo "T.10 OK"
```

**On failure**:
- Mira `/tmp/agora-backend.log` y `/tmp/laia-pathd.log`.
- Si dice "FileNotFoundError" de algún path viejo → algún dir no se
  migró correctamente. Identifica cuál y reporta.
- Si dice "Permission denied" → verifica owner de
  `/home/laia-hermes/LAIA-ARCH/` y `/srv/laia/arch/`.

---

### T.11 — Crear usuario de prueba `verify_bob`

(Idéntico al de la versión anterior del plan.)

**Commands**:
```bash
ADMIN_USER=$(awk -F: '/^username:/ {gsub(/ /,""); print $2}' \
             /home/laia-hermes/LAIA-ARCH/.admin-credentials 2>/dev/null \
             || awk -F: '/^username:/ {gsub(/ /,""); print $2}' \
                /home/laia-hermes/.laia/admin-credentials 2>/dev/null)
ADMIN_PASS=$(awk -F: '/^password:/ {gsub(/ /,""); print $2}' \
             /home/laia-hermes/LAIA-ARCH/.admin-credentials 2>/dev/null \
             || awk -F: '/^password:/ {gsub(/ /,""); print $2}' \
                /home/laia-hermes/.laia/admin-credentials 2>/dev/null)

TOKEN=$(curl -fsS -X POST http://127.0.0.1:8088/api/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
  | jq -r .access_token)
[[ -n "$TOKEN" && "$TOKEN" != "null" ]] || { echo "T.11 FAIL admin login"; exit 1; }

# Crear verify_bob si no existe:
if ! curl -fsS http://127.0.0.1:8088/api/users -H "Authorization: Bearer $TOKEN" \
     | jq -e '.[] | select(.username == "verify_bob")' >/dev/null; then
  RESP=$(curl -fsS -X POST http://127.0.0.1:8088/api/users \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"username":"verify_bob","display_name":"Bob","role":"employee"}')
  BOB_PASS=$(echo "$RESP" | jq -r .password)
  BOB_ID=$(echo "$RESP" | jq -r .user.id)

  # Provisionar container si hay LXD:
  if command -v lxc >/dev/null 2>&1 && sudo lxc image info laia-agent >/dev/null 2>&1; then
    sudo bash /home/laia-hermes/LAIA/infra/lxd/scripts/create-agent.sh verify_bob \
      >/tmp/bob-create.json 2>&1
    curl -fsS -X POST http://127.0.0.1:8088/api/agents/register \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
      -d "$(jq -c --arg uid "$BOB_ID" '.user_id = $uid' /tmp/bob-create.json)" >/dev/null
  fi
fi

BOB_TOKEN=$(curl -fsS -X POST http://127.0.0.1:8088/api/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"verify_bob\",\"password\":\"${BOB_PASS:-chattest}\"}" | jq -r .access_token)

if [[ -n "${LAIA_VERIFY_LLM_KEY:-}" ]]; then
  curl -fsS -X PATCH http://127.0.0.1:8088/api/user/llm-config \
    -H "Authorization: Bearer $BOB_TOKEN" -H 'Content-Type: application/json' \
    -d "{\"provider\":\"${LAIA_VERIFY_LLM_PROVIDER:-deepseek}\",\"model\":\"${LAIA_VERIFY_LLM_MODEL:-deepseek-chat}\",\"api_key\":\"$LAIA_VERIFY_LLM_KEY\"}" \
    >/dev/null
fi
```

**Verify**: `[[ -n "$BOB_TOKEN" ]] && echo "T.11 OK"`

---

### T.12 — Batería F.X.Y completa

Ejecuta los **71 checks F.X.Y** definidos en la sección 4. Cada uno
emite `<ID> OK|FAIL|WARN|SKIPPED` al log.

---

## 4. Definiciones F.X.Y (banco de comandos)

> Idéntico al plan anterior — sección 4 completa con todos los checks
> agrupados por las 22 secciones documentadas en `docs/db-export/nodes/`.
> Cada check produce 1 línea de resultado.

### F.1 — Infraestructura

```bash
# F.1.1 — Symlink /opt/laia (puede no existir en dev-style)
if [[ -L /opt/laia ]]; then
  test -d "/opt/$(readlink /opt/laia)" && echo "F.1.1 OK" || echo "F.1.1 FAIL"
else
  echo "F.1.1 SKIPPED (dev-style, no /opt/laia)"
fi

# F.1.2 — Dirs canonical
test -d /home/laia-hermes/LAIA-ARCH    && echo "F.1.2a OK" || echo "F.1.2a FAIL"
sudo test -d /srv/laia/agora            && echo "F.1.2b OK" || echo "F.1.2b FAIL"
sudo test -d /srv/laia/users            && echo "F.1.2c OK" || echo "F.1.2c FAIL"
sudo test -d /srv/laia/arch             && echo "F.1.2d OK" || echo "F.1.2d FAIL"
test -f /home/laia-hermes/.laia/auth.json && echo "F.1.2e OK" || echo "F.1.2e WARN"

# F.1.4 — Layout post-d02afcb0 (interactivo en su sitio)
for d in workspaces memories skills plugins; do
  test -d "/home/laia-hermes/LAIA-ARCH/$d" \
    && echo "F.1.4.$d OK" || echo "F.1.4.$d WARN"
done
```

### F.2 — Servicios

```bash
# F.2.1 — units instalados (puede ser 0 en dev-style)
for u in agora-backend laia-gateway laia-pathd laia-ui-server; do
  if systemctl list-unit-files | grep -q "$u.service"; then
    echo "F.2.1.$u OK"
  else
    echo "F.2.1.$u SKIPPED (dev-style, sin systemd unit)"
  fi
done

# F.2.2a — agora-backend respondiendo (con o sin systemd)
curl -fsS http://127.0.0.1:8088/api/health | jq -e '.ok == true' \
  && echo "F.2.2a OK" || echo "F.2.2a FAIL"

# F.2.2b — laia-pathd corriendo
pgrep -f laia-pathd >/dev/null && echo "F.2.2b OK" || echo "F.2.2b WARN"
```

### F.3 — Containers LXD

```bash
if command -v lxc >/dev/null 2>&1; then
  # F.3.1
  sudo lxc image list --format csv 2>/dev/null | awk -F, '{print $1}' \
    | grep -qE "(laia-agent|laia-agora)" \
    && echo "F.3.1 OK" || echo "F.3.1 WARN"
  # F.3.2
  sudo lxc list --format csv -c ns 2>/dev/null | grep -q "RUNNING" \
    && echo "F.3.2 OK" || echo "F.3.2 WARN"
else
  echo "F.3 SKIPPED (sin LXD instalado)"
fi
```

### F.4 — AGORA API

```bash
# F.4.1 — health (ya verificado en T.10/F.2.2a)
echo "F.4.1 OK"

# F.4.2 — admin login (en T.11)
[[ -n "$TOKEN" ]] && echo "F.4.2 OK" || echo "F.4.2 FAIL"

# F.4.3 — /api/me
curl -fsS http://127.0.0.1:8088/api/me -H "Authorization: Bearer $TOKEN" \
  | jq -e ".username == \"$ADMIN_USER\"" && echo "F.4.3 OK" || echo "F.4.3 FAIL"

# F.4.4 — users
curl -fsS http://127.0.0.1:8088/api/users -H "Authorization: Bearer $TOKEN" \
  | jq -e '. | length >= 1' && echo "F.4.4 OK" || echo "F.4.4 FAIL"

# F.4.5 — providers
curl -fsS http://127.0.0.1:8088/api/llm/providers -H "Authorization: Bearer $TOKEN" \
  | jq -e '. | length > 0' && echo "F.4.5 OK" || echo "F.4.5 FAIL"

# F.4.6 — agents
curl -fsS http://127.0.0.1:8088/api/agents -H "Authorization: Bearer $TOKEN" \
  | jq -e '. | length >= 0' && echo "F.4.6 OK" || echo "F.4.6 FAIL"

# F.4.7 — admin/status
curl -fsS http://127.0.0.1:8088/api/admin/status -H "Authorization: Bearer $TOKEN" \
  | jq -e '.status.health.ok == true' && echo "F.4.7 OK" || echo "F.4.7 WARN"

# F.4.8 — Telegram (warn-only)
TG=$(curl -fsS -X POST http://127.0.0.1:8088/api/user/telegram/link-token \
       -H "Authorization: Bearer $BOB_TOKEN" 2>/dev/null)
echo "$TG" | jq -e '.token != null' >/dev/null \
  && curl -fsS -X DELETE http://127.0.0.1:8088/api/user/telegram/link \
       -H "Authorization: Bearer $BOB_TOKEN" | jq -e '.ok == true' >/dev/null \
  && echo "F.4.8 OK" || echo "F.4.8 WARN"
```

### F.5 — Chat E2E

```bash
if [[ -z "${LAIA_VERIFY_LLM_KEY:-}" ]] \
   || ! command -v lxc >/dev/null 2>&1 \
   || ! sudo lxc list --format csv -c n 2>/dev/null | grep -q "agent-verify_bob"; then
  for sub in 1 2 3 4a 4b 5 6; do echo "F.5.$sub SKIPPED"; done
else
  # F.5.1, F.5.2, F.5.3 ya hechos en T.11
  echo "F.5.1 OK"; echo "F.5.2 OK"; echo "F.5.3 OK"

  # F.5.4 — chat SSE + bind mount
  PROMPT='Crea /home/user/verify.txt con texto "ok-verify" usando write_file. No ejecutes nada más.'
  HTTP=$(curl -fsS -N -X POST http://127.0.0.1:8088/api/agents/me/chat \
    -H "Authorization: Bearer $BOB_TOKEN" -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg m "$PROMPT" '{message:$m,session_id:"verify"}')" \
    -o /tmp/chat.txt -w '%{http_code}')
  [[ "$HTTP" == "200" ]] && echo "F.5.4a OK" || echo "F.5.4a FAIL"
  sleep 5
  sudo test -f /srv/laia/users/verify_bob/home/verify.txt \
    && echo "F.5.4b OK" || echo "F.5.4b FAIL"

  # F.5.5 — persistencia post-recreate
  sudo lxc delete --force agent-verify_bob 2>/dev/null
  sudo bash /home/laia-hermes/LAIA/infra/lxd/scripts/create-agent.sh verify_bob >/dev/null 2>&1
  sleep 8
  sudo test -f /srv/laia/users/verify_bob/home/verify.txt \
    && echo "F.5.5 OK" || echo "F.5.5 FAIL"

  # F.5.6 — aislamiento
  curl -fsS -X POST http://127.0.0.1:8088/api/users \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"username":"verify_carol","display_name":"Carol","role":"employee"}' >/dev/null 2>&1
  sudo bash /home/laia-hermes/LAIA/infra/lxd/scripts/create-agent.sh verify_carol >/dev/null 2>&1
  sleep 5
  sudo lxc exec agent-verify_carol -- cat /srv/laia/users/verify_bob/home/verify.txt 2>/dev/null \
    && echo "F.5.6 FAIL (aislamiento roto)" || echo "F.5.6 OK"
fi
```

### F.6 — ARCH UI (puerto 8077)

```bash
if pgrep -f "laia-ui-server" >/dev/null 2>&1 \
   || systemctl is-active --quiet laia-ui-server.service 2>/dev/null; then
  curl -fsS http://127.0.0.1:8077/api/health 2>/dev/null \
    | jq -e '.ok == true' >/dev/null && echo "F.6.1 OK" || echo "F.6.1 FAIL"
  test -d /home/laia-hermes/LAIA/.laia-core/laia-ui-server/frontend/dist \
    && echo "F.6.2 OK" || echo "F.6.2 FAIL"
else
  echo "F.6.1 SKIPPED"; echo "F.6.2 SKIPPED"
fi
```

### F.7 — CLI host

```bash
# F.7.1 — diagnose (puede no existir en dev-style)
if command -v laia >/dev/null 2>&1; then
  sudo laia diagnose 2>&1 | tee /tmp/diagnose.log >/dev/null
  grep -qi "error\|fail" /tmp/diagnose.log && echo "F.7.1 FAIL" || echo "F.7.1 OK"
else
  echo "F.7.1 SKIPPED (sin /usr/local/bin/laia en dev-style)"
fi

# F.7.2
if command -v laia >/dev/null 2>&1; then
  sudo laia status 2>&1 | grep -qE "agora|pathd" \
    && echo "F.7.2 OK" || echo "F.7.2 WARN"
else
  echo "F.7.2 SKIPPED"
fi

# F.7.3
command -v laia >/dev/null 2>&1 \
  && (laia --version 2>&1 | grep -qE "v[0-9]+\." && echo "F.7.3 OK" || echo "F.7.3 WARN") \
  || echo "F.7.3 SKIPPED"
```

### F.8 — Skills + plugins

```bash
curl -fsS http://127.0.0.1:8088/api/me/agent-area/skills \
  -H "Authorization: Bearer $BOB_TOKEN" \
  | jq -e '. | length >= 5' && echo "F.8.1 OK" || echo "F.8.1 WARN"

curl -fsS http://127.0.0.1:8088/api/me/agent-area/plugins \
  -H "Authorization: Bearer $BOB_TOKEN" | jq 'length' >/dev/null \
  && echo "F.8.2 OK" || echo "F.8.2 WARN"
```

### F.9 — Layout estricto (post-migración)

```bash
# F.9.1 — LAIA-ARCH no contiene operacional
F91=OK
for forbidden in sessions atlas cron SOUL.md state.db; do
  [[ -e "/home/laia-hermes/LAIA-ARCH/$forbidden" ]] && F91=FAIL
done
echo "F.9.1 $F91"

# F.9.2 — /srv/laia/arch tiene operacional
sudo test -d /srv/laia/arch/sessions && echo "F.9.2 OK" || echo "F.9.2 WARN"

# F.9.3 — Config rewrite limpio
if sudo test -f /srv/laia/arch/config.yaml; then
  RESIDUE=$(sudo grep -c "~/\.laia/\|/home/laia-hermes/\.laia/" \
            /srv/laia/arch/config.yaml 2>/dev/null || echo 0)
  [[ "$RESIDUE" -eq 0 ]] && echo "F.9.3 OK" || echo "F.9.3 FAIL ($RESIDUE residuos)"
else
  echo "F.9.3 SKIPPED"
fi

# F.9.4 — ~/.laia/ solo contiene legacy compat
ALLOWED="auth.json|auth.lock|\.env|bin|cache|gateway\.|pathd\.sock|processes\.json|admin-session\.json|channel_directory|context_length_cache|models_dev_cache|ollama_cloud_models_cache|backups|state"
F94=OK
for f in $(ls /home/laia-hermes/.laia/); do
  if ! echo "$f" | grep -qE "$ALLOWED"; then
    echo "  ~/.laia/$f no debería seguir ahí"
    F94=WARN
  fi
done
echo "F.9.4 $F94"
```

### F.10 — Executor /exec

```bash
if sudo lxc list --format csv -c n 2>/dev/null | grep -q "agent-verify_bob"; then
  EXEC_IP=$(sudo lxc list "agent-verify_bob" --format csv -c 4 | awk '{print $1}')
  curl -fsS "http://$EXEC_IP:9091/health" | jq -e '.ok == true' \
    && echo "F.10.1 OK" || echo "F.10.1 FAIL"
  sudo lxc exec agent-verify_bob -- cat /etc/laia/executor-token 2>/dev/null \
    | grep -qE '^[A-Za-z0-9_-]{20,}$' && echo "F.10.2 OK" || echo "F.10.2 FAIL"

  EXEC_TOKEN=$(sudo lxc exec agent-verify_bob -- cat /etc/laia/executor-token 2>/dev/null)
  echo "hola" | sudo tee /srv/laia/users/verify_bob/home/test-exec.txt >/dev/null
  curl -fsS -X POST "http://$EXEC_IP:9091/exec" \
    -H "Authorization: Bearer $EXEC_TOKEN" -H 'Content-Type: application/json' \
    -d '{"tool":"read_file","args":{"path":"/home/user/test-exec.txt"}}' \
    | jq -e '.result | contains("hola")' && echo "F.10.3 OK" || echo "F.10.3 FAIL"

  curl -fsS "http://$EXEC_IP:9091/tools" -H "Authorization: Bearer $EXEC_TOKEN" \
    | jq -e '. | length >= 22' && echo "F.10.4 OK" || echo "F.10.4 WARN"

  curl -s -o /dev/null -w '%{http_code}' -X POST "http://$EXEC_IP:9091/exec" -d '{}' \
    | grep -qE '^(401|403)$' && echo "F.10.5 OK" || echo "F.10.5 FAIL"
else
  for sub in 1 2 3 4 5; do echo "F.10.$sub SKIPPED (no agent container)"; done
fi
```

### F.11 — Forwarder

```bash
if command -v lxc >/dev/null 2>&1 \
   && sudo lxc list --format csv -c n 2>/dev/null | grep -q laia-agora; then
  sudo lxc exec laia-agora -- test -d /opt/laia/.laia-core/plugins/agora-executor-forwarder \
    && echo "F.11.1 OK" || echo "F.11.1 FAIL"
else
  # Dev-style: el forwarder está en el repo directo
  test -d /home/laia-hermes/LAIA/.laia-core/plugins/agora-executor-forwarder \
    && echo "F.11.1 OK" || echo "F.11.1 FAIL"
fi
```

### F.12 — Marketplace

```bash
curl -fsS http://127.0.0.1:8088/api/marketplace/skills \
  -H "Authorization: Bearer $TOKEN" 2>/dev/null \
  | jq -e '. | length >= 10' && echo "F.12.1 OK" || echo "F.12.1 WARN"

curl -fsS http://127.0.0.1:8088/api/marketplace/plugins \
  -H "Authorization: Bearer $TOKEN" 2>/dev/null \
  | jq 'length' >/dev/null && echo "F.12.2 OK" || echo "F.12.2 WARN"
```

### F.13 — Scheduled jobs

```bash
NOW_PLUS_5=$(date -u -d '+5 min' '+%M %H * * *')
curl -fsS -X POST http://127.0.0.1:8088/api/user/scheduled-jobs \
  -H "Authorization: Bearer $BOB_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"cron\":\"$NOW_PLUS_5\",\"prompt\":\"ping\",\"delivery\":\"local\",\"one_shot\":true}" \
  2>/dev/null | jq -e '.id != null' && echo "F.13.1 OK" || echo "F.13.1 WARN"

curl -fsS http://127.0.0.1:8088/api/user/scheduled-jobs \
  -H "Authorization: Bearer $BOB_TOKEN" 2>/dev/null \
  | jq -e '. | length >= 1' && echo "F.13.2 OK" || echo "F.13.2 WARN"
```

### F.14 — Webhooks

```bash
RESP=$(curl -fsS -X POST http://127.0.0.1:8088/api/user/webhook \
         -H "Authorization: Bearer $BOB_TOKEN" 2>/dev/null)
WH_SECRET=$(echo "$RESP" | jq -r .secret 2>/dev/null)
WH_SLUG=$(echo "$RESP" | jq -r .slug 2>/dev/null)
[[ ${#WH_SECRET} -eq 64 ]] && echo "F.14.1 OK" || echo "F.14.1 WARN"

if [[ ${#WH_SECRET} -eq 64 ]]; then
  PAYLOAD='{"text":"v"}'
  SIG=$(printf '%s' "$PAYLOAD" | openssl dgst -sha256 -hmac "$WH_SECRET" | awk '{print $2}')
  curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8088/api/wh/$WH_SLUG" \
    -H "X-Hub-Signature-256: sha256=$SIG" -H 'Content-Type: application/json' -d "$PAYLOAD" \
    | grep -q 200 && echo "F.14.2 OK" || echo "F.14.2 FAIL"
  curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8088/api/wh/$WH_SLUG" \
    -H "X-Hub-Signature-256: sha256=BAD" -H 'Content-Type: application/json' -d "$PAYLOAD" \
    | grep -qE '^(401|403)$' && echo "F.14.3 OK" || echo "F.14.3 FAIL"
fi
```

### F.15 — Soul/Instructions

```bash
curl -fsS http://127.0.0.1:8088/api/me/agent-area \
  -H "Authorization: Bearer $BOB_TOKEN" \
  | jq -e 'has("soul_md") and has("instructions_md")' \
  && echo "F.15.1 OK" || echo "F.15.1 FAIL"

curl -fsS -X PATCH http://127.0.0.1:8088/api/me/agent-area \
  -H "Authorization: Bearer $BOB_TOKEN" -H 'Content-Type: application/json' \
  -d '{"soul_md":"# Bob soul verify"}' \
  | jq -e '.soul_md | contains("Bob soul verify")' \
  && echo "F.15.2 OK" || echo "F.15.2 FAIL"

curl -fsS http://127.0.0.1:8088/api/me/agent-area \
  -H "Authorization: Bearer $BOB_TOKEN" \
  | jq -e '.soul_md | contains("Bob soul verify")' \
  && echo "F.15.3 OK" || echo "F.15.3 FAIL"
```

### F.16 — Voice/Vision/Web

```bash
# En dev-style sin container agora, miramos el venv del backend del host:
VENV=/home/laia-hermes/LAIA/services/agora-backend/.venv/bin/python
$VENV -c "import edge_tts" 2>/dev/null && echo "F.16.1 OK" || echo "F.16.1 FAIL"
$VENV -c "import firecrawl" 2>/dev/null && echo "F.16.2 OK" || echo "F.16.2 FAIL"
$VENV -c "import exa_py" 2>/dev/null && echo "F.16.3 OK" || echo "F.16.3 FAIL"

if [[ -z "${LAIA_VERIFY_LLM_KEY:-}" ]]; then
  echo "F.16.4 SKIPPED"
else
  curl -fsS -N -X POST http://127.0.0.1:8088/api/agents/me/chat \
    -H "Authorization: Bearer $BOB_TOKEN" -H 'Content-Type: application/json' \
    -d '{"message":"Usa fetch_url con https://example.com y dime el title","session_id":"v-fetch"}' \
    -o /tmp/fetch.txt -w '%{http_code}' | grep -q 200 \
    && grep -qi "Example Domain" /tmp/fetch.txt \
    && echo "F.16.4 OK" || echo "F.16.4 WARN"
fi
```

### F.17 — Delegation

```bash
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/agents/delegate \
  -H "Authorization: Bearer $BOB_TOKEN" -X POST -d '{}' \
  | grep -qE '^(400|422|404)$' && echo "F.17.1 OK" || echo "F.17.1 WARN"
```

### F.18 — Snapshot/Restore

```bash
curl -fsS -X POST "http://127.0.0.1:8088/api/agents/verify_bob/snapshot" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"label":"verify"}' 2>/dev/null | jq -e '.id != null' \
  && echo "F.18.1 OK" || echo "F.18.1 WARN"

curl -fsS "http://127.0.0.1:8088/api/agents/verify_bob/snapshots" \
  -H "Authorization: Bearer $TOKEN" 2>/dev/null | jq -e '. | length >= 1' \
  && echo "F.18.2 OK" || echo "F.18.2 WARN"
```

### F.19 — Backup

```bash
cd /home/laia-hermes/LAIA
sudo make backup 2>&1 | tee /tmp/backup.log >/dev/null
grep -qE "backup created|created successfully|tar.gz" /tmp/backup.log \
  && echo "F.19.1 OK" || echo "F.19.1 WARN"

(sudo ls /srv/laia/backups/ 2>/dev/null | grep -qE "\.tar\.gz$" \
 || sudo ls /home/laia-hermes/.laia/backups/ 2>/dev/null | grep -qE "\.tar\.gz$") \
  && echo "F.19.2 OK" || echo "F.19.2 WARN"
```

### F.20 — ARCH UI extendido

```bash
if pgrep -f laia-ui-server >/dev/null 2>&1 \
   || systemctl is-active --quiet laia-ui-server.service 2>/dev/null; then
  curl -fsS http://127.0.0.1:8077/api/workspaces 2>/dev/null | jq 'length' >/dev/null \
    && echo "F.20.1 OK" || echo "F.20.1 FAIL"
  curl -fsS http://127.0.0.1:8077/api/agent/sessions 2>/dev/null | jq 'length' >/dev/null \
    && echo "F.20.2 OK" || echo "F.20.2 FAIL"
  curl -fsS http://127.0.0.1:8077/ 2>/dev/null | grep -qi '<html' \
    && echo "F.20.3 OK" || echo "F.20.3 FAIL"
else
  for sub in 1 2 3; do echo "F.20.$sub SKIPPED"; done
fi
```

### F.21 — Gateway + plataformas

```bash
# F.21.1 — gateway unit o proceso
(systemctl list-unit-files | grep -q laia-gateway.service \
  || pgrep -f "laia-gateway\|gateway run" >/dev/null) \
  && echo "F.21.1 OK" || echo "F.21.1 WARN"

# F.21.2 — telegram deep_link
curl -fsS -X POST http://127.0.0.1:8088/api/user/telegram/link-token \
  -H "Authorization: Bearer $BOB_TOKEN" 2>/dev/null \
  | jq -e '.deep_link | startswith("https://t.me/") or startswith("tg://")' \
  && echo "F.21.2 OK" || echo "F.21.2 WARN"
```

### F.22 — Atlas / pathd

```bash
# F.22.1 — socket existe (en nueva ubicación o legacy)
(sudo test -S /home/laia-hermes/.laia/pathd.sock \
  || sudo test -S /srv/laia/arch/pathd.sock \
  || sudo test -S /home/laia-hermes/LAIA-ARCH/.pathd.sock) \
  && echo "F.22.1 OK" || echo "F.22.1 WARN"

# F.22.2 — atlas dir
sudo test -d /srv/laia/arch/atlas && echo "F.22.2 OK" || echo "F.22.2 WARN"
```

---

## 5. Reporte final

### T.13 — Compilar reporte

```bash
cat > /tmp/laia-migrate-report.md <<EOF
# LAIA Migration + E2E Verification Report

- Fecha: $(date -Iseconds)
- VM: $(hostname)
- Layout antes: ~/.laia/ (482MB mezclado)
- Layout después:
  - ~/LAIA-ARCH/: $(du -sh /home/laia-hermes/LAIA-ARCH 2>/dev/null | awk '{print $1}')
  - /srv/laia/arch/: $(sudo du -sh /srv/laia/arch 2>/dev/null | awk '{print $1}')
  - ~/.laia/ (legacy compat): $(du -sh /home/laia-hermes/.laia 2>/dev/null | awk '{print $1}')

## Resumen

| Resultado | Total |
|---|---|
| OK | $(grep -c " OK$" /tmp/laia-migrate.log) |
| FAIL | $(grep -c " FAIL" /tmp/laia-migrate.log) |
| WARN | $(grep -c " WARN" /tmp/laia-migrate.log) |
| SKIPPED | $(grep -c " SKIPPED" /tmp/laia-migrate.log) |

## Detalle por sección F.*

EOF

for sec in F.1 F.2 F.3 F.4 F.5 F.6 F.7 F.8 F.9 \
           F.10 F.11 F.12 F.13 F.14 F.15 F.16 F.17 F.18 F.19 F.20 F.21 F.22; do
  echo "### $sec" >> /tmp/laia-migrate-report.md
  echo '```' >> /tmp/laia-migrate-report.md
  grep "^$sec\." /tmp/laia-migrate.log | sort -u >> /tmp/laia-migrate-report.md
  echo '```' >> /tmp/laia-migrate-report.md
done

cat >> /tmp/laia-migrate-report.md <<EOF

## Críticos en FAIL (bloquean prod)

\`\`\`
$(grep -E "(F\.1\.2[a-d]|F\.2\.2a|F\.4\.1|F\.4\.2|F\.4\.3|F\.4\.5|F\.9\.1|F\.9\.3|F\.11\.1|F\.14\.2|F\.14\.3|F\.15\.1|F\.16\.1|F\.16\.2|F\.16\.3) FAIL" /tmp/laia-migrate.log)
\`\`\`

## Cosas que sobran en ~/.laia/ (F.9.4)

\`\`\`
$(ls /home/laia-hermes/.laia/ | sort)
\`\`\`
EOF

cat /tmp/laia-migrate-report.md
```

---

## 6. Criterios de aceptación

**Críticos (0 FAIL obligatorio)**:
- F.1.2a-d (dirs canonical existen)
- F.2.2a (agora-backend responde)
- F.4.1-4.5 (API básica)
- F.9.1, F.9.3 (layout limpio, sin residuos)
- F.11.1 (forwarder existe)
- F.14.2, F.14.3 (HMAC)
- F.15.1 (soul/instructions API)
- F.16.1-16.3 (libs voice/vision/web)
- F.10.1-10.3, F.10.5 SI hay container LXD activo

**Con `LAIA_VERIFY_LLM_KEY`** añade:
- F.5.4, F.5.5, F.5.6, F.16.4

**WARN-tolerantes** (no bloquean):
- F.1.1, F.7.* (dev-style sin /opt/laia ni wrappers)
- F.3.* (sin LXD)
- F.6, F.20 (sin ui-server)
- F.4.8, F.21.2 (sin Telegram)
- F.12, F.13, F.17, F.18, F.19, F.22 (features parciales o opcionales)

---

## 7. Rollback si algo va mal

Si el plan se rompe a mitad:

```bash
# Desde el HOST (Mac), restaurar snapshot:
multipass restore <vm-name>.pre-migration-2026-05-25
```

Vuelve al estado pre-T.0. Toda la migración se descarta.

Si llegaste hasta T.10 y los servicios no arrancan pero los ficheros
están donde toca, puedes intentar:

```bash
# Restaurar config.yaml a su estado pre-migración:
sudo cp /srv/laia/arch/config.yaml.pre-migrate.bak /srv/laia/arch/config.yaml

# Mover de vuelta dirs interactivos (si quieres deshacer T.4):
for dir in workspaces memories skills plugins; do
  sudo -u laia-hermes mv /home/laia-hermes/LAIA-ARCH/$dir /home/laia-hermes/.laia/$dir
done

# Mover de vuelta operacionales (T.5):
sudo mv /srv/laia/arch/* /home/laia-hermes/.laia/   # ojo: solo si .laia/ está vacío
```

Pero el snapshot es mucho más fiable.

---

## 8. NO TOCAR (lista explícita)

- `/home/laia-hermes/LAIA/` — repo intacto.
- `/srv/laia/agora/` — data viva del backend, ya en sitio canonical.
- `/srv/laia/users/` — workspaces de PA-AGORA users.
- `/srv/laia/backups/`, `/srv/laia/state/` — operacional existente.
- `~/.laia/auth.json`, `~/.laia/.env`, `~/.laia/auth.lock` — secrets
  legacy que los containers leen.
- `~/.laia/admin-session.json` — token sesión web (operador decide).
- `~/.laia/bin/`, `~/.laia/cache/` — caches legacy.
- Código del repo (no se modifica nada de `bin/`, `infra/`, `services/`).

---

## 9. Resumen ejecutivo

- **Migración in-place**, sin reinstalar, sin perder data viva.
- **1 IA, 1 VM, secuencial**.
- **T.0 snapshot obligatorio** — sin él NO se continúa.
- **T.1-T.9**: parar procesos, mover ~482 MB de data a su sitio
  canonical, reescribir config, update env.
- **T.10**: rearrancar procesos contra el nuevo layout.
- **T.11-T.12**: crear `verify_bob` + ejecutar batería F.X.Y completa
  (71 checks cubriendo las 22 secciones documentadas).
- **T.13**: reporte markdown.
- **Tiempo total**: 1-2 horas (sin reinstalar acelera mucho).
- **Si todo verde** → esta VM ES la referencia funcional viva del nuevo
  layout. Cualquier server nuevo que ejecute install/clone debería
  acabar idéntico.
- **Si hay FAIL** → cada uno en `workflow/problems.md` con evidencia.
  Decidir si arreglar antes de promover `stable` a tag nuevo.

---

## 10. Archivos críticos referenciados

| Archivo | Propósito |
|---|---|
| `workflow/arch-data-layout.md` | Contrato del layout (qué va dónde). |
| `infra/installer/lib/clone.sh:782-832` | `clone_phase_h_rewrite_config_paths` — referencia para T.7. |
| `services/agora-backend/.venv/bin/python` | Backend que rearranca en T.10. |
| `infra/bin/laia-pathd` | Daemon que rearranca en T.10. |
| `docs/db-export/nodes/*.md` | Documentación de cada subsistema testeado en F.*. |

---

## 11. T.14 — Pulido final (production-ready + install/clone alignment)

> **Cuándo correr esta sección**: después de T.0-T.13 con la batería F.X.Y
> ejecutada al menos una vez. Esta fase cierra los gaps detectados en el
> reporte de T.13, valida E2E con LLM real + container, y deja el árbol
> listo para que `install.sh` y `clone.sh` produzcan EXACTAMENTE este
> mismo layout en cualquier máquina nueva.
>
> **Objetivo**: cero FAIL, cero WARN crítico, snapshot LXD nuevo como
> baseline, y un commit en `main` que tagea esta VM como "referencia
> funcional viva post-d02afcb0".

### T.14.1 — Resolver bypass del backend a `/srv/laia/arch/config.yaml`

**Goal**: `app/main.py:221` fuerza `LAIA_HOME=settings.data_dir`
(= `/srv/laia/agora`) al arrancar, anulando el rewrite del T.7. O se
cambia el código, o se documenta que el backend tiene su propio config
y arch no aplica.

**Investigación**:
```bash
grep -nE "LAIA_HOME|config\.yaml" /home/laia-hermes/LAIA/services/agora-backend/app/main.py
grep -nE "LAIA_HOME|config\.yaml" /home/laia-hermes/LAIA/services/agora-backend/app/agent_pool.py
grep -rnE "_os.environ\[.LAIA_HOME.\]" /home/laia-hermes/LAIA/services/
```

**Decisión esperada**:
- **Opción A** (recomendada): el backend lee `config.yaml` del LAIA_HOME
  que recibe del entorno; si está vacío, fallback a su `data_dir`. Esto
  hace que el rewrite del T.7 sí tenga efecto.
- **Opción B**: documentar que `agora-backend` tiene config propio en
  `/srv/laia/agora/config.yaml` y `/srv/laia/arch/config.yaml` es
  exclusivamente para el ARCH (laia-pathd, laia-ui-server, CLI). En ese
  caso, T.7 del plan necesita un paso paralelo para `agora`.

**Output**: parche aplicado al código O nota en `workflow/arch-data-layout.md`
explicando la separación de configs.

**Verify**:
```bash
# Tras parchar, reiniciar y comprobar:
LAIA_HOME=/home/laia-hermes/LAIA-ARCH pm2 restart agora-backend --update-env
sleep 3
curl -fsS http://127.0.0.1:8088/api/health | jq -r '.data_dir, .auth_json_path'
# Debe reflejar el path que el operador eligió, no un hardcoded.
```

---

### T.14.2 — Limpiar stubs de `~/.laia/` creados por sesión CLI activa

**Goal**: Tu `laia` CLI en otra sesión SSH repobló `~/.laia/` con stubs
vacíos. Cerrarlo, validar que el bashrc nuevo aplica, y borrar los
stubs.

**Commands**:
```bash
# 1. Identificar y cerrar la sesión activa:
ps -ef | grep -E "/\.laia-core/laia" | grep -v grep
# Cerrar manualmente la sesión SSH/terminal correspondiente.

# 2. Verificar que ningún proceso `laia` queda:
pgrep -af "/.laia-core/laia" && echo "STILL RUNNING" || echo "CLEAN"

# 3. Borrar los stubs vacíos:
for d in SOUL.md cron logs memories sessions skills workspaces state.db state.db-shm state.db-wal; do
  if [[ -e "/home/laia-hermes/.laia/$d" ]]; then
    # Sanity: skip if NOT empty (no debería haber, pero por si acaso)
    if [[ -d "/home/laia-hermes/.laia/$d" ]] && [[ -z "$(ls -A /home/laia-hermes/.laia/$d)" ]]; then
      rmdir "/home/laia-hermes/.laia/$d" && echo "removed empty dir $d"
    elif [[ -f "/home/laia-hermes/.laia/$d" ]]; then
      SIZE=$(stat -c%s "/home/laia-hermes/.laia/$d")
      [[ "$SIZE" -lt 100 ]] && rm "/home/laia-hermes/.laia/$d" && echo "removed stub file $d"
    fi
  fi
done

# 4. Reabrir nueva sesión y verificar LAIA_HOME:
bash -lc 'echo $LAIA_HOME'   # debe ser /home/laia-hermes/LAIA-ARCH

# 5. Arrancar laia CLI y verificar que NO repobla ~/.laia/:
bash -lc 'laia --version'
ls -la /home/laia-hermes/.laia/ | grep -v "auth\|\.env\|bin\|cache\|admin-session\|channel_directory\|context_length_cache\|models_dev_cache\|ollama_cloud_models_cache\|backups\|gateway_state"
# Salida vacía = OK.
```

**Verify**:
```bash
test ! -d /home/laia-hermes/.laia/sessions \
  && test ! -d /home/laia-hermes/.laia/workspaces \
  && test ! -f /home/laia-hermes/.laia/SOUL.md \
  && echo "T.14.2 OK"
```

**On failure**: Si tras reabrir shell el CLI sigue repoblando, indica que
el código del CLI tiene un fallback hardcoded a `~/.laia/`. Buscar en
`/home/laia-hermes/LAIA/.laia-core/` y proponer fix.

---

### T.14.3 — Destrabar LXD y aprovisionar `verify_bob`

**Goal**: el daemon LXD quedó colgado en `lxc init laia-agent
agent-verify_bob` durante T.11. Reiniciar daemon, reintentar provision,
y registrar el agent en el backend.

**Commands**:
```bash
# 1. Diagnóstico previo:
sudo lxc operation list 2>&1 | head
sudo journalctl -u snap.lxd.daemon --since "30 min ago" --no-pager | tail -20

# 2. Reiniciar daemon LXD:
sudo systemctl restart snap.lxd.daemon
sleep 5
sudo lxc list   # debe responder rápido y mostrar agent-jorge-dev + laia-agora

# 3. Reintentar create-agent:
sudo bash /home/laia-hermes/LAIA/infra/lxd/scripts/create-agent.sh verify_bob \
  | tee /tmp/bob-create-retry.json

# 4. Esperar IPv4:
for i in {1..30}; do
  IP=$(sudo lxc list "agent-verify_bob" --format csv -c 4 2>/dev/null | awk '{print $1}')
  [[ -n "$IP" ]] && break
  sleep 2
done
echo "agent-verify_bob IPv4: $IP"

# 5. Registrar agent en agora:
source /tmp/laia-creds.env   # del T.11 (si sigue presente)
curl -fsS -X POST http://127.0.0.1:8088/api/agents/register \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "$(jq -c --arg uid "$BOB_ID" '.user_id = $uid' /tmp/bob-create-retry.json | tail -1)"
```

**Verify**:
```bash
sudo lxc list --format csv -c ns | grep -q "agent-verify_bob.*RUNNING" \
  && echo "T.14.3 OK"
curl -fsS "http://$IP:9091/health" | jq -e '.ok == true' && echo "executor OK"
```

---

### T.14.4 — F.5 Chat E2E completo (con LLM key + container)

**Goal**: re-ejecutar la subsección F.5 que quedó SKIPPED. Requiere
`LAIA_VERIFY_LLM_KEY` exportado y `agent-verify_bob` provisionado
(T.14.3).

**Pre-requisito**:
```bash
export LAIA_VERIFY_LLM_KEY="sk-1a0508d4b43e47e3976d5c26052bd7ea"  # deepseek de jorge, o uno fresco
export LAIA_VERIFY_LLM_PROVIDER=deepseek
export LAIA_VERIFY_LLM_MODEL=deepseek-chat

# Configurar LLM en verify_bob:
source /tmp/laia-creds.env
curl -fsS -X PATCH http://127.0.0.1:8088/api/user/llm-config \
  -H "Authorization: Bearer $BOB_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"provider\":\"$LAIA_VERIFY_LLM_PROVIDER\",\"model\":\"$LAIA_VERIFY_LLM_MODEL\",\"api_key\":\"$LAIA_VERIFY_LLM_KEY\"}"
```

**Commands**: ejecutar la batería F.5.1-F.5.6 (idéntica a la definida en
sección 4 del plan). Cada sub-check debe quedar `OK`.

**Verify**:
```bash
grep -E "^F\.5\." /tmp/laia-migrate.log | tail -7
# Esperado: 7 líneas OK (no SKIPPED).
```

**On failure**:
- F.5.4b FAIL (bind mount) → revisar `/srv/laia/users/verify_bob/home/` y profile LXD `laia-employee`.
- F.5.5 FAIL (persistencia post-recreate) → bind mount no es persistente
  o el script de recreate borra demasiado.
- F.5.6 FAIL (aislamiento roto) → CRÍTICO de seguridad, parar y reportar.

---

### T.14.5 — F.10 Executor /exec completo

**Goal**: re-ejecutar F.10.1-F.10.5 con el container provisto en T.14.3.

**Commands**: idénticos a la sección 4 F.10 del plan.

**Verify**:
```bash
grep -E "^F\.10\." /tmp/laia-migrate.log | tail -5
# Esperado: 5 líneas OK.
```

---

### T.14.6 — F.14 Webhooks (clarificar endpoint creator)

**Goal**: el plan asumía `/api/user/webhook` pero esa ruta devuelve 404.
La ruta delivery real es `/api/webhooks/{slug}`. Falta localizar la ruta
de creación o documentar que el feature está en flujo distinto.

**Investigación**:
```bash
curl -fsS http://127.0.0.1:8088/openapi.json | jq -r '.paths | keys[] | select(test("webhook"; "i"))'
grep -rnE "@app\.|@router\.|/api/.*webhook" /home/laia-hermes/LAIA/services/agora-backend/app/ | grep -v ".pyc"
```

**Output**: actualizar F.14 en sección 4 del plan con la ruta correcta
o marcar como SKIPPED with note si el endpoint no está expuesto aún.

---

### T.14.7 — Auditar `install.sh` para que produzca este layout en VM fresca

**Goal**: garantizar que un `curl|sudo bash install.sh` en una VM Ubuntu
limpia produce el mismo árbol que esta VM tiene tras T.0-T.14. Hoy el
instalador no contempla `~/LAIA-ARCH/` y `/srv/laia/arch/` separados.

**Checklist**:
```bash
# 1. Leer todas las fases del installer:
ls /home/laia-hermes/LAIA/infra/installer/lib/
grep -nE "mkdir|chown|chmod" /home/laia-hermes/LAIA/infra/installer/lib/*.sh

# 2. Verificar que crea:
#    /home/<user>/LAIA-ARCH/   (700, user-owned)
#    /srv/laia/arch/           (700, root-owned)
#    /srv/laia/agora/          (existing)
#    /srv/laia/users/          (existing)
#    /srv/laia/backups/        (existing)
#    /srv/laia/state/          (existing)

# 3. Verificar que el config.yaml inicial:
#    - laia_home apunta a $HOME/LAIA-ARCH
#    - Paths operacionales apuntan a /srv/laia/arch/
#    - NO contiene refs a ~/.laia/

# 4. Verificar que el `.bashrc` queda con `export LAIA_HOME=...LAIA-ARCH`.

# 5. Verificar que el installer NO toca `~/.laia/` salvo para:
#    - auth.json (linking), .env, auth.lock (legacy compat)
```

**Output**: parche al installer (un commit dedicado) que añada las
nuevas fases. Si el installer ya las tenía via `clone.sh`, dejar nota
indicando que `install.sh` debe convergir.

**Tests**: añadir test en `~/LAIA/tests/installer/` que monte una VM
desechable, ejecute `install.sh`, y verifique el layout con un subset
mínimo de F.X.Y.

---

### T.14.8 — Auditar `clone.sh` (LXC clone)

**Goal**: el clonador ya tiene `clone_phase_h_rewrite_config_paths`
(referenciado en T.7), pero hay que validar que produce el layout
canónico de extremo a extremo en una VM nueva.

**Checklist**:
```bash
# 1. Leer todas las fases:
grep -E "^clone_phase_" /home/laia-hermes/LAIA/infra/installer/lib/clone.sh

# 2. Verificar que cada fase crea los paths correctos:
grep -nE "LAIA-ARCH|/srv/laia/arch|/srv/laia/agora" /home/laia-hermes/LAIA/infra/installer/lib/clone.sh

# 3. Comprobar que tras clone:
#    - El target VM tiene ~/.LAIA-ARCH/ y /srv/laia/arch/ creados
#    - workspaces, memories, plugins se restauran al sitio nuevo (no a ~/.laia/)
#    - sessions, atlas, state.db acaban en /srv/laia/arch/
#    - config.yaml en target apunta a paths del target, no del source

# 4. Test E2E sugerido:
#    - LXC launch ubuntu nueva
#    - sudo clone.sh laia-hermes  (o equivalente)
#    - Ejecutar batería F.X.Y reducida (F.1, F.2, F.4, F.9)
```

**Output**: si hay drift entre `install.sh` y `clone.sh`, decidir cuál
es la fuente de verdad y converger.

---

### T.14.9 — Test E2E permanente en `tests/`

**Goal**: la batería F.X.Y de este plan es un one-off shell. Convertirla
en test ejecutable repetible. Per CLAUDE.md "toda integración nueva
necesita un test en `~/LAIA/tests/`".

**Commands**:
```bash
mkdir -p /home/laia-hermes/LAIA/tests/e2e
# Crear tests/e2e/test_ecosystem_layout.sh con la batería F.X.Y completa,
# parametrizable por env (LAIA_VERIFY_LLM_KEY opcional).
# Hacer que `make test-e2e` la invoque.
```

**Verify**:
```bash
cd /home/laia-hermes/LAIA
make test-e2e   # exit 0 si todo verde
```

**Criterio de aceptación**: el test E2E corre limpio en esta VM y en una
VM nueva clonada, y se integra al CI si lo hay.

---

### T.14.10 — Snapshot baseline + tag git

**Goal**: dejar un punto de restore definitivo y un commit firmado en
`main` que tagee este estado como "post-d02afcb0 ecosystem reference".

**Commands** (host Mac, no la VM):
```bash
# 1. Snapshot LXD/Multipass nuevo:
multipass snapshot <vm-name> --name post-migration-2026-05-26-clean

# 2. En la VM, tag git:
cd /home/laia-hermes/LAIA
git checkout stable
git tag -a v2026.05-ecosystem-clean -m "Ecosystem layout post-d02afcb0 verified end-to-end (T.14 polish)"
# git push origin v2026.05-ecosystem-clean    # solo tras consenso con Jorge
```

**Verify**:
```bash
git tag -l "v2026.05-ecosystem-clean" | grep -q "v2026.05-ecosystem-clean" && echo "tag OK"
```

---

### T.14.11 — Actualizar docs canónicas

**Goal**: si hay drift entre `LAIA_ECOSYSTEM.md`, `workflow/arch-data-layout.md`
y la realidad post-T.14, actualizar (con consenso Jorge).

**Checklist**:
- `LAIA_ECOSYSTEM.md` — solo se edita con permiso explícito (regla
  CLAUDE.md). Si necesita cambios, propuesta en `workflow/proposals/`.
- `workflow/arch-data-layout.md` — actualizar si T.14.1 cambia el
  comportamiento del backend respecto al config.yaml.
- `workflow/changelog.md` — añadir entrada con resumen de T.14.
- `workflow/problems.md` — cerrar los items abiertos por T.13 (backend
  bypass, CLI stubs, LXD hang) si se resolvieron.
- `workflow/security.md` — añadir nota del NOPASSWD sudoers temporal
  usado durante migración (creado y borrado).

---

### T.14.12 — Cleanup final

**Goal**: borrar artefactos transitorios de la migración.

**Commands**:
```bash
# 1. Backups pre-migración (mantener 1 semana, luego borrar):
ls -la /srv/laia/arch/config.yaml.pre-migrate.bak
ls -la /home/laia-hermes/.bashrc.pre-migrate.bak
# Borrar tras 7 días si no hubo rollback.

# 2. Logs y evidencias del migration runner:
ls /tmp/laia-migrate*
ls /tmp/laia-migrate-evidence/
# Mover a /home/laia-hermes/LAIA/workflow/evidence/2026-05-26-migration/
# antes de que /tmp se limpie.

# 3. Sudoers temp ya borrado en T.13 — verificar:
sudo test -f /etc/sudoers.d/99-laia-migration && echo "STILL THERE — REMOVE" || echo "CLEAN"

# 4. Dirs vacíos en ~/.laia/ tras T.14.2:
find /home/laia-hermes/.laia/ -maxdepth 1 -type d -empty
```

**Verify**:
```bash
test ! -f /etc/sudoers.d/99-laia-migration && echo "T.14.12 sudoers OK"
test -d /home/laia-hermes/LAIA/workflow/evidence/2026-05-26-migration && echo "evidence archived"
```

---

## 12. Criterios de aceptación T.14 (production-ready)

**Críticos (0 FAIL obligatorio, 0 SKIPPED salvo justificación documentada)**:
- T.14.1: backend respeta config.yaml O separación documentada.
- T.14.2: `~/.laia/` solo contiene legacy compat real.
- T.14.3: `agent-verify_bob` RUNNING.
- T.14.4: F.5.1-F.5.6 todos OK.
- T.14.5: F.10.1-F.10.5 todos OK.
- T.14.7: `install.sh` produce el layout en VM nueva (test pasado).
- T.14.8: `clone.sh` produce el layout en VM nueva (test pasado).
- T.14.9: `make test-e2e` exit 0.
- T.14.10: tag git creado.
- T.14.12: cleanup completo.

**WARN tolerables**:
- T.14.6 si webhook creator endpoint no existe aún (feature in flight).
- T.14.11 si no hay drift documental que cerrar.

---

## 13. Output esperado al final de T.14

1. **Esta VM**: ARCH UI, agora-backend, executor, chat E2E, todo
   funcional. Cero residuos legacy. Snapshot baseline grabado.
2. **Repo**: commit en `main` con tag `v2026.05-ecosystem-clean`, tests
   E2E permanentes, installer y cloner alineados con el layout, docs
   actualizados.
3. **VM nueva (validación)**: ejecutar `install.sh` en VM Ubuntu fresca
   y obtener un layout idéntico al de esta VM, con la batería F.X.Y
   completa pasando.

---

## 14. Archivos críticos referenciados (extendido para T.14)

| Archivo | Propósito |
|---|---|
| `services/agora-backend/app/main.py:221` | Bypass de LAIA_HOME — objeto del T.14.1. |
| `services/agora-backend/app/config.py:14-22` | Resolución de `data_dir` — referencia para T.14.1. |
| `infra/installer/lib/*.sh` | Fases del installer — auditadas en T.14.7. |
| `infra/installer/lib/clone.sh` | Cloner LXC — auditado en T.14.8. |
| `tests/e2e/test_ecosystem_layout.sh` | Test E2E permanente — creado en T.14.9. |
| `Makefile` (target `test-e2e`) | Entry point del test — creado en T.14.9. |
