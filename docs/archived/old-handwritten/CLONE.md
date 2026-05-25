# LAIA — Migración con `laia-clone`

`laia-clone` es PULL: se ejecuta **en el servidor nuevo** y tira los datos
desde el viejo por SSH. No usa `lxc export/import`; reconstruye containers
en el destino con su arquitectura nativa, así que cross-arch
(`arm64` → `amd64` y viceversa) está soportado.

## Pre-checks en el servidor nuevo

Antes de lanzar el clone:

```bash
# 1. Espacio en disco
df -h /        # debe haber >= 15 GB libres

# 2. SSH al viejo debe funcionar SIN prompt de password
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519     # si no existe
ssh-copy-id laia-hermes@<viejo-ip-o-hostname>
ssh -o BatchMode=yes laia-hermes@<viejo-ip-o-hostname> 'echo ok'

# 3. Snapshot del estado virgen del server nuevo (si el hypervisor lo permite)

# 4. apt list para verificar disponibilidad de snapd
command -v snap || sudo apt-get install -y snapd
```

## Comando

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo bash -s -- --mode clone --source usuario@IP_O_HOST_REAL --yes -- --bwlimit=50M
```

Repo privado:

```bash
read -rsp "GitHub token: " GITHUB_TOKEN; echo
curl -fsSL \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo LAIA_GITHUB_TOKEN="$GITHUB_TOKEN" bash -s -- --mode clone --source usuario@IP_O_HOST_REAL --yes -- --bwlimit=50M
```

No uses placeholders como `IP_DEL_VIEJO`, `old-server` o
`viejo-server`: el bootstrap los rechaza antes de abrir SSH. En modo
interactivo puedes omitir `--mode` y `--source`; el instalador preguntará si
quieres instalar desde cero o clonar, y si clonas pedirá usuario SSH + IP/host.

Si `/opt/laia` no existe en el destino (o está parcialmente instalado),
`laia-clone` lo detecta, limpia y ejecuta `laia-install --minimal` primero,
inicializa defaults LXD y construye las imágenes (10-20 min en aarch64).
Durante la build de imágenes verás un heartbeat cada 60 s; si te incomoda
el silencio, `tail -f /tmp/build-base.log /tmp/build-agora.log` en otro shell.

## Qué transfiere

| Recurso | Transferido | Detalle |
|---|---|---|
| `/opt/laia/` | NO | El destino lo recrea vía `laia-install --minimal`. |
| `/srv/laia/agora/` | SÍ | rsync íntegro (incluye `agora.db`, la fuente única). |
| `/srv/laia/users/<slug>/` | SÍ | rsync por slug enumerado de `agora.db`. UID/GID re-mapeados al idmap real del container LXD del destino. |
| `/srv/laia/arch/` | SÍ | rsync íntegro si existe; si no, fallback a `~/.laia/{workspaces,memories,cron,sessions,atlas,platforms,plugins,sandboxes,orchestrator-runs,pastes,migration,whatsapp,state.db,SOUL.md,config.yaml}` con remap. |
| `~/.laia/auth.json` y `~/.laia/.env` | SÍ | rsync archivo a archivo, mode 600. |
| `~/.laia/admin-session.json` | OPCIONAL | sólo con `--keep-session`. |
| `~/.laia/mlx-servers/` | NO | Datos personales fuera del producto. Si los necesitas, copia aparte. |
| Containers LXD vía `lxc export/import` | NO | Se reconstruyen locales (`rebuild-3-provision-agora.sh` + `rebuild-4-first-user.sh --existing-user-only`). |

### Rewrite de `config.yaml` (Atlas-aware)

El destino normaliza tres anchors canónicas en `/srv/laia/arch/config.yaml`:

```yaml
paths:
  laia_root: /opt/laia                              # antes /home/<user>/LAIA
  laia_home: ${LAIA_HOME:-/srv/laia/arch}           # antes /home/<user>/.laia
  agora_data: /srv/laia/agora/agora.db              # antes ${paths.laia_home}/agora.db
