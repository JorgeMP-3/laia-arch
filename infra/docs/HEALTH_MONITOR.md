# Monitor de salud de LAIA (`laia-health-monitor`)

> Track B · slice B2. Autovigilancia: LAIA corre periódicamente el runner de
> integridad y publica un **veredicto consultable** (sin email). Jorge lo mira
> cuando quiere; un dashboard puede leer el JSON.

## Qué es

`infra/bin/laia-health-monitor` consume el runner de integridad **T1**
(`tests/integration/run_integrity.sh --profile host --json …`) y publica su
veredicto a un estado consultable bajo `/srv/laia/state/health/`. Pensado para
dispararse por un `systemd timer` cada ~10 min, pero también corre a mano.

No confundir con `infra/bin/laia-health` (chequeo **interactivo** a terminal).
Éste es el monitor **no-interactivo** que alimenta el estado/dashboard.

```
runner T1 (D2 + futuros checks)  ──►  laia-health-monitor  ──►  /srv/laia/state/health/
  (lee el ecosistema, read-only)        (veredicto + estado)        latest.json / latest.txt / history.jsonl
```

## Estado publicado (`/srv/laia/state/health/`)

| Fichero | Qué es |
|---|---|
| `latest.json` | Veredicto: `status` (`green`/`red`/`error`), `cause`, `summary`, `failed[]` (con `stderr_tail`), `generated_at`, `host`, `profile`. **Lo que lee un dashboard.** |
| `latest.txt`  | El mismo veredicto en tabla legible (`cat` y listo, o `laia-health-monitor show`). |
| `report.json` | El reporte crudo del runner T1 (evidencia completa). |
| `history.jsonl` | Una línea compacta por run (`epoch`, `status`, pass/fail/skip, `cause`), **capada** a las últimas N (default 50). |

**Sin email, sin ruido (decisión de Jorge):** `latest.*` se **sobrescriben**
atómicamente cada run (`os.replace` → un lector nunca ve un fichero a medias) y
el histórico es corto. No hay canal de alertas que spamear: el "cooldown" es la
cadencia del timer + el histórico capado. Ampliar a email/Telegram sería trivial
(leer `latest.json` y empujar), pero está **fuera de alcance** por decisión de Jorge.

## Veredicto

| `status` | Cuándo | Exit del runner |
|---|---|---|
| `green` | todos los checks pasaron (`failed=0`, `passed>0`) | 0 |
| `red`   | algún check de integridad falló | 1 |
| `error` | el runner no pudo emitir veredicto fiable (config / ningún test / reporte ilegible / runner ausente) | 2 |

El monitor **siempre termina 0** si logró publicar el estado: la salud se
consulta en el fichero, no en el exit code del unit (un `red` no debe marcar el
timer de systemd como "failed"). Sólo un fallo del propio monitor da `!= 0`.

## Uso manual

```bash
laia-health-monitor run     # corre el runner y publica el estado
laia-health-monitor show    # imprime el último estado (latest.txt)
laia-health-monitor path    # imprime el directorio de estado
```

Env (overrides): `LAIA_ROOT`, `LAIA_STATE_ROOT` (default `/srv/laia/state`),
`LAIA_HEALTH_STATE_DIR`, `LAIA_HEALTH_PROFILE` (default `host`),
`LAIA_HEALTH_HISTORY_MAX` (default 50). El monitor **propaga el entorno** al
runner, así que los knobs de D2 (`CONTAINER`, `AGORA_HEALTH_PORT`, …) también valen.

## Habilitar en producción ⚠️ PROD-RISK — revisión de Lead + Jorge

Los units (`laia-health-monitor.service` + `.timer`) se **renderizan e instalan**
con el resto en cada deploy (glob de `infra/installer/systemd/*.tmpl`), pero
quedan **inertes**: instalar ≠ habilitar. Activarlos es un paso explícito y
prod-risk (toca systemd en prod):

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now laia-health-monitor.timer
systemctl list-timers laia-health-monitor.timer    # próxima ejecución
laia-health-monitor show                            # estado actual
journalctl -u laia-health-monitor.service -n 50     # log del último run
```

Requisitos para que el veredicto sea fiable en prod (ver caveats abajo):
- El servicio corre como `${LAIA_USER}`. **Ese usuario debe poder operar `lxc`**
  (estar en el grupo `lxd`) — en el host `doyouwin-server` `laia-arch` lo está.
- `/srv/laia/state` debe ser **escribible** por `${LAIA_USER}`.
- `jq` instalado en el host (D2 lo usa para resolver la IP del container — ver caveats).

## Caveats de D2 detectados en el ensayo (VM `laia-dev`, 2026-05-30)

El monitor reporta **fielmente lo que dice D2**; D2 tiene supuestos de entorno que
conviene conocer (registrados en `~/laia-developers/workflow-main/PROBLEMS.md`):

1. **Privilegios LXD**: D2 hace `lxc list/info`. Si el usuario que lo corre no ve
   el container (no está en el grupo `lxd`), D2 marca "container no existe" →
   falso rojo. El servicio debe correr como un usuario con acceso a `lxc`.
2. **`jq` + puerto de health**: el check de `/api/health` resuelve la IP del
   container con `jq` y cur-lea `http://<ip>:${AGORA_HEALTH_PORT:-8000}/api/health`.
   Sin `jq` el check **falla** (no degrada a skip) → falso rojo. El puerto por
   defecto (8000) es el correcto contra la IP del container.

## Ensayo en VM (criterio de aceptación B2) — ✅ 2026-05-30

Validado en la VM `laia-dev` contra el ecosistema **real anidado** (sin tocar prod;
el cerebro de prod en el host quedó intacto y verificado RUNNING):

| Paso | Acción | Veredicto |
|---|---|---|
| 1 | cerebro `laia-agora` arriba | **GREEN** (D2 9 checks ok/pend) |
| 2 | `lxc exec laia-dev -- lxc stop laia-agora` (parar cerebro anidado) | **RED** + causa (`ecosystem_integrity_d2`: container STOPPED + `/api/health` inaccesible) |
| 3 | `lxc exec laia-dev -- lxc start laia-agora` (recuperar) | **GREEN** |

`history.jsonl` registró las transiciones `green → red → green`.

> El cerebro **anidado** de la VM se opera SIEMPRE con `lxc exec laia-dev -- lxc …`.
> `lxc stop laia-agora` **en el host** pararía PRODUCCIÓN — nunca se hace eso.
