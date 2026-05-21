# LAIA — Instalación

`laia-install` lleva un Ubuntu limpio a un factory-default vivo: código en
`/opt/laia`, datos base, LXD inicializado, `laia-agora` reconstruido localmente,
`auth.json` placeholder, admin LAIA configurado y skills base sembradas.

## Requisitos

- Ubuntu 22.04+ con kernel 5.15+.
- Arquitectura `amd64` o `arm64`.
- `sudo`, `git`, `rsync`, `python3` 3.11+, `curl`.
- 15 GB libres para imágenes y containers LXD.
- SSH saliente si luego se usará `laia-clone`.

## Instalación Factory

```bash
sudo -E laia-install --from-local /ruta/LAIA --version vX.Y.Z --yes
```

Opciones útiles:

```bash
sudo -E laia-install --minimal --yes
sudo -E laia-install --auth-file /secure/auth.json --yes
sudo -E laia-install --admin-user admin --admin-pass '...' --yes
sudo -E laia-install --init-lxd --yes
```

`--minimal` instala solo la base host y salta la Fase G. Es el modo usado por
CI y por `laia-clone` cuando debe autoinstalar el destino antes de importar.

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

- LXD ausente: usa `--init-lxd --yes` o instala manualmente con
  `sudo snap install lxd && sudo lxd init --auto`.
- `auth.json` unset: es válido para factory. Configura proveedor LLM antes del
  primer chat real.
- Rebuild de imágenes lento: es normal la primera vez; se construye con la
  arquitectura nativa del host.
