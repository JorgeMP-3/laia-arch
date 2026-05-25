# Hermes Core — Commands

## Metadata

- ID: `73`
- Slug: `hermes-core-commands-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-commands-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:23:22.200732+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `hermes-core-commands-detail`

## Summary

Sistema de slash commands centralizado: COMMAND_REGISTRY, CommandDef, categorías y consumers

## Body

# Hermes Core — Commands

Sistema de slash commands centralizado — COMMAND_REGISTRY es la fuente única de verdad.

## CommandDef Dataclass

```python
@dataclass(frozen=True)
class CommandDef:
    name: str                          # "new", "clear", "history"
    description: str                   # human-readable
    category: str                     # "Session", "Configuration", etc.
    aliases: tuple[str, ...] = ()      # ("bg",)
    args_hint: str = ""               # "<prompt>", "[name]"
    subcommands: tuple[str, ...] = () # tab-completable subcommands
    cli_only: bool = False
    gateway_only: bool = False
    gateway_config_gate: str | None = None
```

## COMMAND_REGISTRY (~40 commands)

### Session (~10)
- new / reset — nueva sesión
- clear — limpiar pantalla + nueva sesión (cli_only)
- history — mostrar historial (cli_only)
- save — guardar conversación (cli_only)
- retry — reenviar último mensaje
- undo — remover último exchange
- title — poner título a sesión
- branch / fork — bifurcar sesión
- compress — comprimir manualmente
- rollback — restaurar checkpoints

### Configuration (~10)
- model — cambiar modelo
- provider — cambiar provider
- tools — tool config
- skills — skills config
- system — edit system prompt
- env — ver/set env vars
- context — context budget
- temperature — set temperature
- cache — cache control
- max_tokens — max output tokens

### Tools (~5)
- tool — invoke tool directamente
- tools list — list available tools
- tools enable/disable
- delegate — delegation control

### Skills (~3)
- /skills — browse/search/install skills
- skill — invoke skill
- skills sync — sync skills

### Navigation
- ls, cd, pwd — filesystem navigation

### Debug/Utility
- debug — debug mode
- doctor — health check
- logs — view logs
- test — run tests
- exit / quit

## Consumers del Registry

1. CLI (HermesCLI.process_command()) — resolve_command() para aliases
2. Gateway — GATEWAY_KNOWN_COMMANDS frozenset + resolve_command()
3. Telegram — telegram_bot_commands() genera BotCommand menu
4. Slack — slack_subcommand_map() para /hermes routing
5. Help — gateway_help_lines() genera /help output
6. Autocomplete — SlashCommandCompleter para prompt_toolkit

## Slash Command Resolution

resolve_command(token: str) -> str:
- Matchea name exacto
- Matchea aliases
- Case insensitive
- Retorna canonical name

## Skill Commands

agent/skill_commands.py:
- Escanea ~/.laia/skills/ dynamically
- Inyecta como user message (no system prompt) — preserva prompt caching
- Shared entre CLI y gateway

## Command Categories

Session, Configuration, Tools, Skills, Navigation, Debug, Utility, Info, Agent

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Commands

# Hermes Core — Commands

Sistema de slash commands centralizado — COMMAND_REGISTRY es la fuente única de verdad.

## CommandDef Dataclass

```python
@dataclass(frozen=True)
class CommandDef:
    name: str                          # "new", "clear", "history"
    description: str                   # human-readable
    category: str                     # "Session", "Configuration", etc.
    aliases: tuple[str, ...] = ()      # ("bg",)
    args_hint: str = ""               # "<prompt>", "[name]"
    subcommands: tuple[str, ...] = () # tab-completable subcommands
    cli_only: bool = False
    gateway_only: bool = False
    gateway_config_gate: str | None = None
```

## COMMAND_REGISTRY (~40 commands)

### Session (~10)
- new / reset — nueva sesión
- clear — limpiar pantalla + nueva sesión (cli_only)
- history — mostrar historial (cli_only)
- save — guardar conversación (cli_only)
- retry — reenviar último mensaje
- undo — remover último exchange
- title — poner título a sesión
- branch / fork — bifurcar sesión
- compress — comprimir manualmente
- rollback — restaurar checkpoints

### Configuration (~10)
- model — cambiar modelo
- provider — cambiar provider
- tools — tool config
- skills — skills config
- system — edit system prompt
- env — ver/set env vars
- context — context budget
- temperature — set temperature
- cache — cache control
- max_tokens — max output tokens

### Tools (~5)
- tool — invoke tool directamente
- tools list — list available tools
- tools enable/disable
- delegate — delegation control

### Skills (~3)
- /skills — browse/search/install skills
- skill — invoke skill
- skills sync — sync skills

### Navigation
- ls, cd, pwd — filesystem navigation

### Debug/Utility
- debug — debug mode
- doctor — health check
- logs — view logs
- test — run tests
- exit / quit

## Consumers del Registry

1. CLI (HermesCLI.process_command()) — resolve_command() para aliases
2. Gateway — GATEWAY_KNOWN_COMMANDS frozenset + resolve_command()
3. Telegram — telegram_bot_commands() genera BotCommand menu
4. Slack — slack_subcommand_map() para /hermes routing
5. Help — gateway_help_lines() genera /help output
6. Autocomplete — SlashCommandCompleter para prompt_toolkit

## Slash Command Resolution

resolve_command(token: str) -> str:
- Matchea name exacto
- Matchea aliases
- Case insensitive
- Retorna canonical name

## Skill Commands

agent/skill_commands.py:
- Escanea ~/.laia/skills/ dynamically
- Inyecta como user message (no system prompt) — preserva prompt caching
- Shared entre CLI y gateway

## Command Categories

Session, Configuration, Tools, Skills, Navigation, Debug, Utility, Info, Agent

> 📅 Documentado: 2026-05-08
