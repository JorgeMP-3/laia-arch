# PRD (draft) — Track T · Suite de regresión / integridad del ecosistema

- **Fecha**: 2026-05-30
- **Owner**: Jorge (aprueba) · Coder-Codex (implementa) · Lead (diseña + revisa)
- **Estado**: draft (pendiente OK de Jorge)
- **Track**: T (regresión) · **Agente**: Coder-Codex · **Prioridad**: tras A, **antes de D**.
- **Relación**: **EXPANDE** `tests/integration/test_ecosystem_integrity.sh` (D2). La **maquinaria** que
  la corre (CI + monitor + dashboard) = **Track B** (Opus). Absorbe el smoke de carga (C5 de PRD-C).

## Contexto

Hoy la integridad del ecosistema solo se comprueba con **D2** (un gate manual de 6 capas). Vamos a
integraciones (canales, plugins, skills) y usuarios reales: hace falta una **red de regresión** que
detecte **automáticamente** si un cambio rompe un invariante — para añadir cosas sin miedo y enterarse
cuando algo se rompe.

## Objetivo

Suite estructurada que cubra el ecosistema de arriba a abajo, **corra sola** (PR + periódica + pre-deploy)
y reporte en formato máquina-legible. **Calidad de cobertura > cantidad de tests.**

## Principios (el "cómo", que es lo que la hace profesional)

- **Pirámide**: muchos **unit** rápidos + **integración** medianos + **pocos e2e** pesados. NO todo e2e.
- **Contratos por capa**, no tests sueltos: cada capa afirma sus invariantes.
- Cada test **determinista**, con **teardown limpio**, **idempotente**.
- **Explícito qué corre dónde** (CI sin-LXD vs host/VM con-LXD) — sin silent gaps.

## Alcance — categorías (slices)

- **T1 · Runner + taxonomía.** `tests/integration/run_integrity.sh` que descubre tests por capa/nivel,
  **selecciona el subset por entorno** (CI sin-LXD vs host/VM con-LXD) y **reporta JSON + exit code**
  (formato que consumirá el monitor de Track B). Migra D2 a esta estructura **sin perder cobertura**.
- **T2 · Invariantes por capa** (las 6 de D2: host, LXD, AGORA, executor, datos 2-zonas, Atlas, backups).
  Ej: usuario provisionado ⇒ container + executor + workspace + fila en DB **consistentes**; refs de
  Atlas resuelven; `secrets` 0600; `agora.db` schema/integrity.
- **T3 · Camino dorado e2e**: provisionar usuario → crear agente → chat → tool-call ejecuta en **SU**
  container → resultado → desprovisionar **sin residuo**. Corre en la VM golden.
- **T4 · Consistencia cruzada**: DB ↔ filesystem ↔ containers concuerdan en ambos sentidos (sin huérfanos).
- **T5 · Regresión de bugs**: por cada bug `resolved` de `workflow/problems.md`, un test que lo fija
  (que **no vuelva nunca**).
- **T6 · Idempotencia/teardown + carga** (absorbe C5): provision/deprovision N veces deja el host limpio;
  smoke de ~10 agentes + (cuando C aterrice) verificar idle-eviction.

## Dónde corre (clave — si no corre solo, no sirve)

- **Subset rápido (sin LXD)** → CI de PR (Track B / B1).
- **Subset pesado (LXD/e2e)** → VM golden + monitor del host (Track B / B2) → dashboard.
- **Pre-deploy** → gate del cutover de prod (Lead).

## Criterios de aceptación

- Taxonomía clara (carpetas por capa/nivel) + un runner que selecciona subset por entorno y reporta
  **JSON + exit code**.
- Cada capa con sus invariantes núcleo; **camino dorado e2e verde** en la VM.
- **≥1 test de regresión por bug `resolved`** de `problems.md`.
- Documentado **qué corre en CI vs VM/host** (no silent gaps).
- Reproducible y razonablemente rápida (paralelizar donde se pueda; lo pesado solo en VM/host).

## No-objetivos

- La maquinaria (CI, monitor, dashboard) = Track B, no aquí.
- Tests de UI del frontend (fuera por ahora).

## Riesgos

- **Flaky e2e** → entorno golden + teardown estricto + reintentos acotados y marcados.
- **Lentitud** → pirámide + paralelismo + lo pesado fuera del PR.
- **Acoplamiento con B** → fijar **ya** el formato de reporte (JSON) para que B lo consuma sin fricción.

## Decisiones de Jorge

- ✅ Prioridad: Codex hace esto tras A, antes de D (confirmado).
- 🟡 Formato de reporte: sugerencia del Lead = **JSON simple + exit code** (fácil de consumir por el
  monitor de B y por el gate del cutover). Objeta si prefieres TAP.
