# Plan: laia-install factory-default + laia-clone install-and-import

> 📅 2026-05-19 | Claude Code Opus 4.7 | v1.0

---

## Context
Importante leer antes /home/laia-hermes/LAIA/LAIA_ECOSYSTEM.md.
El modelo de producto corregido:

- **laia-install** = instalador del producto comercial. Cuando un cliente lo ejecuta sobre un Ubuntu limpio recibe un LAIA vivo factory-default: LXD inicializado, container `laia-agora` corriendo el backend AGORA (con DB inicializada vacía), 10 base-skills sembradas en el marketplace, `auth.json` + credenciales del admin LAIA-ARCH configuradas. Listo para que el cliente acceda a la UI y empiece a dar de alta empleados. Es la historia de despliegue del producto.

- **laia-clone** = `laia-install` + importación de datos. Un solo comando que instala el sistema desde cero y importa los empleados + sus PA-AGORA containers + workspaces + tools personales de la máquina anterior. Es la herramienta de migración.

El estado actual no cumple esto: el `laia-install` de hoy deja el sistema como cáscara vacía sin LXD ni AGORA. El `laia-clone` requiere que `laia-install` haya corrido antes y solo hace rsync de datos.

La buena noticia: todo el código bootstrap ya existe en el repo (`infra/dev/laia-init.sh`, `infra/lxd/scripts/rebuild-{2,3,4}-*.sh`, `infra/dev/seed-base-skills.sh`). El trabajo es orquestación encima de las primitivas, no reescritura.

---

## Modelo de producto (LAIA_ECOSYSTEM.md)

El ecosistema tiene tres entidades que el installer/cloner debe respetar:

| Entidad | Quién | Qué ve / hace |
|---------|-------|---------------|
| **LAIA-ARCH** | Jorge | Host completo: LXD, systemd, nginx. Puede `lxc exec laia-agora` (ve el código base). Es quien ejecuta `laia-install` y `laia-clone`. Invisible para los usuarios finales. Tiene las 71 herramientas. |
| **LAIA-AGORA** | — | Agente autónomo. Es el coordinador de AGORA. No es una persona, es un modo de chat con toolset restringido (regla ⑫). Los empleados chatean con él para consultas compartidas. |
| **PA-AGORA** | Cada usuario | Su agente personal con nombre propio. Root en su container. El empleado chatea con él para tareas personales. |

**NO existe un "Admin de AGORA" como rol separado por ahora.** LAIA-ARCH gestiona la infraestructura. LAIA-AGORA coordina la plataforma. Los empleados tienen sus PA-AGORA.

- El producto es B2B: un LAIA-ARCH instala LAIA para su organización. LAIA-AGORA y los PA-AGORA hacen el resto.
- "LAIA" para los usuarios es LAIA-AGORA (el coordinador). El container interno se llama `laia-agora`.

### Qué NO incluye el factory-default

Tras `laia-install` el sistema tiene AGORA arrancado y marketplace sembrado, pero NO tiene:

- Ningún PA-AGORA dado de alta. Se crean cuando LAIA-ARCH provisiona empleados.
- Ningún workspace compartido. Se crean según la organización los necesite.
- Ningún workspace compartido. Se crean según la organización los necesite.

`rebuild-4-first-user.sh` por tanto NO se invoca en `laia-install` — solo en `laia-clone`, una vez por slug detectado en la `agora.db` importada (con un nuevo flag `--existing-user-only` que salta el `POST /api/users` porque el usuario ya está en la DB).

---

## Reglas duras del ecosistema relevantes

Estas no se negocian (de `LAIA_ECOSYSTEM.md §5`):

- **②** "LAIA" reservado para el coordinador → validación en AGORA backend, no en installer.
- **⑤** LAIA-ARCH y LAIA-AGORA son roles independientes → mantener separación en mensajes y permisos.
- **⑦** `.laia-core/` SOLO existe en host (`/opt/laia/.laia-core/`) y en container `laia-agora`. NUNCA en containers de usuario → el installer no debe meterlo en `agent-*` ni en `/srv/laia/users/`.
- **⑨** Para los usuarios, AGORA es "LAIA" a secas. En todos los mensajes user-facing usar "LAIA"; el sufijo "-AGORA" es solo dev-internal.
- **⑩** LAIA-ARCH es invisible para los usuarios → los mensajes del installer son para el admin LAIA-ARCH (operador técnico), no para el usuario final.

---

## Architectural decisions (locked)

