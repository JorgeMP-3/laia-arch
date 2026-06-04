# LAIA — Política de seguridad y modelo de confianza

Este documento nombra **la frontera de seguridad que LAIA trata como load-bearing**, clasifica
el resto de protecciones como lo que son (heurísticas), y define qué cuenta como vulnerabilidad.
Adaptado del trust model de Hermes Agent (upstream) a la realidad **multi-usuario** de LAIA.

> Si algo aquí contradice a `LAIA_ECOSYSTEM.md`, **gana el canónico** (reglas duras ⑤-⑭).
> Este doc las formaliza en términos de seguridad; no las sustituye.

## 1. Reportar una vulnerabilidad

LAIA es un proyecto de operador único. Reporta **en privado a Jorge** (no en issues públicos).
Las IAs de desarrollo registran hallazgos en `~/laia-developers/workflow-main/SECURITY.md`
(repo **privado**) con severidad P0-P3. No hay programa de recompensas.

Un buen reporte incluye: componente afectado (path:líneas), reproducción contra `main`,
y **qué frontera del §2 se cruza**.

## 2. Modelo de confianza

### 2.1 Definiciones

- **El cerebro** — el container `laia-agora`: backend/API, pool de instancias IA, Tool
  Forwarder, BD central (`agora.db`), código (`.laia-core`).
- **El despacho** — el container privado `agent-<usuario>` de cada PA-AGORA, con su
  `laia-executor`. El usuario es **root ahí dentro, por diseño**.
- **LAIA-ARCH** — la capa administradora del host. Solo Jorge. Invisible para usuarios.
- **Superficie de entrada** — cualquier canal por el que entra contenido al contexto de un
  agente: mensajes de usuario, web, archivos, resultados de tools.
- **Envelope de confianza del usuario** — lo que SU container alcanza: sus archivos
  (`/srv/laia/users/<slug>`), su workspace, los workspaces compartidos con él.

### 2.2 LA frontera: aislamiento a nivel de OS (containers LXD)

**La única frontera real contra un LLM adversarial (o un usuario malicioso) es el container.**
El LLM razona en el cerebro, pero **toda acción se ejecuta en el despacho del usuario que
llama** — como root, sin sandbox in-process. Nada de lo que ocurre *dentro* del proceso del
agente constituye contención.

Las fronteras load-bearing de LAIA, de fuera hacia dentro:

| # | Frontera | Qué confina |
|---|---|---|
| F1 | **Container de usuario** (LXD unprivileged + idmap, bind mounts `shift=true`) | Las acciones del PA/usuario: no alcanzan el host ni a otros usuarios. |
| F2 | **Separación cerebro ⟷ despachos** | El usuario nunca ve `.laia-core` ni `agora.db` (no existen en su container); las tool calls viajan por el Tool Forwarder, nunca se ejecutan en `laia-agora` (reglas ⑦⑧⑬). |
| F3 | **Separación AGORA ⟷ ARCH** | El admin de AGORA no administra el host: sin `lxc exec`, sin infraestructura (reglas ⑤⑥). |
| F4 | **Host endurecido** | `/srv/laia` root-owned con secretos 0600 en `arch/secrets/`; UFW + fail2ban; acceso preferente por Tailscale. |

### 2.3 Heurísticas in-process (útiles; NO son fronteras)

- El **toolset restringido del coordinador LAIA** (modo de chat, regla ⑫-⑭): lo aplica el
  backend (código confiable) — un **fallo del gating es vulnerabilidad** (§3.1), pero el
  toolset en sí no contiene a un LLM que ya ejecuta en el container del caller.
- Flujos de aprobación, validaciones de entrada del backend, redaction en logs/UI.
- La **aprobación de plugins/skills del Marketplace**: es revisión previa (ayuda al operador),
  no contención — lo instalado ejecuta en el container del usuario (F1 es quien contiene).

### 2.4 Superficies externas (reglas uniformes)

Superficies: la API/backend de AGORA (vía nginx), webhooks, la futura UI web.

1. **Autorización en cada superficie** que cruce una frontera de confianza. Fail-closed:
   sin auth configurada → no se despacha trabajo.
2. **Un session/chat ID es un handle de enrutado, NO autorización** — el acceso se
   re-verifica contra el usuario autenticado.
3. Dentro del envelope de un usuario, sus sesiones son igual de confiables; no hay
   capacidades por-sesión.
4. Por defecto las superficies se exponen **solo a red local/Tailscale**. Exponer a
   internet público sin VPN/allowlist es decisión **break-glass del operador** (§3.2).

## 3. Alcance

### 3.1 En alcance (vulnerabilidad)

- **Escape de F1**: código ejecutado en un `agent-*` que alcanza el host u otro container.
- **Cruce de F2**: leer `.laia-core`/`agora.db`/secretos desde un container de usuario;
  ejecutar tool calls en `laia-agora`.
- **Acceso cross-usuario** sin permiso: datos, workspaces no compartidos, sesiones ajenas.
- **Cruce de F3**: del rol admin-de-AGORA a control del host.
- **Exfiltración de credenciales** de `/srv/laia/arch/secrets/` o de API keys de usuarios
  por un mecanismo que debía impedirlo (permisos, logs, transporte).
- **Bypass de autorización** en superficies externas (§2.4), incluido fallar-abierto.
- Código que se comporta **contrario a lo documentado** aquí o en el canónico.

### 3.2 Fuera de alcance (no es vulnerabilidad; puede ser issue normal)

- **Prompt injection per se**: lograr que el LLM emita algo raro, sin encadenar un cruce
  del §3.1. El PA haciendo destrozos *dentro del container de su dueño* es el modo de
  fallo previsto del diseño "root en tu despacho".
- **El usuario siendo root en SU container** y lo que eso permite dentro de su envelope.
- Bypasses de heurísticas del §2.3 sin cruce de frontera (mejóralas vía PR normal).
- **Configuraciones break-glass** elegidas por el operador (exponer la API a internet sin
  VPN, desactivar UFW, correr dev sobre datos reales).
- Skills/plugins de Marketplace haciendo cosas malas **dentro del container de quien los
  instaló** — la frontera es F1 + la revisión de aprobación; bugs en el *proceso de
  aprobación/instalación* que oculten lo que se instala sí están en alcance.

## 4. Hardening de despliegue (resumen operativo)

- Aislamiento acorde al contenido que el agente ingiere (la decisión nº 1).
- Secretos solo en `/srv/laia/arch/secrets/` (0600, root) — nunca en config ni en git
  (gate `scripts/check-no-secrets.sh` en CI).
- Supply-chain: deps con techo + actions por SHA (gate `scripts/check-supply-chain.sh`).
- Red: UFW deny-incoming por defecto, fail2ban, acceso por Tailscale; servicios nuevos
  nacen loopback/LAN.
- Estado real del host y su seguridad: `~/laia-developers/SERVER.md` +
  `~/laia-developers/workflow-main/SECURITY.md`.
