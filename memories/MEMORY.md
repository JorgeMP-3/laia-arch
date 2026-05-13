MEMORY — Lo esencial y no repetible > Lecciones aprendidas (no obvias): **Docker Desktop "Lingering processes"**: los contenedores siguen funcionando con Docker Engine aunque el GUI dé warnings. Verificar con `docker ps`.
§
Jorge Miralles · Mac mini Myhelpcar · Docker en /home/familiamp/memory/servidor-docker.md
§
## Servidor Dell OptiPlex 9020 (laia-server) · laia-arch
- Docs: /home/laia-arch/LAIA/docs/docs/
- Stack: Arete (:8000), WordPress Docker, nginx, Cloudflare Tunnel
- Hermes venv: ~/laia-arch/hermes-agent/venv/ · workspace-ui :8077
- gsave: ~/bin/gsave
- Vision: Ollama qwen2.5vl:7b http://127.0.0.1:11434/v1
- NO emojis in voice mode
§
Telegram/OpenClaw slash commands must be explicitly registered in the gateway/plugin layer; creating a Hermes skill with triggers like `/usageai` does not automatically make the Telegram bot recognize that slash command.
§
delegation model/base_url en config.yaml NO se aplican en sesiones ya activas — hay que usar flags `-m MiniMax-M2.7 --provider minimax` en cada lanzamiento de subagente, o hacer /reset de sesión para que coja la config fresca. En `~/.hermes/config.yaml`, `delegation.max_concurrent_children` está configurado en 20. Siempre verificar que los subagentes usan MiniMax con esos flags explícitos.
§
NO emojis in voice mode — awkward when narrated. Only use emojis in text chat.
§
Vision: Ollama qwen2.5vl:7b en http://127.0.0.1:11434/v1. Funciona bien (~15-20s/imagen). No optimizar. Procedure: vision_analyze con image_url local + question en español. No MLX.
§
LAIA ecosystem: agente=LAIA, ARCH=modo admin host (Jorge, VPN), AGORA=modo equipo (empleados, Docker). Repos separados. Workspace maestro: laia-ecosystem. Jorge prefiere preguntar y pulir conceptos ANTES de escribir planes.
§
LAIA Tools: plan laia-tools-plan [agent-plan] en laia_arch. Bin: /home/laia-arch/LAIA/.laia-arch/bin/. Bypass funciona con inject de una sola vez. NO matar terminal tras tarea si el proyecto continúa — revisar CC con read_all antes de cerrar sesión.