- **auth.json**: placeholder vacío por defecto + flag `--auth-file PATH` opcional para pre-staging. Modo `--yes` se mantiene 100% no-interactivo.
- **LAIA-ARCH credentials**: env vars `LAIA_ARCH_USERNAME` / `LAIA_ARCH_PASSWORD` + flags `--admin-user` / `--admin-pass`. En modo `--yes` sin ninguno: genera admin + password aleatorio de 20 chars, lo imprime una vez por stdout, lo guarda mode-600 en `$DATA_DIR/.admin-credentials`. Estas credenciales son para que LAIA-ARCH acceda a la plataforma AGORA.
- **LXD ausente**: prompt interactivo "¿Instalo LXD ahora? [Y/n]". Si el usuario confirma o `--yes`, ejecuta `snap install lxd` + `lxd init --auto`. Si no, aborta con instrucciones claras.
- **Proveedor LLM default**: `{"provider": "unset"}` en `auth.json`. AGORA backend debe detectar "unset" y devolver error claro "configura auth antes del primer chat" en vez de 500 silencioso.
- **Arquitectura**: `inst_preflight` añade detección de `dpkg --print-architecture` (amd64 o arm64). Se guarda como `LAIA_HOST_ARCH`. Las imágenes LXD se construyen desde `images:ubuntu/22.04` (LXD resuelve a la arquitectura nativa). Los containers son ephemeral: NO se exportan/importan tarballs entre máquinas (rompe entre arm64/amd64); en su lugar se reconstruyen localmente con la arquitectura nativa del destino y se rebindean a los datos (portables porque viven en `/srv/laia/...` como bind mounts en el host).
- **Containers ephemeral** (derivada de regla ④): los datos de cada PA-AGORA viven en `/srv/laia/users/<slug>/{home,workspace,plugins}` (bind mounts del host). Los datos de AGORA viven en `/srv/laia/agora/` (incluye `agora.db` con todos los usuarios/agentes registrados) + `~/LAIA-ARCH/auth.json`. Los containers en sí no contienen estado. Esto cambia la estrategia de clone radicalmente: en vez de `lxc export/import`, se rsyncan los bind mounts y se reconstruyen los containers localmente.

---

## Naming

- **Fase G** = factory bootstrap (LXD + AGORA + skills + auth + admin). Nueva.
- **Fase H** = rsync de bind mounts (host) + rebuild local de containers en clone. Lo que el plan v1.1 llamaba "Fase E" (lxc export/import) se descarta.
- Las Fases A-D existentes no cambian.

---

## Approach

Añadir dos libs nuevas encima de las primitivas existentes — no reescribir nada.

```
infra/installer/lib/
├── common.sh        (existe)
├── sudo.sh          (existe)
├── system.sh        (existe)
├── version.sh       (existe)
├── install.sh       (existe — 22 inst_* primitivas, NO se tocan)
├── release.sh       (existe — rel_capture/restart/healthcheck, NO se tocan)
├── shell_rc.sh      (existe)
├── systemd.sh       (existe)
├── clone.sh         (existe — clone_* primitivas; SE EXTIENDE con clone_phase_h_*)
├── bootstrap.sh     (NUEVO — boot_* wrappers de los rebuild-*.sh)
└── factory.sh       (NUEVO — fact_* seeders de auth/admin/skills/templates)
```

`bin/laia-install` orquesta: bare-infra (Fase B existente) → bootstrap (Fase G) → factory (Fase G) → summary.

`bin/laia-clone` orquesta: si `/opt/laia` no existe → invoca `laia-install` primero → continúa con clone phases (Fases D + H).

`--minimal` flag en `laia-install` es la válvula de escape crítica: salta Fase G y mantiene el comportamiento Fase B actual. Los 226 tests existentes corren con `--minimal` (o equivalente vía override-mode) y siguen verdes.

---

## Work Packages

### WP1 — bootstrap.sh (Agent A, sin dependencias)

Wrappers de los rebuild-* existentes. Cada función `boot_*` ≈ 30 líneas: log header, gate de override-mode, exec del script, surface exit code.

**Funciones:**

