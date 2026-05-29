# Plan: Auditoría Profunda y Corrección del Ecosistema LAIA

> **Para Claude Code (Opus):** Este documento lista TODOS los problemas encontrados en el servidor.
> Yo (OpenCode) soy limitado — por favor verifica cada problema antes de actuar.
> Para cada problema: descripción + hipótesis + solución(s).

---

## 1. REGISTRO ATLAS.YAML — Problemas

### P1.1: `jorge_container` apunta a `agent-jorge` que no existe

- **Descripción**: `atlas.yaml` línea 224 dice `value: agent-jorge`. El container `agent-jorge` NO existe en LXD.
- **Realidad**: El container correcto es `agent-jorge-dev` (corre en 10.99.0.163, tiene `laia-executor` dentro).
- **Impacto**: `atlas get jorge_container` devuelve `agent-jorge` — un nombre que no resuelve en LXD.
- **Solución**: Cambiar `value: agent-jorge` → `value: agent-jorge-dev` en atlas.yaml.

### P1.2: `executor_api.host` apunta a `agent-jorge` que no existe

- **Descripción**: atlas.yaml línea 166-167: `host: agent-jorge`, `port: 9091`.
- **Realidad**: `agent-jorge-dev` es el container que corre el executor en 9091.
- **Impacto**: `atlas check executor_api` siempre falla con "name resolution failed".
- **Solución**: Cambiar `host: agent-jorge` → `host: agent-jorge-dev` en atlas.yaml.

### P1.3: `laia_root` usa `~/LAIA` (tilde) en lugar de path absoluto

- **Descripción**: atlas.yaml línea 18: `value: ~/LAIA`
- **Realidad**: La shell de atlas resuelve esto a `/home/laia-arch/LAIA` (por el usuario actual), pero en contexto de Python dentro del container o servicios, la tilde puede no resolver.
- **Impacto**: Posible inconsistencia si alguien corre atlas desde otro usuario o contexto.
- **Solución**: Cambiar `value: ~/LAIA` → `value: /home/laia-arch/LAIA` para evitar dependencia del shell.

### P1.4: `srv_laia` usa `/srv/laia` pero el directory listing muestra `drwxr-xr-x 4 root root 4096 May 26 14:51 .`

- **Descripción**: `/srv/laia` pertenece a `root:root` con permisos `drwxr-xr-x`.
- **Realidad**: El directorio existe y tiene subdirectorios `agora` y `users` (ambos vacíos o sin acceso por permisos).
- **Impacto**: Baja — es intencional que sea root-owned. Pero `agora_env` no existe porque falta `sudo` para crearlo.
- **Solución**: Crear el directorio con los permisos correctos si se necesita.

### P1.5: `executor_api` está marcado `optional: true` pero ES el servicio principal de Jorge

- **Descripción**: El executor de Jorge es el servicio más importante para su workflow.
- **Impacto**: Al ser `optional`, `atlas doctor` lo ignora silenciosamente.
- **Solución**: Quitar `optional: true` de `executor_api` ahora que `agent-jorge-dev` está corriendo.

---

## 2. GIT — Problemas

### P2.1: `bin/atlas.py` sin trackear (fichero suelto)

- **Descripción**: Existe `bin/atlas.py` (copia del `bin/atlas`) sin rastrear en git.
- **Impacto**: Confusión — podría ser una versión antigua o backup accidental.
- **Solución**: Borrar `bin/atlas.py` (el CLI correcto es `bin/atlas`).

### P2.2: `skills/.curator_state` modificado

- **Descripción**: 5 líneas cambiadas, no staged.
- **Impacto**: Relevante solo si hay skill de curaduría activa.
- **Solución**: Revisar qué cambió y hacer `git add` o `git restore` según corresponda.

### P2.3: Commits directos a `main` en lugar de branch `wip/`

- **Descripción**: Los commits `f7d7d3c6`, `4c873690`, `28a47d02` están en `main` directamente (no vía PR).
- **Impacto**: Violación de las reglas de git de LAIA.
- **Solución**: Para cambios futuros, usar branches `wip/<agente>/<tarea>`. No reescribir historial de `main` ya mergeado.

---

