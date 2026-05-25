# Apple/macOS Skills

## Metadata

- ID: `95`
- Slug: `skills-apple`
- Kind: `doc`
- Status: `active`
- Filename: `skills-apple.md`
- Parent: `hermes`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:02.104648+00:00`
- Updated at: `2026-05-08T08:34:02.104648+00:00`
- Aliases: `skills-apple`

## Summary

Skills de Apple/macOS. Solo cargan en sistemas macOS. Ubicadas en `skills/apple/`.

## Body

# Apple Skills

# Integrated Tools — Apple Skills

## Resumen

Skills de Apple/macOS. Solo cargan en sistemas macOS. Ubicadas en `skills/apple/`.

## Skills disponibles

| Skill | CLI | Descripcion |
|---|---|---|
| `apple-notes` | `memo` | CRUD de Apple Notes |
| `apple-reminders` | `remindctl` | Tareas en Apple Reminders |
| `findmy` | AppleScript + screencapture | Localizacion de dispositivos/AirTags |
| `imessage` | `imsg` | Enviar/recibir iMessages |

## Instalacion de herramientas

```bash
# Notes
brew tap antoniorodr/memo && brew install antoniorodr/memo/memo

# Reminders
brew install steipete/tap/remindctl

# iMessage
brew install steipete/tap/imsg