- `boot_detect_arch` — primero de todo. `LAIA_HOST_ARCH="$(dpkg --print-architecture)"` (amd64 / arm64 / etc). Si no es amd64 ni arm64 → die con error claro "arquitectura no soportada". Export como global. Los tests pueden mockear con `LAIA_HOST_ARCH_OVERRIDE`.
- `boot_check_lxd_installed` — `command -v lxc` + `lxc remote list`. Si falla: en modo `--yes` (sin TTY) → exec `snap install lxd && lxd init --auto`. Con TTY → confirm "¿Instalo LXD ahora?" y si afirmativo lo mismo. Si rechaza → die con instrucciones.
- `boot_init_defaults` — wrap `infra/lxd/scripts/init-defaults.sh`.
- `boot_build_images` — wrap `infra/lxd/scripts/rebuild-2-images.sh`. Idempotente: skip si `lxc image list | grep -q laia-agora-base`. La imagen base se construye con `images:ubuntu/22.04` que LXD resuelve a la arquitectura nativa (`LAIA_HOST_ARCH`). Cross-arch nota: en clone, el destino reconstruye con su propia arch; los datos importados son portables.
- `boot_provision_agora` — wrap `infra/lxd/scripts/rebuild-3-provision-agora.sh`. Idempotente: skip body pero re-bind mounts si container existe. Crítico: el bind mount `/srv/laia/agora/ → /opt/agora/data` significa que la `agora.db` vive en el host, no en el container.
- `boot_wait_for_agora_health` — poll `http://127.0.0.1:8088/api/health` con timeout (reusa `rel_healthcheck` de `release.sh`).

**Override-mode gate:** cuando `inst_is_override_mode` es true OR `LAIA_TEST_STUB_PATH=1`, cada `boot_*` short-circuita con `log_info "[stub] skipping boot_X"` y devuelve 0.

**Acceptance criteria:** `bash -n` pasa; `test_lib_bootstrap.sh` ≥10 asserts pasa en override; con stubs (WP4) las invocaciones se registran en orden correcto.

---

### WP2 — factory.sh (Agent B, depende de WP1)

**Funciones:**

- `fact_seed_cli_config` — copia `.laia-core/cli-config.yaml.example → $DATA_DIR/cli-config.yaml` si falta (nunca sobreescribe). Misma lógica para `.env.example`.
- `fact_seed_authjson` — si `$OPT_AUTH_FILE` está set y existe → `cp -a` al destino. Si no → escribe `{"provider": "unset", "instructions": "Configure via UI or 'laia auth'"}` mode 600.
- `fact_seed_admin_user` — siembra el usuario LAIA-ARCH en AGORA. Resuelve username/password en este orden: flags `--admin-user/--admin-pass` → env vars `LAIA_ARCH_USERNAME/LAIA_ARCH_PASSWORD` → en modo `--yes` autogen admin + password 20-char (`openssl rand -base64 20`) → en modo interactivo, `read` con prompt. Persistencia: `POST` a `http://127.0.0.1:8088/admin/users` (desde el host). Imprime el password una vez por stdout y lo escribe mode-600 a `$DATA_DIR/.admin-credentials`.
- `fact_seed_base_skills` — wrap `infra/dev/seed-base-skills.sh`.
- `fact_persist_env_to_container` — port del bloque `ENV_HOST_FILE` de `infra/dev/laia-init.sh` líneas ~190-209 (Telegram, futuros secretos) a función reusable.

**Acceptance criteria:** `test_lib_factory.sh` cubre los 5 paths de `auth.json`, los 4 paths de admin creds, idempotencia (re-correr no sobreescribe), placeholders cuando faltan flags.

---

### WP3 — bin/laia-install glue (Agent C, depende de WP1+WP2)

**Cambios en `bin/laia-install`:**

1. Source new libs: `source "$LIB_DIR/bootstrap.sh"` + `source "$LIB_DIR/factory.sh"`
2. Nuevos flags:
   - `--minimal` — salta Fase G. Modo para CI y tests existentes.
   - `--auth-file PATH` — pre-stage de `auth.json`.
   - `--admin-user USER` / `--admin-pass PASS` — credenciales admin.
   - `--init-lxd` — fuerza instalación automática de LXD si falta (skip prompt).
3. `main()` extendido — después de `inst_print_summary` añadir Fase G con las funciones de bootstrap + factory.

**Acceptance criteria:** los 226 tests existentes siguen verdes en modo `--minimal`. `test_install_factory.sh` valida secuencia completa contra stubs.

---

### WP4 — Test stubs `tests/installer/_stubs/` (Agent A o D, sin dependencias)

Stub scripts para `lxc`, `lxd`, `snap`, `curl`. Cada uno:
- Registra invocación a `$LAIA_TEST_STUB_LOG`.
- Devuelve output canned predecible.
- Activación: `export LAIA_TEST_STUB_PATH=$REPO/tests/installer/_stubs && export PATH="$LAIA_TEST_STUB_PATH:$PATH"`.

