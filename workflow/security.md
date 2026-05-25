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