```

Los demás `${paths.X}` aliases derivan de éstas; `laia-pathd` regenera
`~/.laia/.env.paths` al detectar el cambio.

### Reset del password admin

El hash del admin importado de `agora.db` no se puede invertir (pbkdf2
one-way), así que `laia-clone` lo resetea a un password autogenerado de
20 caracteres antes de reconstruir containers. El nuevo password queda en:

```
$LAIA_HOME/.admin-credentials      (mode 600)
```

`AGORA_ADMIN_USERNAME` / `AGORA_ADMIN_PASSWORD` también se exportan al
entorno para que los scripts `rebuild-4-first-user.sh` hagan login admin
sin más configuración.

## Post-import

Después de los rsync el destino corre, en orden:

1. `fact_reset_imported_admin_password` (reset de creds).
2. `rebuild-3-provision-agora.sh` (re-launch laia-agora con bind mounts locales).
3. `rebuild-4-first-user.sh --existing-user-only --slug <slug>` por cada usuario en `agora.db`.
4. `clone_phase_h_fix_uid_mapping` (chown a la base idmap del container).
5. `systemctl enable --now laia-pathd.service` si la unit está instalada.

`--existing-user-only` evita crear usuarios que ya existen en la `agora.db`
importada; solo reconstruye el container local y registra el agente.

## Verificación post-clone

```bash
sudo bash /opt/laia/tests/installer/vm-smoke.sh
```

El smoke valida:

- `lxc list` muestra `laia-agora` + `agent-<slug>` en `RUNNING`.
- `curl -fsS http://127.0.0.1:8088/api/health` → 200.
- `sqlite3 /srv/laia/agora/agora.db` reporta los mismos users + skills que el viejo.
- `$LAIA_HOME/.admin-credentials` existe (login admin nuevo).
- `/srv/laia/arch/config.yaml` con `laia_root: /opt/laia`.

## Recovery / re-ejecución

`laia-clone` es idempotente. Si falla a mitad:

1. **Inspecciona logs** antes de borrar nada:
   ```bash
   sudo journalctl --since "30 min ago" > /tmp/clone-fail-$(date +%s).log
   cp /tmp/build-*.log /tmp/   # builds de imágenes
   ```
2. **Re-ejecuta el mismo comando**. Si `/opt/laia` quedó parcial (versión sin
   symlink), `laia-clone` lo detecta y limpia automáticamente.
3. **Para acelerar reintentos** (`agora.db` ya copiada, etc.):
   ```bash
   sudo laia-clone --source ... --yes --resume
   ```
   `--resume` skipea el rsync de `agora.db` si la DB destino tiene ≥ 20 tablas.
4. **Rollback total** (si el snapshot del hypervisor no es opción):
   ```bash
   sudo rm -rf /opt/laia /opt/laia-v* /srv/laia /home/$USER/.laia /home/$USER/LAIA-ARCH
   ```

## Limitaciones conocidas

- **`auth.json` mode 644 dentro del container `laia-agora`**: trade-off por
  LXD unprivileged uid mapping. Mitigación futura con `raw.idmap`. En el
  host, `auth.json` sigue mode 600.
- **Cross-arch arm64 ↔ amd64**: rebuild local de containers cubre el caso.
  `clone_detect_paths` advierte si origen y destino difieren. Si tras el clone
  algo falla, lo más probable es un wheel/venv binario incompatible; `rm -rf
  /opt/laia /opt/laia-v*` y re-ejecuta sin `--skip-pip`.
- **Schema drift `agora.db`**: si origen y destino son versiones distintas del
  backend, asumimos compatibilidad. Las migraciones se aplican al startup del
  container `laia-agora`. Si falla, restaura snapshot y alinea versiones.
- **`--with-tools`**: incluye dotfiles personales (`.claude-cuenta2/`,
  `.codex/`, `.gitconfig`, etc.). NO usar en clone a producción.
- **Path rewrite no toca el viejo**: el clone es PULL no-invasivo. El
  `~/.laia/config.yaml` del origen sigue intacto.