**Acceptance criteria:** `bash tests/installer/_stubs/lxc --version` corre; con stubs en PATH, un `boot_init_defaults` real registra invocación correcta sin tocar el LXD del host.

---

### WP5 — bin/laia-clone install-first + Fase H (Agent D, depende de WP3)

**Cambio crítico de estrategia:** la versión previa de Fase H usaba `lxc export` + rsync de tarballs + `lxc import`. Esto se descarta porque:
- Bloquea el cruce arquitectural arm64 ↔ amd64 (tarballs son arch-specific).
- Es innecesario: por regla ④ los datos viven en bind mounts del host, no dentro del container.
- Los containers son ephemeral.

**Nueva estrategia:** rsync de los bind mounts + rebuild local de containers.

**Dos cambios en `bin/laia-clone`:**

1. **Install-first lógica** al inicio de `main()` (después de `parse_args`): si no existe `/opt/laia`, invoca `laia-install --minimal` + `boot_init_defaults` + `boot_build_images`.

2. **Fase H** — rsync bind mounts + rebuild local:
   - `clone_phase_h_rsync_agora_data` — rsync de `<source>:/srv/laia/agora/ → local /srv/laia/agora/`. Con `--numeric-ids`.
   - `clone_phase_h_rsync_users_data` — extiende `clone_phase3_users` para rsync recursivo de `/srv/laia/users/`.
   - `clone_phase_h_enumerate_slugs` — lee `agora.db` importada y extrae lista de slugs.
   - `clone_phase_h_rebuild_agora_container` — invoca `rebuild-3-provision-agora.sh`.
   - `clone_phase_h_rebuild_agent_container <slug>` — invoca `rebuild-4-first-user.sh` con `--existing-user-only`.
   - `clone_phase_h_fix_uid_mapping` — `chown` según idmap del destino.
   - `clone_phase_h_verify` — `lxc list` + health check + lista de slugs.

**Nuevo flag `--existing-user-only` en `rebuild-4-first-user.sh`:** salta el `POST /api/users` y solo crea el container. El usuario ya está en la DB importada.

**Acceptance criteria:** `test_clone_with_install.sh` y `test_clone_phase_h.sh` validan el flujo contra stubs. Cross-arch test manual en VM real.

---

### WP6 — Test suites nuevas (Agent B o E, ramp paralelo)

En `tests/installer/`:

| Archivo | Cobertura | Asserts target |
|---------|-----------|----------------|
| `test_lib_bootstrap.sh` | override short-circuit + stub invocation order | ~15 |
| `test_lib_factory.sh` | 5 paths auth.json + 4 paths admin creds + idempotencia | ~25 |
| `test_install_factory.sh` | install end-to-end con stubs, valida orden Fase G | ~20 |
| `test_install_minimal.sh` | `--minimal` NO ejecuta boot_*/fact_* (regression guard) | ~10 |
| `test_clone_with_install.sh` | clone sin install previo invoca install --minimal | ~10 |
| `test_clone_phase_h.sh` | rsync bind mounts + rebuild local con stubs | ~15 |

**Total nuevo: ~95 asserts.** Combinado con los 226 existentes → ~320 asserts.

---

### WP7 — Docs + real-VM smoke (Agent E, último)

- `docs/INSTALL.md` (nuevo) — pública. Pre-requisitos, one-liner, troubleshooting.
- `docs/CLONE.md` (nuevo) — pública. Caso migración, `--with-tools`, `--bwlimit` para WAN.
- `docs/RELEASE.md` (nuevo) — interno. Cómo taggear y soltar.
- `LAIA_ECOSYSTEM.md §8` actualizado con paths definitivos + flujo install/clone.
- `--help` de cada `bin/laia-*` actualizado.
- `tests/installer/vm-smoke.sh` (nuevo) — requiere VM real, flujo end-to-end no-stubbed.

---

## Critical files

### Nuevos
- `infra/installer/lib/bootstrap.sh`
- `infra/installer/lib/factory.sh`
- `tests/installer/_stubs/{lxc,lxd,snap,curl}` (4 stubs)
- `tests/installer/test_lib_bootstrap.sh`
- `tests/installer/test_lib_factory.sh`
- `tests/installer/test_install_factory.sh`
- `tests/installer/test_install_minimal.sh`
- `tests/installer/test_clone_with_install.sh`
- `tests/installer/test_clone_phase_h.sh`
- `tests/installer/vm-smoke.sh`
- `docs/INSTALL.md`
- `docs/CLONE.md`
- `docs/RELEASE.md`

