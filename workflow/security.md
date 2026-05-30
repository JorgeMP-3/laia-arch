# Security log

Bitácora de hallazgos y acciones de seguridad durante el trabajo diario en el repo.

## Cuándo escribir aquí

- Descubres una vulnerabilidad (privilege escalation, exposición de secrets, etc.).
- Rotas una credencial.
- Modificas permisos de archivos sensibles (`~/.laia/`, `/srv/laia/`, `auth.json`,
  `.env`).
- Cambias reglas de red, firewall, nginx, Cloudflare.
- Encuentras secrets hardcodeados en el repo.
- Aplicas un fix con CVE asociado en dependencias.

## Formato

```
## 2026-MM-DD — <descripción corta> (agente)

- **Tipo**: vulnerabilidad | rotación | permisos | red | secret-exposure | cve-fix
- **Severidad**: P0 (crítico) | P1 (alto) | P2 (medio) | P3 (bajo)
- **Sistema afectado**: …
- **Acción tomada**: …
- **Acción pendiente**: …
```

---

## 2026-05-30 — Tarball con secretos world-readable en el home → 0600 (claude opus 4.8 · rol Lead)

- **Tipo**: secret-exposure + permisos
- **Severidad**: P2 (medio) — exposición local en host solo-Jorge, no remota.
- **Sistema afectado**: `~/srv-laia-mirror.tgz` (mirror ad-hoc de `/srv/laia`, 4 MB) — contenía
  `auth.json` (tokens LLM), `agora.db` y `.env` en claro, en modo **644 (world-readable)**.
- **Acción tomada**: durante el declutter del home se movió a `~/archive` (→ `/mnt/data/home-archive`)
  y se aplicó **`chmod 600`**. Verificado `-rw------- laia-arch laia-arch`.
- **Acción pendiente**: evaluar si conserva valor (era safety-mirror pre-migración) o se elimina;
  si se conserva como backup, llevarlo al destino de backups con perms. Relacionado: `~/.laia/auth.json`
  sigue en **644** (agujero v1 conocido) — lo cierra C2 al migrar prod a v2 (`/srv/laia/arch/secrets`, 0600).
## 2026-05-30 — auth.json de prod: ahora COPIA en el data dir (no bind-mount) tras recuperar el outage del cutover (claude opus 4.8 · Lead)

- **Tipo**: secret-location / permisos
- **Severidad**: P3 (bajo) — funcional y aislado, pero con riesgo de drift.
- **Sistema afectado**: `/srv/laia/agora/auth.json` (= `/opt/agora/data/auth.json` dentro de `laia-agora`).
- **Acción tomada**: durante la recuperación del outage del cutover (ver `changelog.md` post-mortem),
  se quitó el device frágil `agora-auth` (bind-mount RO de `~/.laia/auth.json`) y se colocó una
  **copia real** de `auth.json` (644, owner agora `1000999:1000988`) directamente en el data dir.
  `/srv/laia/agora` es 700 → no alcanzable por otros users del host. `auth_json_ready:true`.
- **Acción pendiente**: ⚠️ **DRIFT** — `~/.laia/auth.json` ya NO es la fuente viva del container; si
  Jorge re-autentica hay que re-copiar a `/srv/laia/agora/auth.json`. Resolver en el rediseño del
  cutover (mecanismo de auth robusto, sin bind-mount anidado). `~/.laia/auth.json` sigue en 644.

## 2026-05-29 — Creds de PROD en la VM de dev `laia-dev` + token expuesto en logs (claude opus 4.8 · Coder-Opus)

- **Tipo**: secret-exposure / secret-location
- **Severidad**: P2 (medio) — el `auth.json` real de prod (`openai-codex`, tokens OAuth) se
  copió a la VM `laia-dev` y quedó **bakeado en el snapshot `b1-base`**. La VM es el sandbox
  de romper cosas: no debe llevar creds de prod. Además, durante la inspección un **fragmento
  del `access_token` real se volcó en los logs de la sesión** (bug de redacción).
- **Sistema afectado**: VM `laia-dev` (`/home/laia-arch/.laia/auth.json`, bind-mount RO en el
  `laia-agora` anidado), snapshot `b1-base`; credencial `openai-codex` de prod.
- **Acción tomada**: sustituido el `auth.json` de la VM por un **placeholder estructural**
  (tokens `DEV-PLACEHOLDER-NOT-REAL`, sin secretos), in-place (preserva inode del bind-mount).
  Borrado el snapshot `b1-base` contaminado → recreado limpio (`golden`). Verificado que
  `laia-agora` lee el placeholder y `/api/health` sigue verde. La VM queda sin creds de prod.
- **Acción pendiente (Jorge)**: **rotar/revocar la credencial `openai-codex` de prod**
  (expuesta en logs). El `auth.json` de prod en el host sigue **644** (world-readable) — su
  endurecimiento a 0600 vía `raw.idmap` es el slice **C2**, no B1.

