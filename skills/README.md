# LAIA Skills

Agent skills directory. Skills extend LAIA agent capabilities.

## Structure
Each subdirectory is a skill with its own `SKILL.md` manifest.
Skills are auto-discovered at agent startup.

## Creating a skill
1. Create a directory: `skills/mi-skill/`
2. Add `SKILL.md` with metadata (name, version, description, tools)
3. The agent will discover it on next restart
