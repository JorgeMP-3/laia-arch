# LAIA Plugins

Host-level plugins for LAIA Core. These are loaded by the main agent process
and have access to the full system.

## Active plugins
- **workspace-context**: DB-first nodal memory provider. Injects workspace indexes into system prompts.
- **doyouwin**: Context engine that injects memories/doyouwin/*.md as context.

## Note
These plugins are only visible to LAIA Core (host). Personal agent containers
inside LXD do NOT have access to host plugins. They use their own plugin system
at `/opt/laia/plugins/`.
