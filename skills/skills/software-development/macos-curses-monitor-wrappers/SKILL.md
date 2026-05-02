---
name: macos-curses-monitor-wrappers
description: Build and expose real-time curses-based monitoring tools on macOS with simple shell commands, avoiding common PATH/TERM/wrapper mistakes.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [macos, curses, monitoring, wrappers, terminal, python, debugging]
---

# macOS curses monitor wrappers

Use this when creating terminal dashboards/monitors on macOS that:
- run continuously with `curses`
- are written in Python stdlib
- should be launched by short commands like `sysinfo`, `dockerinfo`, `netinfo`, `monitor`
- will be used over SSH or in terminal apps

## Goal
Create Python monitor scripts under a stable directory, then expose them via tiny Bash wrappers in `~/bin` so the user does **not** need to type `python3 /full/path/script.py`.

## Recommended layout

```text
~/.server-scripts/
  sysinfo_monitor.py
  docker_monitor.py
  net_monitor.py
  monitor.py

~/bin/
  sysinfo
  dockerinfo
  netinfo
  monitor
```

## Important lessons / pitfalls

### 1. Never overwrite the real Python scripts with wrappers
A previous failure came from accidentally writing wrapper content into the `.py` files themselves.

**Rule:**
- Python code lives only in `~/.server-scripts/*.py`
- Wrappers live only in `~/bin/*`

### 2. `curses` needs a real terminal
`curses.wrapper(...)` will fail with errors like:
- `setupterm: could not find terminal`

This happens in non-interactive environments or when `TERM` is missing.

**Fix:** wrappers should export a default TERM.

```bash
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
python3 /Users/USERNAME/.server-scripts/sysinfo_monitor.py "$@"
```

### 3. Test curses apps in a PTY, not plain noninteractive shell
Syntax checks are not enough.

Verification stack:
1. `python3 -m py_compile ...`
2. launch in a PTY/background terminal
3. confirm it stays running and does not emit `Traceback`

### 4. Don’t use `ord('ESC')`
Python `ord()` accepts only one character.

**Wrong:**
```python
ord('ESC')
```

**Correct:**
```python
27
```

Use quit handling like:

```python
key = win.getch()
if key in (ord('q'), ord('Q'), 27):
    break
```

### 5. Keep counts separate from lists
In dashboards, don’t reuse one variable for both:
- integer counts
- list data structures

Bad pattern:
```python
c_running = 5
c_running[:10]  # crash
```

Use explicit names:
```python
running_list, stopped_list = get_docker_containers()
c_total, c_running_count, c_images = get_docker_counts()
```

### 6. macOS command assumptions differ from Linux
For macOS monitors, prefer:
- CPU: `top -F -R -l 1 -n 0`
- memory: `vm_stat`, `sysctl -n hw.memsize`
- network: `ifconfig`, `lsof -i -P -n -sTCP:LISTEN`, `netstat -an`, `/etc/resolv.conf`
- docker: `docker ps`, `docker stats --no-stream`, `docker images`, `docker volume ls`, `docker network ls`

Avoid Linux-only assumptions unless checked first.

## Implementation steps

1. Write the full Python monitor into `~/.server-scripts/<name>_monitor.py`
2. Make it executable
3. Create a wrapper in `~/bin/<command>`:

```bash
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
python3 /Users/USERNAME/.server-scripts/<script>.py "$@"
```

4. `chmod +x` both script and wrapper
5. Ensure `~/bin` is on `PATH`
6. Verify with:

```bash
python3 -m py_compile ~/.server-scripts/*.py
which sysinfo dockerinfo netinfo monitor
```

7. PTY runtime check: start each command in an interactive terminal and confirm no traceback

## Minimal wrapper examples

### sysinfo
```bash
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
python3 /Users/USERNAME/.server-scripts/sysinfo_monitor.py "$@"
```

### dockerinfo
```bash
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
python3 /Users/USERNAME/.server-scripts/docker_monitor.py "$@"
```

### netinfo
```bash
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
python3 /Users/USERNAME/.server-scripts/net_monitor.py "$@"
```

### monitor
```bash
#!/bin/bash
export TERM="${TERM:-xterm-256color}"
python3 /Users/USERNAME/.server-scripts/monitor.py "$@"
```

## Verification checklist

- [ ] `.py` files still contain real Python, not wrapper shell code
- [ ] wrappers exist in `~/bin`
- [ ] `~/bin` is on `PATH`
- [ ] `python3 -m py_compile` passes
- [ ] launching from PTY does not emit traceback
- [ ] quit keys work with `q`, `Q`, `ESC`
- [ ] combined dashboard uses separate variables for counts vs lists

## When to use this skill
Use it whenever a user wants:
- a persistent terminal dashboard
- one-word commands for Python tools
- cyberpunk/htop-style monitors on macOS
- SSH-friendly monitoring scripts without extra dependencies