## 3. SERVICIOS Y PUERTOS — Problemas de Inventario

### P3.1: Confusión sobre qué servicio está en cada puerto

**Inventario real del servidor:**

| Puerto | Servicio | Propietario | Estado |
|--------|----------|-------------|--------|
| 80 | Nextcloud Apache (snap) | root | ✅ Funcionando |
| 3000 | Wekan (Kanban, Meteor) | root (snap) | ✅ Funcionando |
| 8080 | signal-cli HTTP daemon | ? | ✅ Funcionando |
| 8088 | agora-api (uvicorn :8000 en container laia-agora) | agora (container) | ✅ NAT funciona |
| 35005 | ??? — listener pero empty reply | ? | ❓ Investigar |
| 35041 | VS Code Server extension host | laia-arch | ✅ Normal |
| 27017 | MongoDB (Rocketchat) | root | ✅ Funcionando |
| 27019 | MongoDB (Wekan) | root (snap) | ✅ Funcionando |
| 5002 | TTS daemon (Python) | root | ✅ Funcionando |
| 9277 | oz-v0.2026.05.20 (OpenVoice/WARP daemon) | laia-arch | ✅ Normal |
| 36599, 43313 | VS Code Server bridges | laia-arch | ✅ Normal |

**Puertos en el container `laia-agora`:**

| Puerto interno | Servicio |
|--------|----------|
| 8000 | uvicorn (agora-backend FastAPI) |
| ? | nginx? |

**Puertos en el container `agent-jorge-dev`:**

| Puerto interno | Servicio |
|--------|----------|
| 9091 | laia-executor (FastAPI) |

### P3.2: Puerto 35005 sin identificar

- **Descripción**: `*:35005` listening pero curl devuelve empty reply.
- **Hipótesis**: Puede ser un servicio viejo de LAIA que quedó colgado, un metrics endpoint, o Redis/Sidekiq.
- **Solución**: Investigar con `ss -tlnp` para obtener el PID y luego `ps -p <PID>` para ver el proceso.

### P3.3: `agora_api` está en `:8088` pero atlas.yaml lo describe como `http://127.0.0.1:8088`

- **Descripción**: El servicio real está en puerto 8000 dentro del container y NATado a 8088 en el host.
- **Impacto**: Ninguno — funciona correctamente.
- **Nota**: Debería documentar en la descripción que es NATado del container.

### P3.4: nginx en el host no está configurado para LAIA

- **Descripción**: El nginx de `infra/nginx/` NO está instalado en el sistema. El puerto 80 lo ocupa Nextcloud.
- **Impacto**: La configuración de nginx de LAIA en `infra/nginx/` no está deployada.
- **Solución**: Si se quiere servir LAIA por nginx, desplegar la config.

---

## 4. CONTENEDORES LXD — Problemas

### P4.1: `jorge_container` en atlas apunta a nombre antiguo

- **Solución**: Ya cubierta en P1.1 — cambiar a `agent-jorge-dev`.

### P4.2: No existe container `agent-verify-bob` ni `agent-verify-carol` en atlas

- **Descripción**: Estos containers existen y corren, pero NO están en atlas.yaml.
- **Impacto**: No hay referencia en Atlas para ellos. Si alguien los necesita, no tiene forma de resolver su IP.
- **Solución**: Añadir `bob_container` y `carol_container` a atlas.yaml si son relevantes para el sistema.

### P4.3: `/opt/laia` vs `/home/laia-arch/LAIA` — confusión de versiones

- **Descripción**: `/opt/laia` tiene `VERSION v0.11.0` y `.laia-core`. El dev repo en `/home/laia-arch/LAIA` es la versión en desarrollo.
- **Impacto**: El container `laia-agora` usa `/opt/laia` (producción). El host usa `/home/laia-arch/LAIA` (desarrollo). Son是两个 cosas distintas.
- **Solución**: Ninguna por ahora — es intencional. Pero debería estar documentado.

---

## 5. SEGURIDAD — Problemas Potenciales

### P5.1: `agora_env` no existe pero tiene secrets

