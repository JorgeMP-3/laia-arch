# Decisión — LXD vs Docker para agentes personales

## Metadata

- ID: `132`
- Slug: `decision-lxd-vs-docker`
- Kind: `important`
- Status: `active`
- Filename: `decision-lxd-vs-docker.md`
- Parent: `agentes-personales`
- Source kind: `tool`
- Created at: `2026-05-08T15:56:50.796783+00:00`
- Updated at: `2026-05-19T11:13:52.676952`
- Aliases: `decision-lxd-vs-docker`

## Summary

Decisión arquitectural LXD vs Docker para agentes AGORA

## Body

# Decisión arquitectural: LXD vs Docker para PA-AGORA AGORA

Fecha: 2026-05-08
Conversación: Sesión de diseño AGORA con Jorge Miralles + análisis Gemini

---

## Decisión: LXD como arquitectura favorita

**Driver:** La visión de AGORA requiere que cada empleado pueda tener un "laboratorio de desarrollo" completo dentro de su agente — levantar nginx, bases de datos, servicios propios, etc. Docker no da esto de forma segura.

## Comparativa determinante

| Criterio | Docker | LXD | Veredicto |
|---|---|---|---|
| SO invitado completo | ❌ No | ✅ Sí | LXD |
| systemd / systemctl | ❌ No | ✅ Sí | LXD |
| Nesting (contenedores dentro) | ⚠️ Peligroso (socket) | ✅ Seguro | LXD |
| Aislamiento filesystem host | ⚠️ Por montaje explícito | ✅ Nativo, zero acceso | LXD |
| Ver código base LAIA (host) | ⚠️ Si monta mal | ❌ No existe ruta | LXD |
| Snapshots | ⚠️ Requiere plugin | ✅ Nativo | LXD |

## Por qué Docker se descarta

- Sin systemd → el empleado no puede `systemctl start nginx`
- Nesting requiere Docker socket o DinD → riesgo de escape al host
- Docker está diseñado para una aplicación por contenedor, no un entorno de desarrollo

## Por qué LXD funciona

- Root dentro del contenedor, UID sin privilegios en el host (unprivileged container)
- Rutas del host (`/home/laia-arch/`) simplemente no existen dentro del LXD
- Aislamiento de red propio (subred 10.0.0.x)
- Snapshots nativos para recovery
- ~20-30MB RAM en idle, igual que Docker

## Exposición web (proxy inverso)

```
Host (nginx :80/:443)
  └── empleado.tuempresa.com → 10.0.0.50 (LXD laia-empleado)
```

El empleado levanta su nginx en el contenedor, nginx del host redirige. El empleado nunca toca el host.

## Alternativa

Docker como backup documentado en `agentes-docker-alternativa.md` por si LXD presenta problemas en Dell 9020.

## Validación pendiente

1. Verificar que LXD está instalado en Dell 9020
2. Medir consumo baseline con un agente de prueba
3. Configurar bridge de red 10.0.0.0/24
4. Configurar nginx proxy inverso en host

## Fuente

Conversación con Gemini + validación Jorge Miralles


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agentes-personales` (Agentes personales — Hijos de LAIA (v2.1)) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Decisión — LXD vs Docker para agentes personales

# Decisión arquitectural: LXD vs Docker para PA-AGORA AGORA

Fecha: 2026-05-08
Conversación: Sesión de diseño AGORA con Jorge Miralles + análisis Gemini

---

## Decisión: LXD como arquitectura favorita

**Driver:** La visión de AGORA requiere que cada empleado pueda tener un "laboratorio de desarrollo" completo dentro de su agente — levantar nginx, bases de datos, servicios propios, etc. Docker no da esto de forma segura.

## Comparativa determinante

| Criterio | Docker | LXD | Veredicto |
|---|---|---|---|
| SO invitado completo | ❌ No | ✅ Sí | LXD |
| systemd / systemctl | ❌ No | ✅ Sí | LXD |
| Nesting (contenedores dentro) | ⚠️ Peligroso (socket) | ✅ Seguro | LXD |
| Aislamiento filesystem host | ⚠️ Por montaje explícito | ✅ Nativo, zero acceso | LXD |
| Ver código base LAIA (host) | ⚠️ Si monta mal | ❌ No existe ruta | LXD |
| Snapshots | ⚠️ Requiere plugin | ✅ Nativo | LXD |

## Por qué Docker se descarta

- Sin systemd → el empleado no puede `systemctl start nginx`
- Nesting requiere Docker socket o DinD → riesgo de escape al host
- Docker está diseñado para una aplicación por contenedor, no un entorno de desarrollo

## Por qué LXD funciona

- Root dentro del contenedor, UID sin privilegios en el host (unprivileged container)
- Rutas del host (`/home/laia-arch/`) simplemente no existen dentro del LXD
- Aislamiento de red propio (subred 10.0.0.x)
- Snapshots nativos para recovery
- ~20-30MB RAM en idle, igual que Docker

## Exposición web (proxy inverso)

```
Host (nginx :80/:443)
  └── empleado.tuempresa.com → 10.0.0.50 (LXD laia-empleado)
```

El empleado levanta su nginx en el contenedor, nginx del host redirige. El empleado nunca toca el host.

## Alternativa

Docker como backup documentado en `agentes-docker-alternativa.md` por si LXD presenta problemas en Dell 9020.

## Validación pendiente

1. Verificar que LXD está instalado en Dell 9020
2. Medir consumo baseline con un agente de prueba
3. Configurar bridge de red 10.0.0.0/24
4. Configurar nginx proxy inverso en host

## Fuente

Conversación con Gemini + validación Jorge Miralles


> 📅 Documentado: 2026-05-08
