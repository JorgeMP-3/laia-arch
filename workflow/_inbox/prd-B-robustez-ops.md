# PRD (draft) — Track B · Robustez / Ops

- **Fecha**: 2026-05-30
- **Owner**: Jorge (aprueba) · Coder-Opus (implementa) · Lead (diseña + revisa)
- **Estado**: draft (pendiente OK de Jorge → mover a `plans/` al aprobar)
- **Track**: B · **Agente**: Coder-Opus
- **Inputs de Jorge (2026-05-30)**: alertas → **dashboard / log consultable**. Email **descartado** ("no me parece importante"). NO Telegram. → B queda **sin bloqueo** (no hace falta SMTP).

## Contexto

LAIA va a usuarios reales (empresa de 10, ver PRD-C). Hoy la salud del ecosistema solo se
comprueba **a mano** corriendo D2 (`tests/integration/test_ecosystem_integrity.sh`). **Update
2026-05-31:** el **CI ya existe y está mergeado** (`.github/workflows/ci.yml` — B1 cumplido vía
PR #30); lo que falta es el **monitor en caliente** (B2, en curso en `wip/claude/monitor-dashboard`)
y el **backup off-site** (los backups D1 van a `/mnt/data` = **mismo disco físico** que la VM → no
es redundancia real). Si algo se cae de madrugada, nadie se entera hasta que un usuario se queja.

## Objetivo

Que LAIA **avise solo** antes de que un usuario lo note, y que sus tests corran en cada cambio.
"Robusto" = se autovigila, falla con aviso, y tiene una copia fuera del disco principal.

## No-objetivos (fuera de alcance de este PRD)

- Observabilidad completa (Prometheus/Grafana): sobredimensionado para 10 usuarios.
- Alta disponibilidad / failover automático.
- Routing LLM (eso era el malentendido de "eficiencia" → ver PRD-D).

## Slices (orden por dependencia; uno a la vez)

- **B1 · CI de la suite** (greenfield) — ✅ **HECHO** (`.github/workflows/ci.yml`, mergeado PR #30).
  Workflow GitHub Actions que corre en cada PR a `main`:
  pytest de `services/agora-backend` + los `tests/installer/*` runnable sin host real.
  **D2 (`test_ecosystem_integrity.sh`) requiere LXD/host → se SKIPea en el runner, documentado
  (no silent cap).** Es el slice más seguro → arranca por aquí.
- **B2 · Monitor de salud + dashboard.** `systemd timer` (cada N min) que corre las aserciones
  D2 ejecutables en caliente (`/api/health`, `agora.db` integrity, `atlas doctor` sin refs rotas,
  backup reciente presente) y escribe el resultado a un **estado consultable**
  (`/srv/laia/state/health/` — JSON/tabla, último estado + histórico corto). Sin email: Jorge lo
  revisa cuando quiere. (Email/Telegram = ampliación futura trivial si hace falta.)
- **B3 · Backup off-site (D5b)** — *prod-risk, ventana*. Réplica del backup D1 al **USB `VM-USB`**
  (`/dev/sdb1`, 217 G libres, ya reservado) sobre `infra/bin/laia-backup`; retención propia.

## Criterios de aceptación

- B1: el workflow pasa en un PR de prueba; matriz "qué corre / qué se skipea" documentada.
- B2: un fallo simulado (parar `laia-agora`) deja el estado en `rojo` en el dashboard con la
  causa; al recuperarse, vuelve a `verde`. Sin ruido (sobrescribe estado, no acumula).
- B3: `laia-backup` deja artefacto verificable en `VM-USB`; restore de prueba OK; retención aplica.
- Tests en `~/LAIA/tests/`; changelog actualizado.

## Riesgos / decisiones

- ✅ **Resuelto:** sin email (decisión de Jorge) → B2 es solo dashboard/estado. B desbloqueado.
- 🟡 USB como off-site: removible → el timer debe degradar con gracia si no está montado (marcar
  "off-site pendiente" en el dashboard, no romper).