- **Descripción**: `/srv/laia/agora/.env` no existe (ni el directorio `agora` tiene acceso).
- **Impacto**: Si alguien despliega agora-backend, no tendrá secrets. Pero el container `laia-agora` SÍ tiene su propia copia interna de `.env`.
- **Solución**: Crear el directorio y `.env` con las keys placeholder. Asegurar que `sudo` se usa para crear porque `/srv/laia` es root.

### P5.2: `.env.paths` en `~/.laia/` — verificar que no tenga secrets

- **Descripción**: Existe `/home/laia-arch/.laia/.env.paths` (5305 bytes).
- **Impacto**: Si contiene secrets en texto plano, es un riesgo.
- **Solución**: Revisar el contenido.

### P5.3: `auth.json` en `~/.laia/` — verificar que no tenga secrets sensibles

- **Descripción**: Existe `/home/laia-arch/.laia/auth.json` (10403 bytes).
- **Impacto**: Posible almacenamiento de credenciales.
- **Solución**: Revisar que no sea un secreto sensible.

---

## 6. `bin/atlas visualize` — Problemas

### P6.1: Mermaid muestra "Syntax error in text"

- **Descripción**: El HTML generado tiene datos correctos (35 nodes, 16 edges) pero Mermaid v11 no logra renderizar.
- **Causa probable**: La sintaxis Mermaid generada es incompatible con v11. Específicamente: `classDef` + `class` statements dentro de `subgraph` puede no funcionar igual en v11 que en versiones anteriores.
- **Estado**: El plan está en `workflow/plans/atlas-visualize-fix.md` con las hipótesis.
- **Solución sugerida**:
  1. Simplificar el grafo: quitar `classDef` y `class` statements, usar nodos simples sin estilos.
  2. Cambiar de Mermaid a D3.js o Cytoscape.js para el grafo (renderizado 100% autocontenido).
  3. O usar una versión específica de Mermaid que se sepa que funciona (ej. `@10`).

### P6.2: `--no-open` no funciona

- **Descripción**: `atlas visualize --no-open` debería escribir el HTML sin abrir el navegador, pero siempre abre.
- **Causa**: El código tiene `getattr(args, "open", False)` pero `action="store_false"` pone `False` por defecto, y la lógica no lo maneja correctamente.
- **Solución**: Revisar el argumento `--no-open` en `cmd_visualize()`.

---

## 7. `infra/pathd/` — Problemas

### P7.1: `laia-pathd` daemon no está corriendo ni instalado

- **Descripción**: No existe `systemctl --user laia-pathd`. El socket `pathd.sock` no existe.
- **Impacto**: Ninguno en la práctica — atlas funciona sin el daemon (usa `laia_paths.py` como fallback).
- **Solución**: Solo instalar si se necesita el daemon para múltiples clientespath resolution en tiempo real.

### P7.2: `infra/scripts/deploy-agora.sh` y otros scripts — revisar hardcoded paths

- **Descripción**: Los scripts de `infra/scripts/` deberían usar `atlas get` en lugar de paths hardcoded.
- **Impacto**: Si los paths cambian, los scripts rompen.
- **Solución**: Migrar los scripts a usar `atlas get` o `$(atlas get <ref>)`.

---

## 8. TESTS — Problemas

### P8.1: Tests referencing old container names

- **Descripción**: `tests/test_create_agent_naming.sh` y `tests/test_rebuild_state.sh` referencian `agent-jorge-dev` y `agent-jorge`.
- **Impacto**: Los tests pueden estar rotos o ser inválidos.
- **Solución**: Verificar que los tests pasan.

---

## 9. FICHeros sin investigar

### F9.1: `bin/atlas.py` (copia suelta de `bin/atlas`)

- **Veredicto**: Borrarlo.

### F9.2: `/home/laia-arch/LAIA-ARCH/` — qué hay aquí exactamente

- **Descripción**: `atlas.yaml` referencia `laia_arch_home` como `~/LAIA-ARCH`.
- **Veredicto**: Verificar que existe y tiene los subdirectorios `workspaces`, `skills`, `memories`.

### F9.3: `docs/db-export/` — verificar que está actualizado

- **Descripción**: Si es un export auto-generado de `workspace.db`, debería estar razonablemente actualizado.
- **Veredicto**: Revisar fecha del último export.

---

## HALLAZGOS NUEVOS (críticos)

