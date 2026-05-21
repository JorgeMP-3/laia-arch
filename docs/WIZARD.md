# LAIA — Setup Wizard

`laia-wizard` es la puerta principal para instalar, clonar, diagnosticar o
resetear LAIA en un host. No reemplaza a `bin/laia-install` ni
`bin/laia-clone` (esos siguen siendo el "modo experto" para CI y scripts) —
es una **capa por encima** que pregunta, valida y orquesta.

```
$ sudo laia-wizard
```

---

## Lo que verás en cada modo

### 1. Pantalla de bienvenida + menú principal

```
                              _      _    ___    _
                             | |    / \  |_ _|  / \
                            | |   / _ \  | |  / _ \
                            | |__/ ___ \ | | / ___ \
                           |____/_/   \_\___/_/   \_\
                                  Setup Wizard


  LAIA — Setup Wizard ─────────────────────────────────────────────────
  ╭───────────────────────────────────────────────────────────────────╮
  │  Bienvenido. Elige qué quieres hacer en esta máquina.             │
  ╰───────────────────────────────────────────────────────────────────╯

  Modo *
   [1]  Instalar LAIA desde cero     ▸ default   [recomendado]
        Factory-default: LXD + laia-agora + skills base. Ubuntu limpio.
   [2]  Clonar desde otra máquina
        Pull de datos + reconstrucción de containers en este destino.
   [3]  Configurar conectividad (SSH / Tailscale)
        Generar SSH key, copiar al destino. Útil pre-clone.
   [4]  Diagnosticar instalación existente
        Verifica health, containers, agora.db, paths. No modifica nada.
   [5]  Reset / wipe (PELIGROSO)
        Borra /opt/laia, /srv/laia, ~/.laia. Doble confirmación.
    Elige (1):
```

### 2. Modo **Fresh install**

Tres pantallas guiadas + confirmación final:

1. **LAIA admin** — username + password (deja vacío y se autogenera).
2. **Proveedor LLM** — DeepSeek / OpenAI / Anthropic / Local / Saltar. Si
   eliges uno real te pide la API key (no se persiste en el checkpoint).
3. **LXD** — auto-instalar si falta (yes/no).
4. **Confirmar** — resumen + botón **▶  Instalar**.

Durante la ejecución verás:

```
  ▸  Instalando LAIA
     · Pre-flight checks
     · Source tree
     · Copying source tree to /opt/laia-vX.Y.Z
     · Python venvs
     · Frontend
     · Symlink
     · Wrappers
     · Data dir
     · Systemd units
     · Bootstrap: host architecture
     · Bootstrap: LXD
     · Bootstrap: LXD defaults
     · Bootstrap: LXD images       ← (10-20 min, con heartbeat 60s)
     · Bootstrap: laia-agora container
     · Bootstrap: AGORA health
     · Factory: LAIA admin user
     · Factory: base skills
  ✓  Instalando LAIA OK     (320.4s)

  ■  Credenciales de admin
  ┌───────────────────────────────────┐
  │  Username   admin                 │
  │  Password   m1xn8Lc8Qq5BvT4eYwzP  │
  │  Guardado   $LAIA_HOME/.admin-credentials (mode 600)
  └───────────────────────────────────┘

  Siguientes pasos:
       • Abre la UI de LAIA-AGORA en http://localhost:8088
       • Loguéate con las creds de arriba y crea el primer empleado.

  ✓  Operación completada con éxito.   (total: 320.4s)
```

### 3. Modo **Clone**

5 pantallas + confirmación:

1. **Origen** — LAN IP / Tailscale / Custom `user@host`.
2. **user@host** — placeholder cambia según la opción anterior.
3. **Autenticación SSH** — clave existente / password / generar nueva.
4. **Opciones de transferencia** — `--bwlimit`, `--keep-session`, `--resume`.
5. **Confirmar** — resumen + botón **▶  Clonar**.

Durante el clone te muestra cada `clone_phase_h_*` como una sub-fase, la
build de imágenes con heartbeat, el reset del admin password importado y
el smoke final.

### 4. Modo **Connectivity** (SSH + Tailscale)

Útil antes de un clone cross-network:

1. **Clave SSH** — generar ed25519, usar existente, o saltar.
2. **Copiar al destino** — `ssh-copy-id user@host` (opcional).
3. **Tailscale** — saltar / `install + up` / sólo `up`.
4. **Confirmar**.

### 5. Modo **Diagnose**