# FindMy UI automation (opcional)
brew install steipete/tap/peekaboo
```

## Permisos requeridos

Todas las skills requieren permisos de Automatizacion en macOS:

- **Notes**: System Settings → Privacy → Automation → Notes.app
- **Reminders**: Automation access cuando se solicita
- **Messages**: Full Disk Access + Automation para Messages.app
- **FindMy**: Screen Recording permission

## Apple Notes (apple-notes)

### Cuando usar
- Usuario pide crear, ver o buscar Apple Notes
- Guardar info en Notes.app para acceso cross-device
- Organizar notas en carpetas

### Cuando NO usar
- Obsidian vault → skill `obsidian`
- Bear Notes → app separada (no soportada)
- Notas internas de agente → tool `memory`

### Comandos

```bash
memo notes                    # Listar todas
memo notes -f "Folder Name"  # Filtrar por carpeta
memo notes -s "query"        # Buscar
memo notes -a                # Crear (interactivo)
memo notes -a "Title"        # Crear con titulo
memo notes -e                # Editar (interactivo)
memo notes -d                # Eliminar (interactivo)
memo notes -m                # Mover a carpeta
memo notes -ex               # Exportar a HTML/Markdown
```

### Limitaciones
- No puede editar notas con imagenes o attachments
- Prompts interactivos requieren terminal con PTY

## Apple Reminders (apple-reminders)

### Cuando usar
- Usuario menciona "reminder" o "Reminders app"
- Crear to-dos con due dates que sincronicen a iOS
- Gestionar listas de Apple Reminders

### Cuando NO usar
- Scheduling de alertas de agente → cronjob tool
- Eventos de calendario → Apple Calendar o Google Calendar
- Project task management → GitHub Issues, Notion

### Comandos

```bash
remindctl                    # Hoy
remindctl today              # Hoy
remindctl tomorrow           # Manana
remindctl week               # Esta semana
remindctl overdue            # Vencidas
remindctl all                # Todo
remindctl 2026-01-04         # Fecha especifica
remindctl list               # Ver listas
remindctl list Work          # Lista especifica
remindctl list Projects --create  # Crear lista
remindctl add "Buy milk"                  # Crear
remindctl add --title "Call mom" --due tomorrow
remindctl complete 1 2 3                  # Completar por ID
remindctl delete 4A83 --force              # Eliminar
```

### Formatos de fecha
- `today`, `tomorrow`, `yesterday`
- `YYYY-MM-DD`
- `YYYY-MM-DD HH:mm`
- ISO 8601

## FindMy (findmy)

### Cuando usar
- "Donde esta mi [dispositivo/cat/llaves/bolso]?"
- Rastrear AirTags
- Ver localizacion de dispositivos (iPhone, iPad, Mac, AirPods)
- Monitorizar movimiento de mascota (patrol routes de AirTag)

### Metodo 1: AppleScript + Screenshot (Basic)

```bash
osascript -e 'tell application "FindMy" to activate'
sleep 3
screencapture -w -o /tmp/findmy.png
```

Luego analizar con `vision_analyze`:

```
vision_analyze(image_url="/tmp/findmy.png", question="What devices/items are shown and their locations?")
```

### Metodo 2: Peekaboo (Recomendado)

```bash
peekaboo see --app "FindMy" --annotate --path /tmp/findmy-ui.png
peekaboo click --on B3 --app "FindMy"
peekaboo image --app "FindMy" --path /tmp/findmy-detail.png
```

### Limitaciones
- FindMy NO tiene CLI ni API
- AirTags solo actualizan mientras la pagina esta abierta
- Screen Recording permission obligatoria
- AppleScript puede romperse entre versiones de macOS

### Reglas
1. Mantener FindMy en foreground al rastrear AirTags
2. Usar `vision_analyze` para leer screenshots
3. Para tracking continuo, usar cronjob periodico

## iMessage (imessage)

### Cuando usar
- Enviar iMessage o SMS
- Leer historial de conversaciones
- Ver chats recientes de Messages.app

### Cuando NO usar
- Telegram/Discord/Slack/WhatsApp → gateway channel correspondiente
- Group chat management → no soportado
- Bulk messaging → siempre confirmar primero

### Comandos

```bash
imsg chats --limit 10 --json              # Listar chats
imsg history --chat-id 1 --limit 20 --json # Ver historial
imsg send --to "+141****1212" --text "Hi" # Enviar
imsg send --to "+141****1212" --file /path/img.jpg # Con attachment
imsg send --to "+1..." --service imessage # Forzar iMessage
imsg send --to "+1..." --service sms      # Forzar SMS
imsg watch --chat-id 1 --attachments      # Watch new messages
```

### Reglas
1. **Siempre confirmar** recipient y contenido antes de enviar
2. **Nunca enviar** a numeros desconocidos sin aprobacion
3. **Verificar** que las rutas de archivos existen
4. **No spam** — rate-limit yourself

## Nodos relacionados

- `integrated-tools` — indice maestro
- `integrated-workspace-tools` — skills workspace
- `dogfood-skill` — QA testing


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Apple/macOS Skills

# Apple Skills

# Integrated Tools — Apple Skills

## Resumen

Skills de Apple/macOS. Solo cargan en sistemas macOS. Ubicadas en `skills/apple/`.

## Skills disponibles

| Skill | CLI | Descripcion |
|---|---|---|
| `apple-notes` | `memo` | CRUD de Apple Notes |
| `apple-reminders` | `remindctl` | Tareas en Apple Reminders |
| `findmy` | AppleScript + screencapture | Localizacion de dispositivos/AirTags |
| `imessage` | `imsg` | Enviar/recibir iMessages |

## Instalacion de herramientas

```bash
# Notes
brew tap antoniorodr/memo && brew install antoniorodr/memo/memo

# Reminders
brew install steipete/tap/remindctl

# iMessage
brew install steipete/tap/imsg

