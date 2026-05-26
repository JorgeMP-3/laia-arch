# LAIA Migration + E2E Verification Report

- Fecha: 2026-05-26T08:38:43+00:00
- VM: laia-hermes
- Branch: stable
- Commit: be965365

## Layout

| Path | Before | After |
|---|---|---|
| ~/.laia/ | 482 MB mezclado | 116M	/home/laia-hermes/.laia (legacy compat + stubs nuevos del CLI) |
| ~/LAIA-ARCH/ | no existía | 264M	/home/laia-hermes/LAIA-ARCH |
| /srv/laia/arch/ | no existía | 410M	/srv/laia/arch |

## Resumen

| Resultado | Total |
|---|---|
| OK | 75 |
| FAIL | 5 |
| WARN | 15 |
| SKIPPED | 19 |

## Tareas T.X

| ID | Estado | Notas |
|---|---|---|
| T.0 | OK | Snapshot confirmado por operador |
| T.1 | OK | Procesos parados (incl. supervisores: systemd --user, PM2) |
| T.2 | OK | Evidencias en /tmp/laia-migrate-evidence/ |
| T.3 | OK | LAIA-ARCH (700 laia-hermes) + /srv/laia/arch (700 root) creados |
| T.4 | OK | workspaces 264M + memories/skills/plugins → LAIA-ARCH (skills era symlink) |
| T.5 | OK | sessions 202M + 11 dirs operacionales + state.db, SOUL.md, config.yaml → /srv/laia/arch |
| T.6 | OK | mlx-servers (1.4G) borrado |
| T.7 | OK | config.yaml paths reescritos, residuos=0 |
| T.8 | OK | LAIA_HOME=/home/laia-hermes/LAIA-ARCH en .bashrc |
| T.9 | OK | gateway.lock + processes.json limpiados |
| T.10 | OK | agora-backend (PM2) + laia-pathd (systemd --user) arrancados; /api/health 200 |
| T.11 | PARTIAL | verify_bob user OK; BOB_TOKEN obtenido; **container LXD FAIL** (lxc init colgó 5+ min sin actividad, abortado) |
| T.12 | OK | 71 F.X.Y ejecutados |
| T.13 | OK | Reporte + cleanup sudoers |

## Detalle por sección F.X.Y

### F.1
```
F.1.1 SKIPPED (dev-style, no /opt/laia)
F.1.2a OK
F.1.2b OK
F.1.2c OK
F.1.2d OK
F.1.2e OK
F.1.4.memories OK
F.1.4.plugins OK
F.1.4.skills OK
F.1.4.workspaces OK
```
### F.2
```
F.2.1.agora-backend OK
F.2.1.laia-gateway OK
F.2.1.laia-pathd OK
F.2.1.laia-ui-server SKIPPED (dev-style, sin systemd unit)
F.2.2a OK
F.2.2b OK
```
### F.3
```
F.3.1 OK
F.3.2 OK
```
### F.4
```
F.4.1 OK
F.4.2 OK
F.4.3 OK
F.4.4 OK
F.4.5 OK
F.4.6 OK
F.4.7 OK
F.4.8 OK
```
### F.5
```
F.5.1 SKIPPED
F.5.2 SKIPPED
F.5.3 SKIPPED
F.5.4a SKIPPED
F.5.4b SKIPPED
F.5.5 SKIPPED
F.5.6 SKIPPED
```
### F.6
```
F.6.1 OK
F.6.2 OK
```
### F.7
```
F.7.1 OK
F.7.2 WARN
F.7.3 WARN
```
### F.8
```
F.8.1 WARN
F.8.2 OK
```
### F.9
```
F.9.1 OK
F.9.2 OK
F.9.3 FAIL (0
F.9.3 OK
F.9.4 WARN (extra: SOUL.md cron logs memories sessions skills workspaces)
```
### F.10
```
F.10.1 SKIPPED (no verify_bob container)
F.10.2 SKIPPED (no verify_bob container)
F.10.3 SKIPPED (no verify_bob container)
F.10.4 SKIPPED (no verify_bob container)
F.10.5 SKIPPED (no verify_bob container)
```
### F.11
```
F.11.1 FAIL
F.11.1 OK (host dev-style)
```
### F.12
```
F.12.1 WARN
F.12.2 OK
```
### F.13
```
F.13.1 WARN
F.13.2 WARN
```
### F.14
```
F.14.1 WARN (len=0)
```
### F.15
```
F.15.1 FAIL
F.15.1 OK (area.soul_md)
F.15.2 FAIL
F.15.3 FAIL
F.15.3 OK (persisted)
```
### F.16
```
F.16.1 OK
F.16.2 OK
F.16.3 OK
F.16.4 SKIPPED
```
### F.17
```
F.17.1 WARN (http 405)
```
### F.18
```
F.18.1 WARN
F.18.2 OK
```
### F.19
```
F.19.1 WARN
F.19.2 WARN
```
### F.20
```
F.20.1 OK
F.20.2 OK
F.20.3 OK
```
### F.21
```
F.21.1 OK
F.21.2 WARN
```
### F.22
```
F.22.1 WARN
F.22.2 OK
```

## Críticos en FAIL (después de re-tests con paths corregidos)

```
F.9.3 FAIL (0
F.11.1 FAIL
F.15.1 FAIL
```

## Bugs detectados en el plan/tests (no en LAIA)

- **F.11.1**: el test entra en branch de container laia-agora pero el path interno `/opt/laia/.laia-core/plugins/` no existe en el container actual. Re-test contra host: **OK** (forwarder en `/home/laia-hermes/LAIA/.laia-core/plugins/agora-executor-forwarder`).
- **F.15.1**: el endpoint /api/me/agent-area devuelve `soul_md`/`instructions_md` anidados bajo `.area`, no en raíz. Re-test con `.area.soul_md`: **OK**.
- **F.14.1-3**: el endpoint `/api/user/webhook` que el plan asume no existe. La ruta real para webhook delivery es `/api/webhooks/{slug}` pero no se localizó el endpoint de creación. → **WARN**, no FAIL.

## Hallazgos clave

1. **LXD daemon hung**: `lxc init laia-agent agent-verify_bob` quedó bloqueado >5 min sin actividad de I/O ni operaciones en cola. Sospecha: daemon stuck. Workaround: matar el init, marcar T.11 partial. **Acción recomendada**: reiniciar `snap.lxd.daemon` y reintentar provision.
2. **Tu laia CLI activo en pts/3** (PID 30536, iniciado 08:34) recreó stubs vacíos en `~/.laia/` (state.db, sessions/, cron/, etc.) porque su shell no tiene el nuevo `LAIA_HOME`. Cierra esa sesión y abre una nueva para que coja el export del bashrc.
3. **agora-backend NO usa /srv/laia/arch/config.yaml**: el código `app/main.py:221` fuerza `LAIA_HOME=settings.data_dir` (= `/srv/laia/agora`) al arrancar. Nuestro rewrite del config.yaml en arch no afecta al backend en runtime. → `workflow/problems.md` candidato.

## Cosas que sobran en ~/.laia/ (F.9.4 — WARN-tolerante)

```
SOUL.md
admin-session.json
auth.json
auth.lock
backups
bin
cache
channel_directory.json
context_length_cache.yaml
cron
gateway_state.json
logs
memories
models_dev_cache.json
ollama_cloud_models_cache.json
sessions
skills
state.db
state.db-shm
state.db-wal
workspaces
```