Una sola pantalla: pulsa `▶ Ejecutar diagnóstico` y verás cada check
parseado del output de `vm-smoke.sh` y `preflight.sh`:

```
  ▸  vm-smoke
     · 1/3 LXD
  ✓  laia-agora está RUNNING
  ✓  /api/health responde
  ⚠  skipping DB assertions; sqlite3 or agora.db missing
  ■  vm-smoke terminado
  ┌─────────────────────┐
  │  OK         3       │
  │  Warnings   1       │
  │  Errors     0       │
  │  Exit       0       │
  └─────────────────────┘
```

### 6. Modo **Reset / wipe**

Dos confirmaciones obligatorias:

1. Casilla `Entiendo que esto NO se puede deshacer` → `Sí`.
2. Pantalla final pide escribir literalmente la palabra **`borrar`**.

Antes del wipe, opcionalmente crea `/var/backups/laia-reset-<timestamp>.tar.gz`
con todo el contenido que se va a borrar. Si te arrepientes a mitad: Ctrl-C
o teclea `q` en cualquier prompt.

---

## Atajos de teclado

En **cualquier** prompt:

| Tecla | Acción |
|-------|--------|
| `b` (Back) | Volver a la pantalla anterior |
| `q` (Quit) | Salir del wizard sin guardar |
| `Enter` | Aceptar el default (mostrado entre paréntesis) |

En prompts numéricos (choice / acciones): teclea el número de la opción.

---

## Re-ejecución segura — `--resume`

Si el wizard se interrumpe a mitad de un clone (terminal cerrada, SSH
caída, Ctrl-C), su estado queda en `$LAIA_HOME/wizard-state.json`
(mode 0600, secretos NO incluidos). La próxima vez:

```
$ sudo laia-wizard --resume
```

retoma justo donde te quedaste. El checkpoint se borra automáticamente al
completar con éxito o si haces quit.

> Importante: passwords y tokens nunca se guardan en el checkpoint. Tendrás
> que reescribirlos al reanudar.

---

## Atajos de invocación

```bash
# Saltar el menú principal y ir directo a un modo
sudo laia-wizard --mode install
sudo laia-wizard --mode clone
sudo laia-wizard --mode diagnose
sudo laia-wizard --mode reset
sudo laia-wizard --mode connectivity

# Forzar la UI mínima sin colores (terminales raros, scripts)
sudo laia-wizard --text-ui

# Imprimir versión del contrato y salir
sudo laia-wizard --version
```

---

## Variables de entorno

| Variable | Efecto |
|----------|--------|
| `LAIA_ROOT` | Override del path al repo (default: detectado vía `git rev-parse`). |
| `LAIA_HOME` | Override del dir de datos del admin (default: `$HOME/LAIA-ARCH`). |
| `NO_COLOR=1` | Salida en monocromo (auto si la terminal no soporta color). |
| `LAIA_WIZARD_THEME` | `default` (color) o `mono`. Ver `WIZARD_THEMING.md`. |
| `FORCE_COLOR=1` | Forzar color aunque stdout no sea TTY. |
| `LAIA_BUILD_QUIET=1` | Build de imágenes LXD sin streaming (legacy). |

---

## Pre-requisitos del host

- Ubuntu 22.04+ (kernel 5.15+).
- `python3 >= 3.11`. El bootstrap `bin/laia-wizard` lo instala vía apt si
  ejecutas como root.
- Para el modo Clone también: `sqlite3`, `rsync`, `openssh-client`. El
  bootstrap los aviso si faltan; el flow concreto los reinstala via apt si
  hace falta.

---

## Troubleshooting

- **Log del wizard**: `~/.cache/laia-wizard.log` (línea por launch).
- **Log del installer**: `~/.cache/laia-installer.log` (todas las
  primitivas `inst_*` y `boot_*` escriben aquí).
- **Logs del build de imágenes**: `/tmp/build-base.log` y
  `/tmp/build-agora.log` con stream en vivo (`tail -F` en otra terminal).
- **Checkpoint corrupto**: borra `$LAIA_HOME/wizard-state.json` y vuelve a
  ejecutar sin `--resume`.

---

## Si todo falla

El wizard es una capa por encima. Si necesitas más control:

```bash
# Modo experto: invoca el binario directamente con flags
sudo bin/laia-install --yes --admin-user admin --init-lxd
sudo bin/laia-clone --source user@host --yes --bwlimit=50M
```

Ver `docs/INSTALL.md` y `docs/CLONE.md`.
