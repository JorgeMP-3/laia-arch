"""
Terminal UI for LAIA Server Control Panel
"""

import sys
import os
from pathlib import Path
from typing import Optional

try:
    import curses
except ImportError:
    curses = None

from config import (
    get_system_info, get_service_status, get_pm2_status,
    get_docker_containers, get_endpoint_health,
    systemd_action, pm2_action, docker_action, get_logs,
    ConfigManager, ServerState, DockerContainer,
    SYSTEMD_SERVICES, NGINX_CONFIG_PATH, DOCKER_COMPOSE_PATH
)

C = {
    'reset': curses.COLOR_WHITE,
    'header': curses.COLOR_BLUE,
    'green': curses.COLOR_GREEN,
    'red': curses.COLOR_RED,
    'yellow': curses.COLOR_YELLOW,
    'cyan': curses.COLOR_CYAN,
    'magenta': curses.COLOR_MAGENTA,
}

COLOR_MAP = {
    'reset': 1,
    'header': 2,
    'green': 3,
    'red': 4,
    'yellow': 5,
    'cyan': 6,
    'magenta': 7,
}

def cp(color_key):
    try:
        return curses.cp(COLOR_MAP.get(color_key, 1))
    except:
        return 0

class TUI:
    def __init__(self, stdscr):
        self.s = stdscr
        self.h, self.w = stdscr.getmaxyx()
        curses.curs_set(0)
        curses.use_default_colors()
        curses.noecho()
        curses.cbreak()
        self.s.keypad(True)
        for i in range(1, 8):
            try:
                curses.init_pair(i, C[['reset','header','green','red','yellow','cyan','magenta'][i-1]], -1)
            except curses.error:
                pass
        self.s.clear()
        self.pad_y = 0

    def clear(self):
        self.s.clear()
        self.h, self.w = self.s.getmaxyx()
        self.pad_y = 0

    def title(self, text):
        self.s.attron(cp('header') | curses.A_BOLD)
        self.s.addstr(0, 0, f" ╔{'═'*(self.w-2)}╗")
        self.s.addstr(1, 0, f" ║ {text} ".ljust(self.w-1))
        self.s.addstr(2, 0, f" ╚{'═'*(self.w-2)}╝")
        self.s.attroff(cp('header') | curses.A_BOLD)

    def status(self, text):
        attr = cp('header') | curses.A_BOLD
        self.s.attron(attr)
        self.s.addstr(self.h-1, 0, f" {text} ".ljust(self.w-1))
        self.s.attroff(attr)
        self.s.refresh()

    def label(self, y, x, label, value, color='reset'):
        try:
            self.s.addstr(y, x, f" {label}: ", curses.A_BOLD)
            self.s.addstr(cp(color), value)
        except curses.error:
            pass

    def line(self, y, text="", indent=2):
        try:
            if text:
                self.s.addstr(y, indent, text)
            else:
                self.s.addstr(y, indent, "─" * (self.w - indent - 1))
        except curses.error:
            pass

    def row(self, y, items):
        try:
            col_w = (self.w - 4) // len(items)
            x = 2
            for item in items:
                self.s.addstr(y, x, str(item)[:col_w-1].ljust(col_w-1))
                x += col_w
        except curses.error:
            pass

    def key(self, y, x, key_char, description):
        try:
            self.s.addstr(y, x, f"[{key_char}]", cp('cyan') | curses.A_BOLD)
            self.s.addstr(f" {description}")
        except curses.error:
            pass

    def refresh(self):
        self.s.refresh()

def get_color(status: str) -> str:
    if status in ["active", "online", "Up"]:
        return "green"
    elif status in ["inactive", "stopped", "exited", "Down"]:
        return "red"
    elif status == "failed":
        return "red"
    elif status in ["restarting", "reloading"]:
        return "yellow"
    return "yellow"

def get_health_color(code: str) -> str:
    if code in ["200", "301"]:
        return "green"
    elif code in ["000", "error"]:
        return "red"
    return "yellow"

