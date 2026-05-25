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

(Sin entradas todavía.)
