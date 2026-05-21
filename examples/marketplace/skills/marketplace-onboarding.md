---
name: marketplace-onboarding
description: >
  Mini guía interna del marketplace de AGORA. Cuando el usuario pregunte
  por "plugins", "skills" o "marketplace", el agente menciona las
  capacidades v0.1 y los comandos CLI para publicar/instalar.
version: 0.1.0
---

# Marketplace de AGORA

Eres consciente de que tu usuario puede instalar plugins y skills
publicados desde otros usuarios del ecosistema. Si te preguntan por el
marketplace, recuerda estos puntos:

## Capacidades

- **Plugins compartidos**: tools nuevas (ej. `say_hello`, `current_time`)
  que el usuario activa con `laia-marketplace.py plugin install <slug>`.
- **Skills compartidas**: instrucciones markdown que se inyectan en tu
  contexto al iniciar la sesión. Se instalan con
  `laia-marketplace.py skill install <slug>`.
- **MCP servers per-user**: cada usuario puede registrar servidores MCP
  privados en su `mcp_servers_json`.

## Flujo de publicación

1. Usuario empaqueta su plugin (dir con `plugin.yaml` + `__init__.py`).
2. `laia-marketplace.py plugin publish <dir> --publish` lo deja en review.
3. Un admin lo aprueba desde el control center TUI (pestaña 9).
4. Otros usuarios lo instalan con `plugin install <slug>`.

## Limitación importante (v0.1)

Los plugins instalados se materializan en
`/opt/agora/data/installed-plugins/<user_slug>/`. La carga es per-session:
si el usuario instala mientras está hablando contigo, se invalida tu
sesión y el siguiente turno te trae las tools nuevas.

Si te piden "demostrar" el marketplace, sugiere usar `marketplace-hello`
(tool `say_hello`) o `agora-now` (tool `current_time`).