class Dashboard:
    def __init__(self, tui: TUI):
        self.tui = tui

    def render(self, state: ServerState):
        t = self.tui
        t.clear()
        t.title("LAIA Server Control Panel")
        y = 4

        info = get_system_info()

        t.line(y, "┌─ SYSTEM ─────────────────────────────────────────────┐")
        y += 1
        self._info_row(y, "Hostname", info.get('hostname', 'N/A'))
        self._info_row(y, "Uptime", info.get('uptime', 'N/A'))
        y += 2

        self._info_row(y, "CPU Cores", str(info.get('cpu_cores', 'N/A')))
        self._info_row(y, "Memory", f"{info.get('memory_used', 'N/A')} / {info.get('memory_total', 'N/A')} ({info.get('memory_free', 'N/A')} free)")
        y += 1
        self._info_row(y, "Disk", f"{info.get('disk_used', 'N/A')} / {info.get('disk_total', 'N/A')} ({info.get('disk_free', 'N/A')} free)")
        y += 2

        t.line(y, "├─ SERVICES (systemd) ────────────────────────────────┤")
        y += 1
        services = [get_service_status(svc) for svc in SYSTEMD_SERVICES]
        t.row(y, ["SERVICE", "STATUS", "PID", "MEMORY"])
        y += 1
        for s in services:
            color = get_color(s.status)
            t.row(y, [s.name, f"[{s.status}]", str(s.pid or '-'), s.memory or '-'])
            y += 1
        y += 1

        t.line(y, "├─ PM2 SERVICES ──────────────────────────────────────┤")
        y += 1
        pm2_list = get_pm2_status()
        if pm2_list:
            t.row(y, ["NAME", "STATUS", "PID", "MEMORY", "CPU"])
            y += 1
            for s in pm2_list:
                color = get_color(s.status)
                t.row(y, [s.name, f"[{s.status}]", str(s.pid or '-'), s.memory or '-', s.cpu or '-'])
                y += 1
        else:
            self.tui.s.addstr(y, 2, "  No PM2 services running")
            y += 1
        y += 1

        t.line(y, "├─ DOCKER CONTAINERS ──────────────────────────────────┤")
        y += 1
        containers = get_docker_containers()
        if containers:
            t.row(y, ["CONTAINER", "STATUS", "IMAGE"])
            y += 1
            for c in containers:
                color = get_color(c.status)
                t.row(y, [c.name, f"[{c.status}]", c.image])
                y += 1
        else:
            self.tui.s.addstr(y, 2, "  No Docker containers running")
            y += 1
        y += 1

        t.line(y, "├─ ENDPOINT HEALTH ────────────────────────────────────┤")
        y += 1
        health = get_endpoint_health()
        items = list(health.items())
        for i in range(0, len(items), 2):
            line = ""
            for j in range(2):
                if i + j < len(items):
                    name, code = items[i + j]
                    color = get_health_color(code)
                    line += f"  {name:25} HTTP [{code}]"
                else:
                    line += "  " + " " * 35
            try:
                self.tui.s.addstr(y, 2, line)
            except curses.error:
                pass
            y += 1
        y += 2

        try:
            self.tui.s.addstr(y, 2, f" Last updated: {state.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        except curses.error:
            pass
        y += 2

        t.line(y)
        y += 1
        t.key(y, 2, "1-6", "systemd services")
        t.key(y, 22, "2", "PM2")
        t.key(y, 32, "3", "Docker")
        t.key(y, 44, "4", "Config")
        t.key(y, 56, "5", "Logs")
        t.key(y, 68, "Q", "Quit")

        t.status("Navigate: arrows │ Select: Enter │ Refresh: R │ Quit: Q")
        t.refresh()

    def _info_row(self, y, label, value):
        try:
            self.tui.s.addstr(y, 2, f" {label}: ", curses.A_BOLD)
            self.tui.s.addstr(str(value))
        except curses.error:
            pass

class ServiceMenu:
    def __init__(self, tui: TUI):
        self.tui = tui
        self.selected = 0
        self.action_idx = 0

    def systemd_selector(self) -> Optional[str]:
        t = self.tui
        while True:
            t.clear()
            t.title("Select systemd service")

            services = [get_service_status(svc) for svc in SYSTEMD_SERVICES]
            y = 4
            for i, (svc, s) in enumerate(zip(SYSTEMD_SERVICES, services)):
                color = get_color(s.status)
                marker = "► " if i == self.selected else "  "
                try:
                    t.s.addstr(y + i, 2, f"{marker}[{i+1}] {svc:20} [{s.status}]")
                except curses.error:
                    pass

            y += len(services) + 2
            t.line(y)
            y += 1
            t.key(y, 2, "↑↓", "navigate")
            t.key(y, 16, "Enter", "select")
            t.key(y, 30, "Q", "back")

            t.status("Select service to manage")
            t.refresh()

            key = t.s.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.selected = min(len(SYSTEMD_SERVICES) - 1, self.selected + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                return SYSTEMD_SERVICES[self.selected]
            elif key in [27, ord('q'), ord('Q')]:
                return None
            elif key in [ord(str(i)) for i in range(1, 7)]:
                idx = int(chr(key)) - 1
                if idx < len(SYSTEMD_SERVICES):
                    return SYSTEMD_SERVICES[idx]

    def systemd_manager(self, service_name: str):
        t = self.tui
        actions = ["status", "restart", "stop", "start"]

        while True:
            t.clear()
            t.title(f"Service: {service_name}")

            s = get_service_status(service_name)
            y = 4
            color = get_color(s.status)
            t.label(y, 2, "Status", s.status, color)
            y += 1
            if s.uptime:
                t.label(y, 2, "Uptime", s.uptime)
                y += 1
            if s.pid:
                t.label(y, 2, "PID", str(s.pid))
                y += 1
            if s.memory:
                t.label(y, 2, "Memory", s.memory)
                y += 1
            if s.cpu:
                t.label(y, 2, "CPU", s.cpu)
                y += 1

            y += 2
            t.line(y, "├─ ACTIONS ─────────────────────────────────────────┤")
            y += 1
            for i, action in enumerate(actions):
                marker = "► " if i == self.action_idx else "  "
                try:
                    t.s.addstr(y + i, 2, f"{marker}[{i+1}] {action}")
                except curses.error:
                    pass

            y += len(actions) + 2
            t.line(y)
            y += 1
            t.key(y, 2, "↑↓", "select action")
            t.key(y, 16, "Enter", "execute")
            t.key(y, 30, "Q", "back")

            t.status(f"Managing: {service_name}")
            t.refresh()

            key = t.s.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.action_idx = max(0, self.action_idx - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.action_idx = min(len(actions) - 1, self.action_idx + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                action = actions[self.action_idx]
                self._execute_action(service_name, action)
            elif key in [27, ord('q'), ord('Q')]:
                break
            elif key in [ord(str(i)) for i in range(1, 5)]:
                idx = int(chr(key)) - 1
                if idx < len(actions):
                    self.action_idx = idx

    def _execute_action(self, service_name: str, action: str):
        t = self.tui
        t.clear()
        t.title(f"Executing: {action} {service_name}")
        t.refresh()

        if action == "status":
            success, output = systemd_action("status", service_name)
        else:
            success, output = systemd_action(action, service_name)

        y = 5
        for line in output.split("\n")[:t.h - 10]:
            try:
                t.s.addstr(y, 2, line[:t.w - 4])
            except curses.error:
                pass
            y += 1

        t.status("Press any key to continue...")
        t.refresh()
        t.s.getch()

    def pm2_manager(self):
        t = self.tui
        actions = ["status", "restart", "stop", "logs"]

        while True:
            t.clear()
            t.title("PM2: arete-backend")

            services = get_pm2_status()
            y = 4
            for s in services:
                color = get_color(s.status)
                t.label(y, 2, s.name, f"[{s.status}]", color)
                y += 1
                info = f"   PID: {s.pid or '-'}  MEM: {s.memory or '-'}  CPU: {s.cpu or '-'}"
                try:
                    t.s.addstr(y, 2, info)
                except curses.error:
                    pass
                y += 2

            t.line(y, "├─ ACTIONS ─────────────────────────────────────────┤")
            y += 1
            for i, action in enumerate(actions):
                marker = "► " if i == self.action_idx else "  "
                try:
                    t.s.addstr(y + i, 2, f"{marker}[{i+1}] {action}")
                except curses.error:
                    pass

            y += len(actions) + 2
            t.line(y)
            y += 1
            t.key(y, 2, "↑↓", "select")
            t.key(y, 16, "Enter", "execute")
            t.key(y, 30, "Q", "back")

            t.status("PM2 Management")
            t.refresh()

            key = t.s.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.action_idx = max(0, self.action_idx - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.action_idx = min(len(actions) - 1, self.action_idx + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                action = actions[self.action_idx]
                self._pm2_execute(action)
            elif key in [27, ord('q'), ord('Q')]:
                break
            elif key in [ord(str(i)) for i in range(1, 5)]:
                idx = int(chr(key)) - 1
                if idx < len(actions):
                    self.action_idx = idx

    def _pm2_execute(self, action: str):
        t = self.tui
        t.clear()
        t.title(f"PM2: {action} arete-backend")
        t.refresh()

        success, output = pm2_action(action, "arete-backend")

        y = 5
        for line in output.split("\n")[:t.h - 10]:
            try:
                t.s.addstr(y, 2, line[:t.w - 4])
            except curses.error:
                pass
            y += 1

        t.status("Press any key to continue...")
        t.refresh()
        t.s.getch()

    def docker_manager(self):
        t = self.tui
        actions = ["ps", "logs"]
        container_idx = 0
        self.action_idx = 0

        while True:
            t.clear()
            t.title("Docker Containers")

            containers = get_docker_containers()
            y = 4
            for i, c in enumerate(containers):
                color = get_color(c.status)
                marker = "► " if i == container_idx else "  "
                try:
                    t.s.addstr(y + i, 2, f"{marker}{c.name:25} [{c.status}]")
                except curses.error:
                    pass

            y += len(containers) + 2
            t.line(y, "├─ ACTIONS ─────────────────────────────────────────┤")
            y += 1
            for i, action in enumerate(actions):
                marker = "► " if i == self.action_idx else "  "
                try:
                    t.s.addstr(y + i, 2, f"{marker}[{i+1}] {action}")
                except curses.error:
                    pass

            y += len(actions) + 2
            t.line(y)
            y += 1
            t.key(y, 2, "↑↓", "select")
            t.key(y, 16, "Enter", "execute")
            t.key(y, 30, "Q", "back")

            t.status("Docker Management")
            t.refresh()

            key = t.s.getch()
            if key == curses.KEY_UP or key == ord('k'):
                if self.action_idx > 0:
                    self.action_idx -= 1
                elif container_idx > 0:
                    container_idx -= 1
            elif key == curses.KEY_DOWN or key == ord('j'):
                if self.action_idx < len(actions) - 1:
                    self.action_idx += 1
                elif container_idx < len(containers) - 1:
                    container_idx += 1
            elif key in [curses.KEY_ENTER, 10, 13]:
                action = actions[self.action_idx]
                if containers and container_idx < len(containers):
                    self._docker_execute(action, containers[container_idx].name)
            elif key in [27, ord('q'), ord('Q')]:
                break

    def _docker_execute(self, action: str, container: str):
        t = self.tui
        t.clear()
        t.title(f"Docker: {action} {container}")
        t.refresh()

        success, output = docker_action(action, container)

        y = 5
        for line in output.split("\n")[:t.h - 10]:
            try:
                t.s.addstr(y, 2, line[:t.w - 4])
            except curses.error:
                pass
            y += 1

        t.status("Press any key to continue...")
        t.refresh()
        t.s.getch()

class ConfigViewer:
    def __init__(self, tui: TUI):
        self.tui = tui
        self.selected = 0
        self.scroll = 0

    def render(self):
        t = self.tui
        files = [
            ("nginx.conf", str(NGINX_CONFIG_PATH)),
            ("docker-compose.yml", str(DOCKER_COMPOSE_PATH)),
        ]

        while True:
            t.clear()
            t.title("Configuration Files")

            y = 4
            for i, (name, _) in enumerate(files):
                marker = "► " if i == self.selected else "  "
                try:
                    t.s.addstr(y + i, 2, f"{marker}[{i+1}] {name}")
                except curses.error:
                    pass

            y += len(files) + 2
            t.line(y)
            y += 1
            t.key(y, 2, "↑↓", "select")
            t.key(y, 16, "Enter", "view")
            t.key(y, 30, "V", "validate nginx")
            t.key(y, 46, "Q", "back")

            t.status("Configuration Viewer")
            t.refresh()

            key = t.s.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.selected = min(len(files) - 1, self.selected + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                self.view_file(files[self.selected][1], files[self.selected][0])
            elif key == ord('v') or key == ord('V'):
                if self.selected == 0:
                    self.validate_nginx()
            elif key in [27, ord('q'), ord('Q')]:
                break
            elif key in [ord(str(i)) for i in range(1, 3)]:
                idx = int(chr(key)) - 1
                if idx < len(files):
                    self.selected = idx

    def view_file(self, path: str, name: str):
        t = self.tui
        try:
            content = Path(path).read_text()
        except Exception as e:
            content = f"Error: {e}"

        lines = content.split("\n")
        self.scroll = 0

        while True:
            t.clear()
            t.title(f"Viewing: {name}")

            y = 4
            end = min(self.scroll + t.h - 10, len(lines))
            for i in range(self.scroll, end):
                try:
                    t.s.addstr(y, 2, f"{i+1:4d} │ {lines[i][:t.w - 10]}")
                    y += 1
                except curses.error:
                    pass

            t.status(f"Line {self.scroll + 1}-{end} of {len(lines)} | ↑↓ scroll | Q back")
            t.refresh()

            key = t.s.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.scroll = max(0, self.scroll - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.scroll = min(len(lines) - 1, self.scroll + 1)
            elif key == curses.KEY_PPAGE:
                self.scroll = max(0, self.scroll - (t.h - 8))
            elif key == curses.KEY_NPAGE:
                self.scroll = min(len(lines) - 1, self.scroll + (t.h - 8))
            elif key in [27, ord('q'), ord('Q')]:
                break

    def validate_nginx(self):
        t = self.tui
        t.clear()
        t.title("Validating nginx configuration")
        t.refresh()

        cm = ConfigManager()
        success, msg = cm.validate_nginx_config()

        y = 6
        color = "green" if success else "red"
        t.label(y, 2, "Result", msg, color)

        t.status("Press any key to continue...")
        t.refresh()
        t.s.getch()

class LogViewer:
    def __init__(self, tui: TUI):
        self.tui = tui
        self.selected = 0
        self.scroll = 0
        self.lines = 50

    def render(self):
        t = self.tui
        services = [
            ("hermes", "Hermes"),
            ("workspace-ui", "Workspace-UI"),
            ("nginx", "Nginx"),
            ("cloudflared", "Cloudflared"),
            ("postgresql", "PostgreSQL"),
            ("arete-backend", "Arete Backend"),
            ("tienda_wordpress", "WordPress"),
            ("tienda_db", "MySQL"),
            ("tienda_phpmyadmin", "phpMyAdmin"),
        ]

        while True:
            t.clear()
            t.title("Log Viewer")

            y = 4
            t.key(y, 2, "L", f"Lines: {self.lines}")
            t.key(y, 18, "+/-", "adjust")
            y += 2

            for i, (svc_id, display) in enumerate(services):
                marker = "► " if i == self.selected else "  "
                try:
                    t.s.addstr(y + i, 2, f"{marker}[{i+1}] {display}")
                except curses.error:
                    pass

            y += len(services) + 2
            t.line(y)
            y += 1
            t.key(y, 2, "↑↓", "select")
            t.key(y, 16, "Enter", "view logs")
            t.key(y, 30, "Q", "back")

            t.status(f"Log Viewer | Lines: {self.lines}")
            t.refresh()

            key = t.s.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.selected = min(len(services) - 1, self.selected + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                svc_id = services[self.selected][0]
                self.view_logs(svc_id, services[self.selected][1])
            elif key == ord('l') or key == ord('L'):
                self.lines = max(10, min(500, self.lines + 50))
            elif key in [27, ord('q'), ord('Q')]:
                break
            elif key in [ord(str(i)) for i in range(1, 10)]:
                idx = int(chr(key)) - 1
                if idx < len(services):
                    self.selected = idx

    def view_logs(self, service_id: str, display_name: str):
        t = self.tui
        success, content = get_logs(service_id, self.lines)

        if not success:
            content = f"Error fetching logs for {display_name}"

        lines = content.split("\n")
        self.scroll = 0

        while True:
            t.clear()
            t.title(f"Logs: {display_name}")

            y = 4
            end = min(self.scroll + t.h - 10, len(lines))
            for i in range(self.scroll, end):
                try:
                    t.s.addstr(y, 2, f"{i+1:4d} │ {lines[i][:t.w - 10]}")
                    y += 1
                except curses.error:
                    pass

            t.status(f"Line {self.scroll + 1}-{end} of {len(lines)} | R refresh | Q back")
            t.refresh()

            key = t.s.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.scroll = max(0, self.scroll - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.scroll = min(len(lines) - 1, self.scroll + 1)
            elif key == curses.KEY_PPAGE:
                self.scroll = max(0, self.scroll - (t.h - 8))
            elif key == curses.KEY_NPAGE:
                self.scroll = min(len(lines) - 1, self.scroll + (t.h - 8))
            elif key == ord('r') or key == ord('R'):
                success, content = get_logs(service_id, self.lines)
                if success:
                    lines = content.split("\n")
            elif key in [27, ord('q'), ord('Q')]:
                break

class ServerControlPanel:
    def __init__(self):
        self.state = ServerState()
        self.tui = None
        self.dashboard = None
        self.service_menu = None
        self.config_viewer = None
        self.log_viewer = None

    def run(self):
        if curses:
            curses.wrapper(self._main_loop)
        else:
            print("ERROR: curses module not available")
            sys.exit(1)

    def _main_loop(self, stdscr):
        self.tui = TUI(stdscr)
        self.dashboard = Dashboard(self.tui)
        self.service_menu = ServiceMenu(self.tui)
        self.config_viewer = ConfigViewer(self.tui)
        self.log_viewer = LogViewer(self.tui)

        running = True
        while running:
            self.state.last_updated = __import__("datetime").datetime.now()
            self.dashboard.render(self.state)

            key = self.tui.s.getch()
            if key == ord('1'):
                svc = self.service_menu.systemd_selector()
                if svc:
                    self.service_menu.systemd_manager(svc)
            elif key == ord('2'):
                self.service_menu.pm2_manager()
            elif key == ord('3'):
                self.service_menu.docker_manager()
            elif key == ord('4'):
                self.config_viewer.render()
            elif key == ord('5'):
                self.log_viewer.render()
            elif key == ord('r') or key == ord('R'):
                continue
            elif key in [ord('q'), ord('Q'), 27]:
                running = False

        self.tui.clear()
        self.tui.s.addstr(self.tui.h // 2, (self.tui.w - 10) // 2, "Goodbye!", curses.A_BOLD)
        self.tui.s.refresh()
