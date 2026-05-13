# Ecosistema LAIA — Arquitectura y Conceptos

> Documento vivo. Refleja las decisiones tomadas hasta la fecha. Pendientes marcados con ⚠️.

---

## Visión general

LAIA es un fork evolucionado de Hermes Agent orientado al uso profesional en equipos. Sus principales mejoras sobre el upstream son: manejo de contexto en proyectos grandes, división del trabajo por áreas, interfaz UI, y un ecosistema multi-agente con roles diferenciados.

**Servidor objetivo:** Intel Xeon + 32GB RAM (en camino).
**Equipo:** 10 empleados + 1 administrador (Jorge).

---

## Componentes del ecosistema

### LAIA-ARCH
- **Qué es:** La instancia del administrador. Corre directamente en el host, sin contenedor.
- **Quién la usa:** Solo Jorge.
- **Acceso:** Únicamente por VPN al host. No expuesto en laiajmp.org ni en ningún dominio público.
- **Capacidades:** Control total del host, todas las herramientas disponibles, acceso al Docker socket, gestión de todos los contenedores, acceso a todos los workspaces.
- **Interfaz:** La UI actual (workspace-ui) en un puerto local.

---

### AGORA
- **Qué es:** El conjunto de todos los usuarios y sus agentes. Un contenedor Docker por empleado.
- **Quién lo forma:** Los 10 empleados, cada uno con su propio agente aislado.
- **Acceso:** Vía `https://laiajmp.org` (portal de login centralizado) o app de escritorio Tauri.
- **Interfaz:** Una única app React (proyecto nuevo, diseño limpio) que se conecta al contenedor del usuario tras autenticarse. La misma app empaquetada con Tauri sirve como cliente de escritorio.

#### Acceso y autenticación
```
Usuario abre laiajmp.org o app Tauri
        ↓
Login: usuario + contraseña (gestionado en el servidor)
        ↓
Auth proxy (nginx) identifica el contenedor del usuario
        ↓
Enruta peticiones a 127.0.0.1:920X (su contenedor)
        ↓
El usuario nunca ve puertos ni URLs internas
```

- **Web:** laiajmp.org, diseño responsive (funciona también en móvil sin app nativa)
- **Escritorio:** App Tauri que apunta siempre al servidor remoto (laiajmp.org)
- **Móvil:** Web responsive, sin app nativa por ahora

#### Agentes de AGORA
Cada empleado tiene su propio agente con:
- **Puede personalizar:** SOUL.md, MEMORY.md, USER.md, config.yaml (dentro de límites), sus propias skills/tools/plugins.
- **No puede ver ni modificar:** El código base de LAIA/Hermes (protegido, ver sección de protección de código).
- **Toolset restringido:** Sin acceso a `command_center`, `cronjob`, backends de terminal no locales, Docker socket.
- **Aislamiento:** Solo acceso de escritura a su propio `/opt/data/`. Terminal local restringido a su contenedor.

---

### LAIA (el agente coordinador)
- **Qué es:** Un agente autónomo cuyo objetivo es coordinar, organizar y dar coherencia al trabajo del equipo. No pertenece a ningún usuario.
- **Nivel:** Corre en su propio contenedor (mismo nivel que los agentes de AGORA, no es admin).
- **Autonomía:** Alta. Opera 24/7 sin necesidad de ser activado manualmente.

#### Capacidades especiales (toolset `coordinator`)
| Herramienta | Descripción |
|-------------|-------------|
| `workspace_read_all` | Lectura de todos los workspaces de AGORA (monitorización) |
| `task_assign` | Crear tareas en el workspace de cualquier usuario |
| `report_generate` | Sintetizar información cruzada entre agentes |
| `suggest_to_arch` | Enviar sugerencias/informes a laia-arch vía canal dedicado |

#### Funciones principales
1. **Distribución de trabajo:** Mantiene un backlog priorizado y asigna tareas según capacidad y especialidad de cada empleado.
2. **Monitorización:** Heartbeat periódico — detecta agentes bloqueados o inactivos y reasigna si es necesario.
3. **Validador del Skill Marketplace:** Revisa skills/tools/plugins creados por usuarios antes de distribuirlos.
4. **Síntesis de conocimiento:** Puede bridgear aprendizajes relevantes entre agentes sin exponer datos privados.
5. **Canal con laia-arch:** Nodo de workspace dedicado donde LAIA deposita informes, alertas y sugerencias. laia-arch responde en ese canal.
6. **Informe diario:** Resumen automático para laia-arch con estado del equipo, avances, bloqueos y alertas.