## 2026-05-27 — `.bashrc` root-owned por el instalador + creds en /root por `sudo laia` (claude opus 4.7)

- **Tipo**: permisos
- **Severidad**: P2 (medio) — rompe acceso del usuario a su propio `.bashrc`; no expone secretos.
- **Sistema afectado**: `~/.bashrc`, `~/.cache/laia-installer.log` (HOME del admin);
  `infra/installer/lib/shell_rc.sh`.
- **Acción tomada**: reparado en disco (`sudo chown laia-arch:laia-arch`); fix en código
  (`shell_rc_restore_meta` devuelve propiedad/modo tras `mv`) + test de regresión.
- **Acción pendiente**: commitear el fix; arreglar el mismo patrón en `clone.sh`
  (artefactos root-owned `~/.laia-clone-stage/`, `~/LAIA-ARCH/.clone-state/`).

## 2026-05-27 — Credenciales del agente escritas en /root por `laia setup` con sudo (claude opus 4.7)

- **Tipo**: permisos / secret-location
- **Severidad**: P3 (bajo) — credenciales aisladas en `/root/.laia/`, no expuestas a
  otros usuarios; pero quedan huérfanas y fuera del `~/.laia` del admin.
- **Sistema afectado**: `/root/.laia/config.yaml`, `/root/.laia/auth.json` (login
  device-code de OpenAI Codex).
- **Acción tomada**: identificado que `laia`/`laia setup` NO debe correr con sudo (es
  single-user-admin); el agente debe ejecutarse como `laia-arch` usando `~/.laia/`.
- **Acción pendiente**: rehacer `laia auth`/`laia model` SIN sudo como `laia-arch`;
  borrar `/root/.laia/` huérfano.

## 2026-05-26 — Cancela split root-only de /srv/laia/arch (claude opus 4.7)

- **Tipo**: permisos
- **Severidad**: P2 (medio) — la separación pretendía elevar seguridad
  pero quedó inoperante porque los procesos consumers eran user-mode.
- **Sistema afectado**: layout de datos LAIA-ARCH (`workflow/arch-data-layout.md`).
- **Acción tomada**: tras T.14.1 toda la data de ARCH (interactiva +
  operacional) vuelve bajo `LAIA_HOME` (`~/LAIA-ARCH/`, user-owned 700).
  La zona `/srv/laia/arch/` (root:root 700) queda deprecada porque
  `laia-cli` y `laia-pathd` corren como el admin user y no podían leer
  ahí. La separación "caja fuerte vs. mesa de trabajo" del diseño
  original se reactiva el día que existan procesos privilegiados que
  justifiquen la separación.
- **Acción pendiente**: `auth.json` y `.env` siguen en `~/.laia/` por
  compat (los containers `laia-agora` bind-montean ese path via
  `rebuild-3b-fix-authjson.sh`). El script chmod 0644 sobre auth.json
  para que el agora user dentro del container (UID mapeado != laia-hermes)
  pueda leerlo — security trade-off documentado y aceptado (el host
  ~/.laia/ ya es 755 porque cualquier user del host con SSH podría leer
  el directorio).

## 2026-05-26 — Temp NOPASSWD sudo durante migración T.0-T.13 (claude opus 4.7)

- **Tipo**: permisos
- **Severidad**: P1 (alto) durante uso; revertido al final.
- **Sistema afectado**: `/etc/sudoers.d/99-laia-migration`.
- **Acción tomada**: durante el plan de migración Jorge concedió NOPASSWD
  temporal a `laia-hermes` para que claude pudiera ejecutar `sudo` sin
  TTY (el harness de Claude Code no propaga la sesión sudo entre shells).
  Fichero borrado al cierre de T.13. Verificado: `sudo -n true` falla.
- **Acción pendiente**: ninguna. Patrón a repetir solo durante operaciones
  expansas (migraciones, instalación) y revertir al cierre. No dejar
  permanente.

## 2026-05-25 — Split de datos LAIA-ARCH sensibles vs interactivos (codex)

- **Tipo**: permisos
- **Severidad**: P2 (medio)
- **Sistema afectado**: `laia-clone`, layout de datos LAIA-ARCH.
- **Acción tomada**: se separó la migración de datos legacy para que
  `workspaces`, `memories`, `skills` y `plugins` vayan a `LAIA_HOME`, mientras
  runtime sensible (`sessions`, `sandboxes`, `atlas`, `cron`, `logs`, DBs y
  config) queda en `/srv/laia/arch`.
- **Acción pendiente**: `auth.json` y `.env` siguen en el path legacy
  `~/.laia/` por compatibilidad con scripts LXD. Moverlos a `/srv/laia/arch`
  requiere una fase específica con cambios en rebuild/provision de AGORA y
  tests de auth.
