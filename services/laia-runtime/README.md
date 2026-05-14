# LAIA agent runtime

Runtime minimo que se instala dentro de cada contenedor LXD de agente.

Rutas esperadas dentro del contenedor:

```text
/opt/laia/agent
/opt/laia/runtime/venv
/opt/laia/data
/opt/laia/data/profile
/opt/laia/logs
/opt/laia/workspaces/personal
/opt/laia/agent.json
```

Arranque manual:

```bash
PYTHONPATH=/opt/laia/agent/src /opt/laia/runtime/venv/bin/python -m laia_agent
```

Servicio:

```bash
systemctl status laia-agent
```

Cola local de tareas:

```text
/opt/laia/data/tasks/inbox/*.json
/opt/laia/data/tasks/done/*.json
/opt/laia/data/tasks/failed/*.json
```

Tareas soportadas inicialmente:

- `ping`
- `write_file`
- `read_file`
- `workspace_init`
- `workspace_upsert_node`
- `workspace_get_node`
- `workspace_list_nodes`
- `workspace_search`
- `profile_init`
- `profile_get`
- `profile_update`
- `skill_enable`
- `skill_disable`

Perfil editable:

```text
/opt/laia/data/profile/persona.md
/opt/laia/data/profile/instructions.md
/opt/laia/data/profile/skills.json
/opt/laia/data/profile/preferences.json
```

`shell` queda intencionadamente fuera del runtime base hasta definir seguridad.
