# PRD (draft) — Track D · Eficiencia del CÓDIGO y el ECOSISTEMA

- **Fecha**: 2026-05-30
- **Owner**: Jorge (aprueba) · Coder-Codex (implementa) · Lead (diseña + revisa)
- **Estado**: draft (pendiente OK de Jorge) — alcance **confirmado**: código + recursos.
- **Track**: D · **Agente**: Coder-Codex
- **Reframe de Jorge (2026-05-30)**: "eficiencia" = **del código y del ecosistema**
  (rendimiento, arquitectura, recursos). **NO** routing/coste de LLM (malentendido previo).

> 📌 **Aparcado como config, no es este track:** LLM **default = Minimax**, **fallback = Minimax
> o Codex**. Lo capturo aparte (slice de config corto) cuando me digas dónde fijarlo.

## Contexto

El código viene de un fork de Hermes con saneamiento reciente. Hay señales de grasa: un
duplicado conocido (`bin/atlas.py`), código muerto era-Hermes, posibles queries/arranques
lentos, y un footprint por-agente que importa mucho con 10 usuarios (ver PRD-C: RAM es el
recurso que ata). "Eficiente" aquí = **rápido, limpio y ligero en recursos**, sin cambiar
comportamiento.

## Objetivo

Reducir el coste en **tiempo (cold-start, latencia), recursos (RAM/disco por agente) y deuda
(duplicación, código muerto, módulos poco profundos)** del ecosistema, midiendo antes/después.

## No-objetivos

- Routing/coste de LLM (reframe — fuera).
- Reescrituras grandes sin datos: todo refactor profundo sale del audit (D1), no de la intuición.

## Slices (orden por dependencia)

- **D1 · Audit de eficiencia** (read-only) — usa el lens de `improve-codebase-architecture`.
  Perfila y prioriza por **impacto × esfuerzo**: (a) **recursos**: cold-start y footprint
  RAM/disco de `laia-agora` y un agente, tamaño de imagen LXC; (b) **datos**: queries lentas /
  índices ausentes en `agora.db`; (c) **código**: duplicación (`bin/atlas.py` y otros), código
  muerto era-Hermes, módulos acoplados/poco profundos. Entregable: informe priorizado a `_inbox/`.
- **D2 · Quick wins** — aplicar lo de alto-impacto/bajo-riesgo del audit (dedup, borrar muerto,
  índices DB, imagen LXC lean). Cada uno con **benchmark antes/después** y tests verdes.
- **D3 · Refactors profundos** — los que el audit revele que valen la pena; **cada uno con su
  mini-PRD** y revisión, no a granel.

## Criterios de aceptación

- D1: informe priorizado con números (ms de cold-start, MB de footprint, ms de query, LOC
  duplicadas/muertas) — no impresiones.
- D2: cada quick win con benchmark antes/después demostrando la mejora; **comportamiento
  intacto** (suite verde); changelog.
- Nada que toque prod sin ensayo en la VM.

## Decisiones (resueltas)

- ✅ **Alcance** = código + recursos (confirmado por Jorge). LLM/coste fuera.
- ✅ **Prioridad = footprint primero** (cuánta RAM/disco consume cada agente/proceso). Es lo que
  ata la escala en el P720 (30 GiB) y **alimenta directamente C**: bajar el footprint en D = más
  usuarios en C. Velocidad (cold-start) en 2º lugar (mejora el wake-on-demand de C2 de PRD-C);
  mantenibilidad/limpieza, en oportunista (lo que el audit encuentre barato).

> **footprint** = la huella de recursos de algo: los MB de RAM y disco que ocupa. "Reducir footprint"
> = que cada agente pese menos → caben más usuarios en los mismos 30 GiB.
