# LAIA Skills

Agent skills directory. Skills extend LAIA agent capabilities.

## Structure
Each subdirectory is a skill with its own `SKILL.md` manifest.
Skills are auto-discovered at agent startup.

## Creating a skill
1. Create a directory: `skills/<category>/<my-skill>/`
2. Add `SKILL.md` with frontmatter (name, description, version, author, license, metadata.laia)
3. The agent will discover it on next restart

**Authoring standards (required reading before any PR): [`STANDARDS.md`](STANDARDS.md).**