# FindMy UI automation (opcional)
brew install steipete/tap/peekaboo
```

## Permisos requeridos

Todas las skills requieren permisos de Automatizacion en macOS:

- **Notes**: System Settings → Privacy → Automation → Notes.app
- **Reminders**: Automation access cuando se solicita
- **Messages**: Full Disk Access + Automation para Messages.app
- **FindMy**: Screen Recording permission

## Apple Notes (apple-notes)

### Cuando usar
- Usuario pide crear, ver o buscar Apple Notes
- Guardar info en Notes.app para acceso cross-device
- Organizar notas en carpetas

### Cuando NO usar
- Obsidian vault → skill `obsidian`
- Bear Notes → app separada (no soportada)
- Notas internas de agente → tool `memory`

### Comandos

```bash
memo notes                    # Listar todas
memo notes -f "Folder Name"  # Filtrar por carpeta
memo notes -s "query"        # Buscar
memo notes -a                # Crear (interactivo)
memo notes -a "Title"        # Crear con titulo
memo notes -e                # Editar (interactivo)
memo notes -d                # Eliminar (interactivo)
memo notes -m                # Mover a carpeta
memo notes -ex               # Exportar a HTML/Markdown
```

### Limitaciones
- No puede editar notas con imagenes o attachments
- Prompts interactivos requieren terminal con PTY

## Apple Reminders (apple-reminders)

### Cuando usar
- Usuario menciona "reminder" o "Reminders app"
- Crear to-dos con due dates que sincronicen a iOS
- Gestionar listas de Apple Reminders

### Cuando NO usar
- Scheduling de alertas de agente → cronjob tool
- Eventos de calendario → Apple Calendar o Google Calendar
- Project task management → GitHub Issues, Notion

### Comandos

```bash
remindctl                    # Hoy
remindctl today              # Hoy
remindctl tomorrow           # Manana
remindctl week               # Esta semana
remindctl overdue            # Vencidas
remindctl all                # Todo
remindctl 2026-01-04         # Fecha especifica
remindctl list               # Ver listas
remindctl list Work          # Lista especifica
remindctl list Projects --create  # Crear lista
remindctl add "Buy milk"                  # Crear
remindctl add --title "Call mom" --due tomorrow
remindctl complete 1 2 3                  # Completar por ID
remindctl delete 4A83 --force              # Eliminar
```

### Formatos de fecha
- `today`, `tomorrow`, `yesterday`
- `YYYY-MM-DD`
- `YYYY-MM-DD HH:mm`
- ISO 8601

## FindMy (findmy)

### Cuando usar
- "Donde esta mi [dispositivo/cat/llaves/bolso]?"
- Rastrear AirTags
- Ver localizacion de dispositivos (iPhone, iPad, Mac, AirPods)
- Monitorizar movimiento de mascota (patrol routes de AirTag)

### Metodo 1: AppleScript + Screenshot (Basic)

```bash
osascript -e 'tell application "FindMy" to activate'
sleep 3
screencapture -w -o /tmp/findmy.png
```

Luego analizar con `vision_analyze`:

```
vision_analyze(image_url="/tmp/findmy.png", question="What devices/items are shown and their locations?")
```

### Metodo 2: Peekaboo (Recomendado)

```bash
peekaboo see --app "FindMy" --annotate --path /tmp/findmy-ui.png
peekaboo click --on B3 --app "FindMy"
peekaboo image --app "FindMy" --path /tmp/findmy-detail.png
```

### Limitaciones
- FindMy NO tiene CLI ni API
- AirTags solo actualizan mientras la pagina esta abierta
- Screen Recording permission obligatoria
- AppleScript puede romperse entre versiones de macOS

### Reglas
1. Mantener FindMy en foreground al rastrear AirTags
2. Usar `vision_analyze` para leer screenshots
3. Para tracking continuo, usar cronjob periodico

## iMessage (imessage)

### Cuando usar
- Enviar iMessage o SMS
- Leer historial de conversaciones
- Ver chats recientes de Messages.app

### Cuando NO usar
- Telegram/Discord/Slack/WhatsApp → gateway channel correspondiente
- Group chat management → no soportado
- Bulk messaging → siempre confirmar primero

### Comandos

```bash
imsg chats --limit 10 --json              # Listar chats
imsg history --chat-id 1 --limit 20 --json # Ver historial
imsg send --to "+141****1212" --text "Hi" # Enviar
imsg send --to "+141****1212" --file /path/img.jpg # Con attachment
imsg send --to "+1..." --service imessage # Forzar iMessage
imsg send --to "+1..." --service sms      # Forzar SMS
imsg watch --chat-id 1 --attachments      # Watch new messages
```

### Reglas
1. **Siempre confirmar** recipient y contenido antes de enviar
2. **Nunca enviar** a numeros desconocidos sin aprobacion
3. **Verificar** que las rutas de archivos existen
4. **No spam** — rate-limit yourself

## Nodos relacionados

- `integrated-tools` — indice maestro
- `integrated-workspace-tools` — skills workspace
- `dogfood-skill` — QA testing


> 📅 Documentado: 2026-05-08
