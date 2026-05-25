# LAIA — Instalación

`laia-install` lleva un Ubuntu limpio a un factory-default vivo: código en
`/opt/laia`, datos base, LXD inicializado, `laia-agora` reconstruido localmente,
`auth.json` placeholder, admin LAIA configurado y skills base sembradas.

## Requisitos

- Ubuntu 22.04+ con kernel 5.15+.
- Arquitectura `amd64` o `arm64`.
- `sudo`, `git`, `rsync`, `python3` 3.11+, `sqlite3`, `curl`.
- 15 GB libres para imágenes y containers LXD.
- SSH saliente si luego se usará `laia-clone`.

`install.sh` instala automáticamente cualquiera de los prerequisitos
faltantes vía `apt-get` cuando se ejecuta como root.

## Instalación Factory Desde GitHub

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo bash -s -- --mode install --yes
```

Opciones útiles:

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo bash -s -- --mode install --yes -- --minimal

curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo bash -s -- --mode install --yes -- --auth-file /secure/auth.json

curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo bash -s -- --mode install --yes -- --admin-user admin --admin-pass '...'
```

`--minimal` instala solo la base host y salta la Fase G. Es el modo usado por
CI y por `laia-clone` cuando debe autoinstalar el destino antes de importar.

Para probar una rama distinta:

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/main/install.sh \
  | sudo -E LAIA_BRANCH=main bash -s -- install --yes
```

## Repo Privado

Si `JorgeMP-3/laia-arch` es privado, usa un GitHub token con permiso
`Contents: read` sobre ese repo:

```bash
read -rsp "GitHub token: " GITHUB_TOKEN; echo

curl -fsSL \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
  | sudo LAIA_GITHUB_TOKEN="$GITHUB_TOKEN" bash -s -- --mode install --yes
```

## Credenciales

En `--yes`, si no pasas `--admin-user/--admin-pass` ni
`LAIA_ARCH_USERNAME/LAIA_ARCH_PASSWORD`, el instalador crea:

- usuario `admin`
- password aleatorio de 20 caracteres
- copia mode 600 en `$LAIA_HOME/.admin-credentials`

El password se imprime una sola vez por stdout.

## Verificación

```bash
lxc list
curl -fsS http://127.0.0.1:8088/api/health
```

El resultado esperado es `laia-agora` en `RUNNING` y `/api/health` con HTTP 200.

## Troubleshooting

- **LXD ausente**: usa `--init-lxd --yes` o instala manualmente con
  `sudo snap install lxd && sudo lxd init --auto`.
- **`auth.json` unset**: es válido para factory. Configura proveedor LLM antes del
  primer chat real.
- **Rebuild de imágenes lento (10-20 min)**: es normal la primera vez; se
  construye con la arquitectura nativa del host. El instalador emite un
  heartbeat cada 60s y tee'a a `/tmp/build-{base,agora}.log`. Si quieres
  silenciar, `LAIA_BUILD_QUIET=1`. Si parece colgado:
  ```bash
  tail -f /tmp/build-base.log /tmp/build-agora.log
  ```
- **Snap install lxd cuelga 5+ min**: la primera vez `snap install` puede
  tardar. Revisa `sudo journalctl -u snapd -n 50` en otro shell.
- **`sqlite3` not installed**: requerido por el clone-time admin reset.
  `apt-get install -y sqlite3`.

## Limitaciones conocidas

- **Container `laia-agora` ve `auth.json` con mode 644**: trade-off por LXD
  unprivileged uid mapping. En el host sigue mode 600.
- **Cross-arch**: los containers se reconstruyen locales en el destino con la
  arquitectura nativa; el `.venv` del host se recrea (a menos que se pase
  `--skip-pip`).
- **Schema drift `agora.db`**: si reinstalas sobre datos antiguos, asegúrate
  de que la versión del backend en `/opt/laia/services/agora-backend` aplica
  las migraciones en el startup del container (es el comportamiento default).
