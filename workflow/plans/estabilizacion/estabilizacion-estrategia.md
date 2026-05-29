# Plan de la idea: Estabilización de LAIA-ARCH + Entorno de Desarrollo

> **Fecha:** 2026-05-28 · **Autor:** Claude (Opus) · **Tipo:** plan de **idea/estrategia**.
>
> Este documento describe **qué** vamos a hacer y **cómo se divide el trabajo por fases**,
> en lenguaje llano. **No** entra en comandos, paths exactos ni dimensionado: eso irá en un
> **plan técnico aparte**, después de que aprobemos esta idea.
>
> **No reinventa la arquitectura.** El modelo de LAIA (`LAIA_ECOSYSTEM.md`) y el layout en
> disco (`arch-layout.md`) son la referencia y no se tocan. Esto solo **ordena** lo que ya
> está definido y añade una pieza que falta: un entorno de desarrollo aislado.

---

## La idea en una frase

**Separar limpiamente "donde se desarrolla" de "donde funciona el producto", poner orden
en el host, y darle a Jorge un taller de desarrollo donde pueda romper cosas sin riesgo —
sin tocar producción ni la arquitectura.**

---

## Qué tenemos hoy (en llano)

- **Una sola máquina hace dos trabajos a la vez:** el mismo servidor (la ThinkStation) es
  a la vez producción y banco de desarrollo. Lo que se edita y lo que da servicio conviven,
  y eso es frágil: un experimento puede rozar lo que ya funciona.
- **Los ficheros del agente están desordenados:** parte del estado vivo del agente está en
  un sitio que la propia documentación dice que no es el suyo, y hay credenciales
  duplicadas y descoordinadas (incluida una con permisos demasiado abiertos).
- **Pequeños cabos sueltos:** un par de referencias internas rotas, un archivo duplicado,
  y dos tests que fallan.
- **No hay un entorno de desarrollo de verdad aislado:** hoy probar el instalador o una
  migración de forma fiel es arriesgado porque no hay un "host limpio" donde hacerlo.

Nada de esto es grave por separado, pero juntos hacen que el sistema sea más difícil de
evolucionar con confianza. El objetivo es dejarlo ordenado y seguro de tocar.

---

## En qué se divide el trabajo: tres bloques

### Bloque A — Poner orden en el host

**Qué:** arreglar los cabos sueltos de producción: las referencias rotas, el archivo
duplicado, cerrar el permiso inseguro de las credenciales, comprobar que el proceso de
publicar una versión sigue funcionando, arreglar los dos tests que fallan, dejar un
chequeo rápido de salud del sistema, y **montar copias de seguridad que funcionen** (hoy
**no hay ninguna**; la herramienta existe en el repo pero sin activar y con restos legacy
— reutilizarla, no rehacerla). Las copias de seguridad son **prerequisito** del Bloque C.
También limpiamos restos: los dos directorios `workspaces/` **vacíos** (`~/` y `~/LAIA/`),
el `atlas.yaml.bak` suelto, y —con tu OK— los containers de prueba `verify-bob/carol`.


**Para qué:** tener una base limpia y de confianza antes de construir encima.

**Riesgo:** bajo. Son cambios pequeños y reversibles. **No depende de nada** y se puede
hacer ya, en paralelo con lo demás.

### Bloque B — Montar el taller de desarrollo

**Qué:** crear una **máquina de desarrollo dedicada que vive dentro del propio servidor**
(una máquina virtual). Tiene su propia copia de todo y su propio espacio de datos, separada
de producción. Jorge se conecta a ella desde el Mac (solo terminal/editor, sin VM en el
Mac) y desarrolla y prueba ahí. Si algo se rompe, producción ni se entera; y se pueden
guardar "fotos" del estado para volver atrás en segundos.

**Para qué:** poder construir y, sobre todo, **probar el instalador y las migraciones de
forma fiel** (como lo viviría una máquina de cliente real), sin poner producción en riesgo.
Es la pieza que **habilita** trabajar con tranquilidad y la que sustituye a la idea vieja
(e impráctica) de desarrollar en una VM en el Mac.

**Riesgo:** bajo. Es **aditivo**: se añade algo nuevo, no se toca lo que ya funciona. Es
**la prioridad**, porque desbloquea el resto.

### Bloque C — Ordenar la casa del agente

