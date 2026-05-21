# LAIA — Migración con `laia-clone`

`laia-clone` es PULL: se ejecuta en el servidor nuevo y tira los datos desde el
servidor viejo por SSH. No usa `lxc export/import`; reconstruye containers en el
destino con su arquitectura nativa.

## Comando

```bash
curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-cloner-v2/install.sh \
  | sudo -E bash -s -- clone --source laia-hermes@viejo-server --yes --bwlimit=50M
```

Si el repo es privado:

```bash
read -rsp "GitHub token: " GITHUB_TOKEN; echo

curl -fsSL \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-cloner-v2/install.sh \
  | sudo -E LAIA_GITHUB_TOKEN="$GITHUB_TOKEN" bash -s -- clone --source laia-hermes@viejo-server --yes --bwlimit=50M
```

Si `/opt/laia` no existe en el destino, `laia-clone` ejecuta primero
`laia-install --minimal`, inicializa defaults LXD y construye las imágenes.

## Qué Transfiere

- `/srv/laia/agora/` a `/srv/laia/agora/`
- `/srv/laia/users/` a `/srv/laia/users/`
- `/srv/laia/arch/` si existe en origen
- si el origen usa layout dev, remapea `~/.laia/{workspaces,memories,cron,sessions,atlas,platforms,plugins,sandboxes,orchestrator-runs,pastes,migration,whatsapp,state.db,SOUL.md,config.yaml}` a `/srv/laia/arch/`
- `~/.laia/auth.json` y `~/.laia/.env` a `/home/laia-arch/.laia/`

Por defecto no transfiere `admin-session.json`; usa `--keep-session` si quieres
conservar esa sesión.

## Post-Import

Después del rsync, el destino ejecuta:

```bash
rebuild-3-provision-agora.sh
rebuild-4-first-user.sh --existing-user-only --slug <slug>
```

`--existing-user-only` evita crear usuarios que ya existen en la `agora.db`
importada; solo reconstruye el container local y registra el agente.

## Verificación

```bash
lxc list
curl -fsS http://127.0.0.1:8088/api/health
bash tests/installer/vm-smoke.sh
```

El destino esperado tiene `laia-agora` y los `agent-<slug>` en `RUNNING`,
marketplace poblado y login admin funcionando.