### H1: TESTS FALLANDO — 2 de 363 tests failed

```
FAILED tests/test_laia_coordinator.py::test_laia_chat_endpoint_employee_uses_base_toolset
FAILED tests/test_laia_coordinator.py::test_laia_chat_endpoint_admin_streams

Error: worker crashed: test_session_id_defaults_to_user_scoped.<locals>._capture()
        got an unexpected keyword argument 'mode'
```

- **361 passed, 2 failed** en 72 segundos.
- El error parece ser un problema de compatibilidad de versiones en el test runner (no del código de producción).
- **Hipótesis**: El test usa `pytest-asyncio` o similar con una versión incompatible del parámetro `mode`.
- **Solución**: Revisar las dependencias del `.venv` de agora-backend, específicamente `pytest-asyncio` y `httpx`.

### H2: `laia-pathd` SÍ está corriendo (no estaba en el scan inicial)

```
PID 373851: /opt/laia/.laia-core/venv/bin/python /opt/laia/infra/bin/laia-pathd --log-level INFO
```

- **Conclusión**: El daemon pathd SÍ está instalado y corriendo en el host.
- El socket `/home/laia-arch/.laia/pathd.sock` debería existir si está funcionando.
- **Re-evaluar**: `atlas.yaml` lo marca como offline pero el proceso está corriendo. Verificar el socket.

### H3: `auth.json` contiene tokens reales de OpenAI

- El campo `auth.json` contiene `access_token`, `refresh_token`, e `id_token` de OpenAI OAuth.
- **SON tokens reales** — el `access_token` tiene fecha de expiry que indica que es un token real.
- **No es necessarily un problema** — `auth.json` está en `~/.laia/` (directorio de credenciales).
- **Precaución**: Nunca hacer commit de `auth.json` a git.

### H4: Executor en `agent-jorge-dev` SÍ responde

```bash
$ lxc exec agent-jorge-dev -- curl -s http://127.0.0.1:9091/health
{"status":"ok"}
```

- El executor corre en el container `agent-jorge-dev` en puerto 9091.
- **Problema**: `executor_api.host = agent-jorge` en atlas.yaml — el nombre no resuelve porque el container se llama `agent-jorge-dev`.

### H5: Puerto 35005 = LXD event monitor

- Es el puerto TCP del LXD daemon para eventos/monitorización.
- Proceso: container init (PID 1 del container) mapeado al host.
- **No es problema** — es intencional del LXD.

---

## Resumen de Acciones Prioritarias (orden sugerido)

| Prioridad | Problema | Solución |
|-----------|----------|----------|
| 🔴 H1 | 2 tests fallando en `test_laia_coordinator.py` | Revisar dependencias pytest-asyncio/httpx |
| 🔴 P1 | `jorge_container` → `agent-jorge` (muerto) | Editar atlas.yaml: `value: agent-jorge-dev` |
| 🔴 P1 | `executor_api` host → `agent-jorge` (muerto) | Editar atlas.yaml: `host: agent-jorge-dev` |
| 🟡 P2 | `bin/atlas.py` suelt | Borrar `bin/atlas.py` |
| 🟡 H2 | `pathd_socket` offline pero daemon corriendo | Verificar socket y actualizar atlas.yaml si el socket existe |
| 🟡 P5 | `.env.paths` y `auth.json` contienen tokens reales | Asegurar que `~/.laia/` está en .gitignore y nunca se hace commit |
| 🟢 P6 | `atlas visualize` syntax error | Reescribir con D3.js o simplificar Mermaid |
| 🟢 P4 | Tests referencing old names | Revisar y actualizar si es necesario |
| 🟢 P3 | Puerto 35005 sin identificar | Ya identificado — LXD monitor (no es problema) |
| 🟢 P1 | `laia_root` con `~/LAIA` tilde | Cambiar a path absoluto `/home/laia-arch/LAIA` |

---

## Comandos de verificación rápida

