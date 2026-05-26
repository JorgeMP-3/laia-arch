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