**Qué (según tu decisión: *actualizar la documentación*):** en vez de mover el estado vivo
del agente, **formalizamos en la documentación** que su hogar es `~/LAIA-ARCH/` (que es
donde ya está). A cambio arreglamos lo que hay que arreglar sí o sí: la **credencial con
permiso inseguro** y la **credencial duplicada/descoordinada**. Las credenciales que el
cerebro (Agora) necesita leer **se quedan en su zona segura de siempre** — esa parte no se
mueve, porque hay servicios que dependen de ella. Además **fijamos la ruta del "home" del
agente** a una única ruta absoluta en todos los contextos (hoy se resuelve distinto según
desde dónde se ejecuta, y por eso aparecen carpetas `workspaces/` vacías en `~` y `~/LAIA`),
y **corregimos los paths desactualizados** de la propia documentación (p. ej.
`canonical-sources.md` apunta la base de conocimiento a `~/.laia/workspaces/`, que no existe).

**Para qué:** que lo documentado y la realidad coincidan, y cerrar el agujero de seguridad,
**sin arriesgar una migración de datos del agente vivo** (importante porque vamos hacia
usuarios reales).

**Riesgo:** bajo-medio. Es sobre todo trabajo de **documentación + un arreglo de seguridad
puntual**, no de mover el estado del agente. Toca documentos de arquitectura (uno de ellos
**canónico → requiere tu consentimiento explícito** para editarlo); el ajuste de
credenciales conviene **ensayarlo antes en el taller (Bloque B)** y hacerlo con copia de
seguridad.

---

## Cómo se ordenan los bloques

- **A** se puede hacer **ya**, en paralelo, sin esperar a nada (es seguro).
- **B** es la **prioridad**: monta el taller que habilita lo demás y no arriesga producción.
- **C** va **el último**, apoyándose en B para ensayarlo sin riesgo, y con tu aprobación.

```
A (orden en el host) ───────── se puede hacer ya, en paralelo
B (taller de desarrollo) ───── prioridad; habilita lo demás
C (ordenar casa del agente) ── último; se ensaya en B; con backup y tu OK
```

---

## Qué NO vamos a tocar (a propósito)

- **La arquitectura y la visión** (`LAIA_ECOSYSTEM.md`): es el contrato; no se reinventa.
- **Los datos de producción** y los servicios en marcha: intactos, salvo en el Bloque C y
  con todas las cautelas.
- **El Mac de Jorge:** no corre ninguna máquina virtual; solo es terminal y editor.

---

## Decisiones tomadas (2026-05-28)

1. **Objetivo:** vamos hacia **usuarios reales pronto** → prioridad: no romper producción,
   reforzar seguridad y asegurar copias de seguridad.
2. **Casa del agente (Bloque C):** **actualizar la documentación** para bendecir
   `~/LAIA-ARCH/` como hogar del agente (en vez de migrar datos), arreglando igualmente la
   seguridad y los duplicados de credenciales.
3. **Alcance del taller (Bloque B):** **sencillo ahora, escalar luego**.
4. **Orden:** **el taller (B) primero**, y el orden del host (A) **en paralelo**.

## Aún por cerrar (no bloquean planear lo técnico)

- **Copias de seguridad — INVESTIGADO (2026-05-28): NO existen.** Ni directorio, ni
  herramienta instalada, ni cron, ni snapshots LXD. El repo trae herramientas
  (`infra/bin/laia-backup`, `infra/scripts/backup-state.sh`) pero **sin programar y con
  referencias legacy** (PostgreSQL `arete`, usuario `laia-hermes`). → Pasa a ser
  **prioritario** dentro del Bloque A y **prerequisito** del Bloque C.
- **Containers de prueba `verify-bob/carol` — INVESTIGADO:** son agentes de prueba (no
  usuarios reales), creados el 26-may en una corrida de verificación; tienen container +
  datos en `/srv/laia/users/verify-*` + entrada en `agora.db`. → **Retirarlos** (libera
  RAM para el taller), en el Bloque A y **con OK explícito** (toca `/srv/laia` y `agora.db`).
- **Acceso al taller — RESUELTO:** **Tailscale**, conexión directa desde el Mac (sin saltos
  ni IP en la LAN). La VM lleva Tailscale instalado.
- **El `~/LAIA` del host — RESUELTO:** deja de ser banco de desarrollo (todo dev → VM), pero
  **no se borra**: se reconvierte a **checkout de `stable` usado solo para `laia-release`**.

---

## Lo que viene después de esto

Una vez cerrada la idea y el reparto por fases, escribiremos el **plan técnico**: pasos
exactos, paths, dimensionado de la máquina de desarrollo, scripts a usar y plan de
rollback fino — bloque por bloque.