```bash
# Verificar container real del executor
lxc exec agent-jorge-dev -- curl -s http://127.0.0.1:9091/health

# Verificar agora-backend
curl -s http://127.0.0.1:8088/health

# Verificar signal-cli
curl -s http://127.0.0.1:8080/v1/health

# Identificar proceso en puerto misterioso
ss -tlnp | grep 35005

# Ver estado git
cd /home/laia-arch/LAIA && git status

# Revisar contenido de archivos sensibles
cat ~/.laia/.env.paths | head -20
cat ~/.laia/auth.json | head -20

# Ejecutar tests
cd /home/laia-arch/LAIA && make test 2>&1 | tail -30
```

---

## Correcciones al Plan de Claude Code (Opus)

> Añadido por OpenCode tras verificar los hallazgos de Claude.
> Claude hizo un plan basado en asunciones incorrectas. Estas son las correcciones.

### 🔴 Corrección 1: `~/LAIA-ARCH/atlas/` NO es un config de Atlas

**Lo que Claude dijo:** "probable ~/.laia/atlas/atlas.yaml o ~/LAIA-ARCH/atlas/atlas.yaml (a confirmar)".

**Realidad verificada:**

```
~/LAIA-ARCH/atlas/
├── agora          → /opt/laia/services/agora-backend
├── agora_data     → /srv/laia/agora/agora.db
├── infra          → /opt/laia/infra
├── laia_core      → /opt/laia/.laia-core
├── laia_home      → ${LAIA_HOME:-/home/laia-arch/LAIA-ARCH}
├── srv_laia       → /srv/laia
├── laia_root      → /opt/laia
├── skills         → ${LAIA_HOME:-/home/laia-arch/LAIA-ARCH}/skills
├── workspaces     → ${LAIA_HOME:-/home/laia-arch/LAIA-ARCH}/workspaces
└── ... (35 symlinks en total)
```

**Es una granja de symlinks** a `/opt/laia/` para que el agente pueda usar rutas relativas.
El `atlas.yaml` real está en `~/.laia/atlas.yaml` (sin subdirectorio `atlas/`).

**Acción:** Descartar la confusión sobre `~/LAIA-ARCH/atlas/atlas.yaml`. El TODO-1 sigue válido pero con el path correcto `~/.laia/atlas.yaml`.

---

### 🔴 Corrección 2: La unidad systemd está en `/etc/systemd/system/`, no `--user`

**Lo que Claude dijo:** "Servicio systemd activo: laia-pathd.service (PID 373851)" y asume que usa `LAIA_HOME=~/LAIA-ARCH`.

**Realidad verificada:**

- Unit file: `/etc/systemd/system/laia-pathd.service` (no `--user`)
- Contenido clave:
  ```
  User=laia-arch
  Environment=HOME=/home/laia-arch
  Environment=LAIA_HOME=/home/laia-arch/LAIA-ARCH
  ExecStart=/opt/laia/.laia-core/venv/bin/python /opt/laia/infra/bin/laia-pathd --log-level INFO
  ```
- `LAIA_HOME=/home/laia-arch/LAIA-ARCH` ✅ — Claude tenía razón en este punto

**Acción:** El plan es correcto en este punto. Confirmado.

---

### 🟡 Corrección 3: `~/.laia-clone-stage` NO existe

**Lo que Claude dijo:** "sudo rm -rf ~/.laia-clone-stage /root/.laia/" como acción manual.

**Realidad verificada:**

```bash
$ ls ~/.laia-clone-stage 2>/dev/null || echo "no existe"
no existe
```

**Acción:** Eliminar el TODO-14 de la lista de acciones. No hay residuo que limpiar.

---

### 🟡 Corrección 4: `cron/` NO está perdido ni gitignored

**Lo que Claude dijo:** "laia-core-cron-package-gitignored-lost-in-migration — import cron falla porque cron/ está en .gitignore y se perdió".

**Realidad verificada:**

```bash
$ ls ~/LAIA-ARCH/cron/
output/
.tick.lock

$ git check-ignore ~/LAIA-ARCH/cron/ 2>/dev/null && echo "gitignored" || echo "NOT gitignored"
NOT gitignored
```

**Acción:** El `cron/` existe, está en `~/LAIA-ARCH/`, y **no está gitignored**. Descartar TODO-6 de la lista.

---

### 🟡 Corrección 5: `/root/.laia/` — necesita verificación antes de limpiar

**Lo que Claude dijo:** "~/.laia-clone-stage y markers quedan root:root" → "sudo rm -rf /root/.laia/".