### Modificados
- `bin/laia-install` (añade Fase G glue + flags)
- `bin/laia-clone` (install-first + Fase H phases)
- `infra/installer/lib/clone.sh` (añade clone_phase_h_*; extiende clone_phase3_users)
- `infra/installer/lib/install.sh` (añade arch detection en inst_preflight: LAIA_HOST_ARCH)
- `infra/lxd/scripts/rebuild-4-first-user.sh` (añade flag `--existing-user-only`)
- `LAIA_ECOSYSTEM.md §8` (paths definitivos)

---

## Funciones existentes a reutilizar (no reescribir)

- `infra/installer/lib/install.sh` — las 22 `inst_*` primitivas sin cambios
- `infra/installer/lib/release.sh::rel_healthcheck` — reusar en `boot_wait_for_agora_health`
- `infra/lxd/scripts/init-defaults.sh` — wrap
- `infra/lxd/scripts/rebuild-2-images.sh` — wrap
- `infra/lxd/scripts/rebuild-3-provision-agora.sh` — wrap
- `infra/dev/seed-base-skills.sh` — wrap
- `infra/dev/laia-init.sh` líneas 165-168 — port lógica a `fact_seed_admin_user`
- `.laia-core/cli-config.yaml.example` — copy template
- `.laia-core/.env.example` — copy template

---

## Recommended execution order

```
Hour 0:  Agent A → WP1 (bootstrap.sh)        [parallel]
         Agent D → WP4 (stubs)               [parallel]
         Agent E → WP7 docs scaffolding      [parallel, prose only]

Hour 3:  Agent B → WP2 (factory.sh)          [depende de WP1]
         Agent A → WP6 test_lib_bootstrap.sh [paralelo con B]

Hour 6:  Agent C → WP3 (laia-install glue)   [depende de WP1+WP2]
         Agent B → WP6 test_lib_factory.sh

Hour 9:  Agent D → WP5 (clone refactor + H)  [depende de WP3]
         Agent C → WP6 test_install_*.sh

Hour 12: Agent D → WP6 test_clone_*.sh
         Agent E → WP7 real-VM smoke
         Commit + PR boundaries en cada WP completado
```

**Invariante:** los 226 tests existentes deben seguir verdes. WP4 (stubs) + flag `--minimal` son las herramientas para ello.

---

## Riesgos identificados

| Riesgo | Mitigación |
|--------|-----------|
| AGORA backend health post-boot tarda 60-90s | `boot_wait_for_agora_health` usa timeout 120s y diferencia "no responde aún" de "respondió mal" |
| `rebuild-2-images.sh` tarda 10-15 min sin progreso visible | WP1 debe asegurar que `boot_build_images` no redirige stdout a `/dev/null`. Crítico en primera ejecución cross-arch |
| Credenciales autogeneradas se imprimen UNA VEZ | Dejar el path `.admin-credentials` muy visible en el summary final |
| UID mapping cross-host tras rsync | `clone_phase_h_fix_uid_mapping` resuelve via `chown` explícito. Test en VM real cross-arch |
| Schema drift de `agora.db` entre versiones de LAIA | Documentar en `docs/CLONE.md` que origen y destino deben ser misma versión. Validar en `clone_preflight` |
| `docs/INSTALL.md` es copy comercial | Revisión humana por Jorge o revisor antes del merge |
| Slug inválido en DB importada | Pre-flight valida slugs antes de crear containers |

---

## Verificación end-to-end

1. **Tests unitarios:** `for t in tests/installer/test_*.sh; do bash "$t"; done` — 9 viejos + 6 nuevos. ~320 asserts.
2. **Stub-based integration:** con `LAIA_TEST_STUB_PATH` activo, `laia-install --yes --from-local $REPO --version v0.0.0-test` corre Fase G completa sin tocar LXD real.
3. **Override-mode regression:** cada test viejo sigue verde.
4. **VM real (manual):** `bash tests/installer/vm-smoke.sh laia-test` — lanza Multipass VM, verifica health, skills, admin-credentials, auth.json "unset".
5. **Clone real (manual):** segunda VM, `laia-clone --source-dir /mnt/snapshot --yes --with-tools` — verifica containers importados y smoke.
6. **Migración real a producción:** `laia-clone laia-hermes@<host>` contra servidor de producción real.

---

> 📅 Plan v1.0 — 2026-05-19 | Claude Code Opus 4.7