#### Protocolo de escritura en workspaces ajenos
1. **Sugerencia** (normal): LAIA propone, el agente del usuario acepta o rechaza.
2. **Urgente**: LAIA escribe directamente, queda en audit log y notifica a laia-arch.
3. **Crítico**: LAIA escribe, notifica a laia-arch con justificación obligatoria.

#### Lo que LAIA NO es
- No es un jefe. Es un director de orquesta: sugiere, prioriza y organiza.
- No tiene nivel de admin. No puede modificar el código base ni gestionar contenedores.

---

## Skill Marketplace (interno)

```
Usuario crea skill/tool/plugin en su contenedor
        ↓
  /opt/data/mis-skills/
        ↓
  Publica via AGORA UI
        ↓
  LAIA lo recibe y valida (seguridad, calidad, conflictos con el core)
        ↓
  Aprobado → /opt/shared-skills/ (volumen compartido, solo lectura para todos)
        ↓
  Disponible para todos los agentes de AGORA y para laia-arch
        ↓
  laia-arch decide si entra al código oficial de LAIA
```

---

## Protección del código base

1. El código base vive en `/opt/hermes/` dentro del contenedor (parte de la imagen, no montado como volumen).
2. `file_operations` está restringida a rutas bajo `/opt/data/`.
3. El terminal arranca con working directory en `/opt/data/`.
4. El código Python se compila a `.pyc` y se eliminan los `.py` fuente de la imagen.

---

## Infraestructura de despliegue

```
[Servidor Xeon 32GB]
│
├── laia-arch (host nativo, acceso VPN)        ~8-10GB RAM
│
├── LAIA coordinador (contenedor)              ~2GB RAM
│   └── toolset: coordinator
│
└── AGORA — contenedores de empleados
    ├── agora-emp1   :9200   /opt/agora/emp1   ~1.5GB RAM
    ├── agora-emp2   :9201   /opt/agora/emp2   ~1.5GB RAM
    ├── ...
    └── agora-emp10  :9209   /opt/agora/emp10  ~1.5GB RAM

Total estimado: ~28GB RAM (dentro de los 32GB disponibles)

Cloudflare Tunnel → nginx (laiajmp.org)
    → /            → Auth proxy + AGORA React app
    → /api/{user}/ → contenedor del usuario (proxy autenticado)
    → /laia/       → coordinador LAIA
    [admin: solo VPN, no expuesto públicamente]
```

---

## La UI de AGORA

- **Proyecto nuevo** en `laia-agora/frontend/` (no fork de workspace-ui)
- **Stack:** React + Vite (mismo que workspace-ui actual)
- **Diseño:** Más limpio que workspace-ui actual, pensado para usuarios no técnicos
- **Features iniciales:** Las mismas áreas que tiene workspace-ui hoy (sin las features admin que no existen aún)
- **Tauri:** La misma app React empaquetada como cliente de escritorio. Siempre conecta al servidor remoto.
- **Responsive:** Funciona en móvil desde el navegador sin app nativa

---

## Nomenclatura definitiva

| Nombre | Qué es |
|--------|--------|
| **LAIA** | El producto/sistema completo. También el nombre del agente coordinador. |
| **LAIA-ARCH** | Instancia admin. Solo para Jorge. Acceso por VPN. |
| **AGORA** | El ecosistema de todos los usuarios y sus agentes. También el nombre de la UI. |
| **LAIA (agente)** | El coordinador autónomo. Contenedor propio, nivel usuario pero con toolset especial. |

---

## Pendientes por definir ⚠️

- ¿El coordinador LAIA tiene interfaz visible para los empleados en la AGORA UI? (¿Ven las tareas asignadas, pueden comunicarse con él directamente?)
- Nombre individual de cada agente de usuario dentro de AGORA (¿igual que el empleado? ¿nombre propio?)
- Protocolo exacto de comunicación LAIA ↔ laia-arch (¿workspace node? ¿API?)
- Criterios de validación del Skill Marketplace
- Política de actualizaciones: ¿automáticas o con aprobación?
- ¿LAIA tiene acceso de lectura a SOUL.md/USER.md de empleados o solo a workspaces de proyecto?
- Migración de la app actual de laiajmp.org (¿a qué subdominio se mueve?)