**Realidad verificada:** No se verificó el contenido de `/root/.laia/` ni si existe.

**Acción:** Si se quiere limpiar `/root/.laia/`, primero verificar su contenido:
```bash
ls -la /root/.laia/ 2>/dev/null && echo "EXISTS" || echo "no existe"
```

---

### 🟡 Corrección 6: El plan no menciona `bin/atlas.py` tiene `md5` idéntico a `bin/atlas`

**Lo que falta en el plan:** No se dijo que `bin/atlas.py` es byte-a-byte idéntico a `bin/atlas`.

```bash
$ diff bin/atlas bin/atlas.py
(no output — idénticos)
$ md5sum bin/atlas bin/atlas.py
ea7ed373a64267eb476bbec929c9f63d  bin/atlas
ea7ed373a64267eb476bbec929c9f63d  bin/atlas.py
```

**Acción:** El plan en TODO-2 es correcto (borrar `bin/atlas.py`). Confirmado que son idénticos — es claramente un duplicado accidental que se creó durante ediciones.

---

### 🟡 Corrección 7: `/opt/laia/bin/atlas` vs `~/LAIA/bin/atlas` — son cosas distintas

**Confusión potencial no resuelta por Claude:**
- `/opt/laia/bin/atlas` — versión **v0.11.0 instalada** (existe)
- `~/LAIA/bin/atlas` — versión **dev en desarrollo** (existe, es el que editas)
- El CLI en PATH usa `/opt/laia/bin/atlas` (via `/usr/local/bin/laia` symlink)

**Acción:** Ninguna — es intencional. Pero debería estar en los docs de arquitectura (TODO-11 y TODO-12 del plan de Claude).

---

### 🟡 Corrección 8: El plan menciona `skills/.curator_state` pero no lo verificó

**Lo que Claude dijo:** "skills/.curator_state — modificación de 5 líneas, sin commit".

**Realidad verificada:** El cambio es de línea de indentation, no de contenido:
```diff
-  "__path": ...
+    "__path": ...
```
Esto es irrelevante — probablemente un artefacto de formateo de un editor.

**Acción:** Descartar como problema real. `git restore skills/.curator_state` es seguro y limpio.

---

## Resumen: Estado de los TODOs de Claude tras correcciones

| TODO de Claude | Estado | Corrección |
|---|---|---|
| TODO-1: Fix atlas.yaml `agent-jorge` → `agent-jorge-dev` | ✅ Válido | Confirmar path `~/.laia/atlas.yaml` |
| TODO-2: Borrar `bin/atlas.py` | ✅ Válido | Confirmado: byte-a-byte idéntico a `bin/atlas` |
| TODO-3: `skills/.curator_state` | ✅ Válido | Es cambio de indentación, irrelevante pero restaurar para limpiar |
| TODO-4: Integrar auditoria-profunda-ecosistema.md | ✅ Válido | — |
| TODO-5: Test pool contamination | ✅ Válido | Los 2 tests fallan, merece investigación |
| TODO-6: cron gitignored | ❌ Descartado | `cron/` NO está gitignored y existe |
| TODO-7: installer-shell-rc-root-owned | ⚠️ Por verificar | No se ha verificado el estado actual |
| TODO-8: clone-leaves-root-owned | ⚠️ Por verificar | `.laia-clone-stage` no existe, pero也许残留en otro lugar |
| TODO-9: clone-ssh-setup-mode-continues | ⚠️ Por verificar | — |
| TODO-10: backend suite test leak | ⚠️ Duplicado de TODO-5 | Consolidar |
| TODO-11: Docs LAIA_HOME | ✅ Válido | Confirmar `~/LAIA-ARCH/` como verdad |
| TODO-12: Docs relación ~/LAIA ↔ /opt/laia ↔ ~/LAIA-ARCH | ✅ Válido | — |
| TODO-13: Commits directos a main | ✅ Válido | Documentar en changelog.md |
| TODO-14: Residuos root | ❌ Parcialmente descartado | `.laia-clone-stage` no existe; `/root/.laia/` necesita verificación |
| TODO-15: Triage de auditoría | ✅ Válido | — |
