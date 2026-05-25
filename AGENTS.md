# AGENTS.md — Entry point para IAs agénticas en LAIA

Este archivo lo leen automáticamente Codex, OpenCode, Aider y otras herramientas
agénticas convencionales. Claude Code lee `CLAUDE.md`, que apunta aquí. Si eres una
IA que va a tocar algo en este repositorio, **léelo entero antes de actuar**.

## Qué es LAIA, en un párrafo

LAIA es un ecosistema de agentes de IA personales con dos expresiones: **LAIA-ARCH**
(la capa de administración del host, sólo accesible a Jorge, invisible para los usuarios)
y **LAIA-AGORA** (la plataforma multi-usuario en un container, lo que los usuarios llaman
simplemente "LAIA"). Dentro de LAIA-AGORA cada usuario tiene su agente personal
(**PA-AGORA**) en un container privado donde es root. El modelo conceptual completo está
en `LAIA_ECOSYSTEM.md` — es el documento canónico del proyecto.

## Con quién hablas

El desarrollador y único operador de LAIA-ARCH es **Jorge Miralles Pérez**. Dirígete a
él como Jorge.

## Las 5 reglas absolutas

1. **`LAIA_ECOSYSTEM.md` es canónico.** Si cualquier otra cosa (docs/, código viejo,
   memoria, tu intuición) contradice este archivo, gana el archivo.
2. **No inventes.** Paths, endpoints, componentes — si no aparecen en `LAIA_ECOSYSTEM.md`
   o en `docs/db-export/`, no existen.
3. **Toda integración nueva necesita un test en `~/LAIA/tests/`.** Código sin test que
   verifique la integración contra el resto del sistema está incompleto. Antes de
   declarar "hecho", corres la suite completa para confirmar que no rompiste nada.
4. **Antes de cerrar tu turno** actualiza lo que aplique:
   - `workflow/changelog.md` si cambiaste código.
   - `workflow/problems.md` si descubriste un bug (aunque no lo arregles).
   - `workflow/security.md` si tocaste credenciales, permisos, red o secrets.
5. **Nunca edites `LAIA_ECOSYSTEM.md` sin consentimiento explícito de Jorge.**

## Branching operativo

- `main` es desarrollo/integración validada.
- `stable` es producción. El instalador por defecto debe apuntar a `stable`.
- No hagas commits directos a `stable` salvo hotfix aprobado por Jorge.
- Los tags `vX.Y.Z` se crean solo sobre `stable`.
- El runbook completo vive en `workflow/release-flow.md`.

## A dónde ir después

| Archivo | Cuándo |
|---|---|
| `LAIA_ECOSYSTEM.md` | Para entender qué es LAIA. Documento canónico. |
| `workflow/00-start-here.md` | Índice de los archivos operativos. |
| `workflow/01-canonical-sources.md` | Dónde vive la verdad para cada tema. |
| `workflow/02-how-to-work.md` | Branches, commits, tests, cierre de turno. |
| `workflow/03-multi-ai-coordination.md` | Sólo si trabajas en paralelo con otra IA. |
| `docs/db-export/` | Detalle técnico exhaustivo (auto-generado desde `workspace.db`). |

## Referencia rápida de paths

| Path | Qué contiene |
|---|---|
| `~/LAIA/` | Código del proyecto. |
| `~/.laia/` | Runtime de LAIA-ARCH: credenciales (`auth.json`, `.env`), config, atlas. |
| `/srv/laia/` | Datos factory: containers, workspaces de usuarios, agora.db. |
| `/opt/laia/` | Copia instalada de LAIA en producción (no se usa en dev). |
| `~/LAIA/tests/` | Tests del ecosistema. **Tu trabajo nuevo va aquí.** |
| `~/LAIA/workflow/` | Cooperación entre IAs: rules, changelog, problems, plans. |
| `~/LAIA/docs/db-export/` | Export auto-generado de `workspace.db`. |
| `~/.laia/workspaces/laia-ecosystem/workspace.db` | Base de conocimiento técnico exhaustivo. |

## Si encuentras una contradicción

Entre `LAIA_ECOSYSTEM.md` y otra fuente: gana el primero. Si te bloquea, **escala a
Jorge antes de actuar** — no decidas tú cuál tiene razón.
