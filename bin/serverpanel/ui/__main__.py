"""
Terminal UI for LAIA Server Control Panel
"""

import sys
import os
from pathlib import Path
from typing import Optional, Callable

try:
    import curses
    from curses import panel
except ImportError:
    curses = None
    panel = None

from config import (
    get_system_info, get_service_status, get_pm2_status,
    get_docker_containers, get_endpoint_health,
    systemd_action, pm2_action, docker_action, get_logs,
    ConfigManager, ServerState, ServiceStatus, DockerContainer,
    SYSTEMD_SERVICES, NGINX_CONFIG_PATH, DOCKER_COMPOSE_PATH
)

class Color:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    @staticmethod
    def status_color(status: str) -> str:
        if status == "active" or status == "online":
            return Color.GREEN
        elif status in ["inactive", "stopped", "exited"]:
            return Color.RED
        elif status == "failed":
            return Color.RED + Color.BOLD
        elif "up" in status.lower() or "healthy" in status.lower():
            return Color.GREEN
        return Color.YELLOW

    @staticmethod
    def health_color(code: str) -> str:
        if code in ["200", "301"]:
            return Color.GREEN
        elif code == "000":
            return Color.RED
        return Color.YELLOW

class TerminalUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()
        curses.curs_set(0)
        self.current_row = 0
        self.scroll_pos = 0
        self.config_manager = ConfigManager()

    def clear(self):
        self.stdscr.clear()
        self.height, self.width = self.stdscr.getmaxyx()

    def print_header(self, title: str):
        self.stdscr.attron(curses.color_pair(1))
        self.stdscr.attron(curses.A_BOLD)
        header = f" {title} "
        self.stdscr.addstr(0, 0, header.center(self.width - 1))
        self.stdscr.attroff(curses.A_BOLD)
        self.stdscr.attroff(curses.color_pair(1))
        self.stdscr.addstr(1, 0, "─" * (self.width - 1))
        curses.doupdate()

    def print_line(self, y: int, text: str, attr: int = 0):
        if y < 2 or y >= self.height - 1:
            return
        text = text[:self.width - 2]
        try:
            self.stdscr.addstr(y, 0, text.ljust(self.width - 1), attr)
        except curses.error:
            pass

    def print_status_bar(self, msg: str):
        if self.height > 0:
            try:
                self.stdscr.addstr(self.height - 1, 0, msg[:self.width - 1].ljust(self.width - 1), curses.A_REVERSE)
            except curses.error:
                pass

    def print_table(self, headers: list, rows: list, start_y: int, max_height: int = None) -> int:
        if max_height is None:
            max_height = self.height
        col_widths = [max(10, self.width // len(headers) - 1) for _ in headers]
        header_str = "│".join(h[:cw].center(cw) for h, cw in zip(headers, col_widths))
        self.print_line(start_y, "├" + "┼".join("─" * w for w in col_widths) + "┤")
        self.print_line(start_y, "│" + header_str + "│")
        self.print_line(start_y, "├" + "┼".join("─" * w for w in col_widths) + "┤")
        row_strs = []
        for i, row in enumerate(rows[:max_height - start_y - 3]):
            row_str = "│".join(str(cell)[:cw].ljust(cw) for cell, cw in zip(row, col_widths))
            row_strs.append(row_str)
        for j, row_str in enumerate(row_strs):
            self.print_line(start_y + j + 1, "│" + row_str + "│")
        self.print_line(start_y + len(row_strs) + 1, "└" + "┘".join("─" * w for w in col_widths) + "┘")
        return start_y + len(row_strs) + 2

class DashboardView:
    def __init__(self, ui: TerminalUI):
        self.ui = ui

    def render(self, state: ServerState):
        ui = self.ui
        ui.clear()
        ui.print_header("LAIA Server Dashboard")

        y = 3
        info = get_system_info()

        ui.print_line(y, f"  {Color.BOLD}Hostname:{Color.ENDC} {info.get('hostname', 'N/A')}  |  {Color.BOLD}Uptime:{Color.ENDC} {info.get('uptime', 'N/A')}  |  {Color.BOLD}CPU Cores:{Color.ENDC} {info.get('cpu_cores', 'N/A')}")
        y += 1
        ui.print_line(y, f"  {Color.BOLD}Memory:{Color.ENDC} {info.get('memory_used', 'N/A')} / {info.get('memory_total', 'N/A')} (free: {info.get('memory_free', 'N/A')})")
        y += 1
        ui.print_line(y, f"  {Color.BOLD}Disk:{Color.ENDC} {info.get('disk_used', 'N/A')} / {info.get('disk_total', 'N/A')} (free: {info.get('disk_free', 'N/A')})")
        y += 2

        ui.print_line(y, f"  {Color.BOLD}┌{'─'*40} Services (systemd) {'─'*17}┐{Color.ENDC}")
        y += 1
        systemd_services = []
        for svc in SYSTEMD_SERVICES:
            s = get_service_status(svc)
            systemd_services.append(s)
        col1 = systemd_services[:3]
        col2 = systemd_services[3:]
        for i in range(max(len(col1), len(col2))):
            c1 = col1[i] if i < len(col1) else None
            c2 = col2[i] if i < len(col2) else None
            line = ""
            if c1:
                color = Color.status_color(c1.status)
                line += f"  {c1.name:18} {color}{c1.status:10}{Color.ENDC}"
            else:
                line += "  " + " " * 30
            if c2:
                color = Color.status_color(c2.status)
                line += f"  {c2.name:18} {color}{c2.status:10}{Color.ENDC}"
            ui.print_line(y, line)
            y += 1

        y += 1
        ui.print_line(y, f"  {Color.BOLD}┌{'─'*40} PM2 Services {'─'*24}┐{Color.ENDC}")
        y += 1
        pm2_services = get_pm2_status()
        for s in pm2_services:
            color = Color.status_color(s.status)
            mem = s.memory or "N/A"
            cpu = s.cpu or "N/A"
            ui.print_line(y, f"  {s.name:18} {color}{s.status:10}{Color.ENDC} │ PID: {s.pid or 'N/A':>6} │ MEM: {mem:>10} │ CPU: {cpu:>6}")
            y += 1

        y += 1
        ui.print_line(y, f"  {Color.BOLD}┌{'─'*40} Docker Containers {'─'*22}┐{Color.ENDC}")
        y += 1
        containers = get_docker_containers()
        for c in containers:
            color = Color.GREEN if "Up" in c.status else Color.YELLOW
            ui.print_line(y, f"  {c.name:20} {color}{c.status:20}{Color.ENDC} │ {c.image[:30]}")
            y += 1

        y += 1
        ui.print_line(y, f"  {Color.BOLD}┌{'─'*40} Endpoint Health {'─'*22}┐{Color.ENDC}")
        y += 1
        health = get_endpoint_health()
        items = list(health.items())
        for i in range(0, len(items), 2):
            line = ""
            for j in range(2):
                if i + j < len(items):
                    name, code = items[i + j]
                    color = Color.health_color(code)
                    line += f"  {name:22} HTTP {color}{code:6}{Color.ENDC}"
                else:
                    line += "  " + " " * 35
            ui.print_line(y, line)
            y += 1

        y += 1
        ui.print_line(y, f"  Last updated: {state.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        y += 2
        ui.print_line(y, f"  {Color.DIM}[↑↓] Navigate  [ENTER] Manage  [R] Refresh  [Q] Quit{Color.ENDC}")

        ui.print_status_bar("  Press number to select service  │  [1-6] systemd  │  [P] PM2  │  [D] Docker")
        curses.doupdate()
        return y

class ServiceManageView:
    def __init__(self, ui: TerminalUI):
        self.ui = ui
        self.selected_action = 0

    def render_systemd_service(self, service_name: str) -> bool:
        ui = self.ui
        actions = ["status", "restart", "stop", "start", "logs"]
        while True:
            ui.clear()
            ui.print_header(f"Service: {service_name} (systemd)")

            s = get_service_status(service_name)
            y = 3
            color = Color.status_color(s.status)
            ui.print_line(y, f"  {Color.BOLD}Status:{Color.ENDC} {color}{s.status}{Color.ENDC}")
            y += 1
            if s.uptime:
                ui.print_line(y, f"  {Color.BOLD}Uptime:{Color.ENDC} {s.uptime}")
                y += 1
            if s.memory:
                ui.print_line(y, f"  {Color.BOLD}Memory:{Color.ENDC} {s.memory}  {Color.BOLD}CPU:{Color.ENDC} {s.cpu or 'N/A'}")
                y += 1
            if s.pid:
                ui.print_line(y, f"  {Color.BOLD}PID:{Color.ENDC} {s.pid}")
                y += 1

            y += 2
            ui.print_line(y, f"  {Color.BOLD}Actions:{Color.ENDC}")
            y += 1
            for i, action in enumerate(actions):
                marker = "▶ " if i == self.selected_action else "  "
                ui.print_line(y + i, f"  {marker}[{i+1}] {action}")

            y += len(actions) + 2
            ui.print_line(y, f"  {Color.DIM}[↑↓] Select action  [ENTER] Execute  [ESC/Q] Back{Color.ENDC}")

            ui.print_status_bar(f"  Service: {service_name}")
            curses.doupdate()

            key = ui.stdscr.getch()
            if key in [curses.KEY_UP, ord('k')]:
                self.selected_action = max(0, self.selected_action - 1)
            elif key in [curses.KEY_DOWN, ord('j')]:
                self.selected_action = min(len(actions) - 1, self.selected_action + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                action = actions[self.selected_action]
                ui.clear()
                ui.print_header(f"Executing: {action} {service_name}")
                curses.doupdate()

                if action == "status":
                    success, output = systemd_action("status", service_name)
                else:
                    success, output = systemd_action(action, service_name)

                y = 5
                for line in output.split("\n")[:ui.height - 8]:
                    ui.print_line(y, f"  {line}")
                    y += 1

                ui.print_status_bar("  Press any key to continue...")
                curses.doupdate()
                ui.stdscr.getch()
                if not success:
                    return False
            elif key in [27, ord('q'), ord('Q')]:
                return True
            elif key in [ord('1'), ord('2'), ord('3'), ord('4'), ord('5')]:
                idx = ord(str(key)) - ord('1')
                if idx < len(actions):
                    self.selected_action = idx

    def render_pm2_service(self) -> bool:
        ui = self.ui
        actions = ["status", "restart", "stop", "start", "logs"]
        service_name = "arete-backend"
        while True:
            ui.clear()
            ui.print_header(f"PM2 Service: {service_name}")

            services = get_pm2_status()
            y = 3
            for s in services:
                color = Color.status_color(s.status)
                ui.print_line(y, f"  {Color.BOLD}{s.name}{Color.ENDC}")
                y += 1
                ui.print_line(y, f"    Status: {color}{s.status}{Color.ENDC}  PID: {s.pid or 'N/A'}  MEM: {s.memory or 'N/A'}  CPU: {s.cpu or 'N/A'}")
                y += 1

            y += 2
            ui.print_line(y, f"  {Color.BOLD}Actions:{Color.ENDC}")
            y += 1
            for i, action in enumerate(actions):
                marker = "▶ " if i == self.selected_action else "  "
                ui.print_line(y + i, f"  {marker}[{i+1}] {action}")

            y += len(actions) + 2
            ui.print_line(y, f"  {Color.DIM}[↑↓] Select action  [ENTER] Execute  [ESC/Q] Back{Color.ENDC}")

            ui.print_status_bar(f"  PM2: {service_name}")
            curses.doupdate()

            key = ui.stdscr.getch()
            if key in [curses.KEY_UP, ord('k')]:
                self.selected_action = max(0, self.selected_action - 1)
            elif key in [curses.KEY_DOWN, ord('j')]:
                self.selected_action = min(len(actions) - 1, self.selected_action + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                action = actions[self.selected_action]
                ui.clear()
                ui.print_header(f"Executing: {action} {service_name}")
                curses.doupdate()

                success, output = pm2_action(action, service_name)

                y = 5
                for line in output.split("\n")[:ui.height - 8]:
                    ui.print_line(y, f"  {line}")
                    y += 1

                ui.print_status_bar("  Press any key to continue...")
                curses.doupdate()
                ui.stdscr.getch()
                if not success:
                    return False
            elif key in [27, ord('q'), ord('Q')]:
                return True
            elif key in [ord('1'), ord('2'), ord('3'), ord('4'), ord('5')]:
                idx = ord(str(key)) - ord('1')
                if idx < len(actions):
                    self.selected_action = idx

    def render_docker_service(self) -> bool:
        ui = self.ui
        actions = ["ps", "logs", "restart", "stop", "start"]
        while True:
            ui.clear()
            ui.print_header("Docker Containers")

            y = 3
            containers = get_docker_containers()
            for i, c in enumerate(containers):
                color = Color.GREEN if "Up" in c.status else Color.YELLOW
                marker = "▶ " if i == ui.current_row else "  "
                ui.print_line(y + i, f"  {marker}{c.name:25} {color}{c.status:20}{Color.ENDC}")

            y += len(containers) + 2
            ui.print_line(y, f"  {Color.BOLD}Actions:{Color.ENDC}")
            y += 1
            for i, action in enumerate(actions):
                marker = "▶ " if i == self.selected_action else "  "
                ui.print_line(y + i, f"  {marker}[{i+1}] {action}")

            y += len(actions) + 2
            ui.print_line(y, f"  {Color.DIM}[↑↓] Select container/action  [ENTER] Execute  [ESC/Q] Back{Color.ENDC}")

            ui.print_status_bar("  Docker management")
            curses.doupdate()

            key = ui.stdscr.getch()
            if key in [curses.KEY_UP, ord('k')]:
                self.selected_action = max(0, self.selected_action - 1)
            elif key in [curses.KEY_DOWN, ord('j')]:
                self.selected_action = min(len(actions) - 1, self.selected_action + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                action = actions[self.selected_action]
                container_name = containers[ui.current_row].name if ui.current_row < len(containers) else None

                if container_name and action in ["logs", "restart", "stop", "start"]:
                    ui.clear()
                    ui.print_header(f"Executing: {action} {container_name}")
                    curses.doupdate()
                    success, output = docker_action(action, container_name)
                    y = 5
                    for line in output.split("\n")[:ui.height - 8]:
                        ui.print_line(y, f"  {line}")
                        y += 1
                    ui.print_status_bar("  Press any key to continue...")
                    curses.doupdate()
                    ui.stdscr.getch()
                else:
                    if action == "ps":
                        ui.clear()
                        ui.print_header("Docker: ps")
                        y = 5
                        success, output = docker_action("ps")
                        for line in output.split("\n")[:ui.height - 8]:
                            ui.print_line(y, f"  {line}")
                            y += 1
                        ui.print_status_bar("  Press any key to continue...")
                        curses.doupdate()
                        ui.stdscr.getch()
            elif key in [27, ord('q'), ord('Q')]:
                return True

class ConfigView:
    def __init__(self, ui: TerminalUI):
        self.ui = ui
        self.selected_file = 0
        self.scroll_pos = 0
        self.edit_mode = False
        self.edit_content = ""

    def render(self) -> bool:
        ui = self.ui
        files = [
            ("nginx.conf", str(NGINX_CONFIG_PATH)),
            ("docker-compose.yml", str(DOCKER_COMPOSE_PATH)),
        ]

        while True:
            ui.clear()
            ui.print_header("Configuration Viewer")

            y = 3
            ui.print_line(y, "  Select a configuration file to view:")
            y += 2

            for i, (name, path) in enumerate(files):
                marker = "▶ " if i == self.selected_file else "  "
                ui.print_line(y + i, f"  {marker}[{i+1}] {name}")
                y += 1

            y += 2
            ui.print_line(y, f"  {Color.DIM}[↑↓] Select  [ENTER] View  [E] Edit  [V] Validate (nginx)  [ESC/Q] Back{Color.ENDC}")

            ui.print_status_bar("  Configuration files")
            curses.doupdate()

            key = ui.stdscr.getch()
            if key in [curses.KEY_UP, ord('k')]:
                self.selected_file = max(0, self.selected_file - 1)
            elif key in [curses.KEY_DOWN, ord('j')]:
                self.selected_file = min(len(files) - 1, self.selected_file + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                self.view_file(files[self.selected_file][1], files[self.selected_file][0])
            elif key == ord('v') or key == ord('V'):
                if self.selected_file == 0:
                    self.validate_nginx()
            elif key in [27, ord('q'), ord('Q')]:
                return True
            elif key in [ord('1'), ord('2')]:
                idx = ord(str(key)) - ord('1')
                if idx < len(files):
                    self.selected_file = idx

    def view_file(self, path: str, name: str):
        ui = self.ui
        try:
            content = Path(path).read_text()
        except Exception as e:
            content = f"Error reading file: {e}"

        lines = content.split("\n")
        self.scroll_pos = 0

        while True:
            ui.clear()
            ui.print_header(f"Viewing: {name}")

            y = 3
            end = min(self.scroll_pos + ui.height - 8, len(lines))
            for i in range(self.scroll_pos, end):
                line_num = f"{i+1:4d} │ "
                try:
                    ui.print_line(y, f"{Color.DIM}{line_num}{Color.ENDC}{lines[i]}")
                except curses.error:
                    pass
                y += 1

            ui.print_status_bar(f"  Line {self.scroll_pos + 1}-{end} of {len(lines)}  │  [↑↓] Scroll  [ESC/Q] Back")
            curses.doupdate()

            key = ui.stdscr.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.scroll_pos = max(0, self.scroll_pos - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.scroll_pos = min(len(lines) - 1, self.scroll_pos + 1)
            elif key == curses.KEY_PPAGE:
                self.scroll_pos = max(0, self.scroll_pos - (ui.height - 8))
            elif key == curses.KEY_NPAGE:
                self.scroll_pos = min(len(lines) - 1, self.scroll_pos + (ui.height - 8))
            elif key in [27, ord('q'), ord('Q')]:
                break

    def validate_nginx(self):
        ui = self.ui
        ui.clear()
        ui.print_header("Validating nginx configuration")
        curses.doupdate()

        success, msg = ui.config_manager.validate_nginx_config()

        y = 5
        color = Color.GREEN if success else Color.RED
        ui.print_line(y, f"  {color}{msg}{Color.ENDC}")

        ui.print_status_bar("  Press any key to continue...")
        curses.doupdate()
        ui.stdscr.getch()

class LogsView:
    def __init__(self, ui: TerminalUI):
        self.ui = ui
        self.selected_service = 0
        self.scroll_pos = 0
        self.line_count = 50

    def render(self) -> bool:
        ui = self.ui
        all_services = [
            ("hermes", "hermes"),
            ("workspace-ui", "workspace-ui"),
            ("nginx", "nginx"),
            ("cloudflared", "cloudflared"),
            ("postgresql", "postgresql"),
            ("arete-backend", "arete-backend"),
            ("tienda_wordpress", "wordpress"),
            ("tienda_db", "mysql"),
            ("tienda_phpmyadmin", "phpmyadmin"),
        ]

        while True:
            ui.clear()
            ui.print_header("Log Viewer")

            y = 3
            ui.print_line(y, f"  {Color.BOLD}Select service (last {self.line_count} lines):{Color.ENDC}")
            y += 2

            for i, (svc_id, display_name) in enumerate(all_services):
                marker = "▶ " if i == self.selected_service else "  "
                ui.print_line(y + i, f"  {marker}[{i+1}] {display_name}")

            y += len(all_services) + 2
            ui.print_line(y, f"  Lines: [{self.line_count}]  [L] +/-50  [R] Refresh")
            y += 2
            ui.print_line(y, f"  {Color.DIM}[↑↓] Select  [ENTER] View logs  [ESC/Q] Back{Color.ENDC}")

            ui.print_status_bar("  Log viewer")
            curses.doupdate()

            key = ui.stdscr.getch()
            if key in [curses.KEY_UP, ord('k')]:
                self.selected_service = max(0, self.selected_service - 1)
            elif key in [curses.KEY_DOWN, ord('j')]:
                self.selected_service = min(len(all_services) - 1, self.selected_service + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                svc_id = all_services[self.selected_service][0]
                self.view_logs(svc_id, all_services[self.selected_service][1])
            elif key == ord('l') or key == ord('L'):
                self.line_count = max(10, min(500, self.line_count + 50 if key == ord('l') else self.line_count - 50))
            elif key in [27, ord('q'), ord('Q')]:
                return True
            elif key in [ord(str(i)) for i in range(1, 10)]:
                idx = int(chr(key)) - 1
                if idx < len(all_services):
                    self.selected_service = idx

    def view_logs(self, service_id: str, display_name: str):
        ui = self.ui
        success, content = get_logs(service_id, self.line_count)

        if not success:
            content = f"Error fetching logs for {display_name}"

        lines = content.split("\n")
        self.scroll_pos = 0

        while True:
            ui.clear()
            ui.print_header(f"Logs: {display_name}")

            y = 3
            end = min(self.scroll_pos + ui.height - 8, len(lines))
            for i in range(self.scroll_pos, end):
                try:
                    line = lines[i][:ui.width - 8]
                    ui.print_line(y, f"{Color.DIM}{i+1:4d} │ {Color.ENDC}{line}")
                except curses.error:
                    pass
                y += 1

            ui.print_status_bar(f"  Line {self.scroll_pos + 1}-{end} of {len(lines)}  │  [↑↓] Scroll  [R] Refresh  [ESC/Q] Back")
            curses.doupdate()

            key = ui.stdscr.getch()
            if key == curses.KEY_UP or key == ord('k'):
                self.scroll_pos = max(0, self.scroll_pos - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                self.scroll_pos = min(len(lines) - 1, self.scroll_pos + 1)
            elif key == curses.KEY_PPAGE:
                self.scroll_pos = max(0, self.scroll_pos - (ui.height - 8))
            elif key == curses.KEY_NPAGE:
                self.scroll_pos = min(len(lines) - 1, self.scroll_pos + (ui.height - 8))
            elif key == ord('r') or key == ord('R'):
                success, content = get_logs(service_id, self.line_count)
                if success:
                    lines = content.split("\n")
            elif key in [27, ord('q'), ord('Q')]:
                break

class ServerControlPanel:
    def __init__(self):
        self.state = ServerState()
        self.current_view = 0
        self.views = ["dashboard", "services", "docker", "config", "logs"]
        self.dashboard = None
        self.service_view = None
        self.config_view = None
        self.logs_view = None

    def run(self):
        if curses and panel:
            curses.wrapper(self._main_loop)
        else:
            print("ERROR: curses module not available. This tool requires a terminal.")
            sys.exit(1)

    def _main_loop(self, stdscr):
        ui = TerminalUI(stdscr)
        self.dashboard = DashboardView(ui)
        self.service_view = ServiceManageView(ui)
        self.config_view = ConfigView(ui)
        self.logs_view = LogsView(ui)

        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)

        running = True
        while running:
            if self.current_view == 0:
                self.state.last_updated = __import__("datetime").datetime.now()
                self.dashboard.render(self.state)
            elif self.current_view == 1:
                self.service_view.render_systemd_service(SYSTEMD_SERVICES[0])
                self.current_view = 0
                continue
            elif self.current_view == 2:
                self.service_view.render_pm2_service()
                self.current_view = 0
                continue
            elif self.current_view == 3:
                self.service_view.render_docker_service()
                self.current_view = 0
                continue
            elif self.current_view == 4:
                self.config_view.render()
                self.current_view = 0
                continue
            elif self.current_view == 5:
                self.logs_view.render()
                self.current_view = 0
                continue

            ui.print_status_bar("  Press number to select  │  [1] systemd  │  [2] PM2  │  [3] Docker  │  [4] Config  │  [5] Logs  │  [Q] Quit")
            curses.doupdate()

            key = stdscr.getch()
            if key == ord('1'):
                self._show_service_menu(ui)
            elif key == ord('2'):
                self.service_view.render_pm2_service()
            elif key == ord('3'):
                self.service_view.render_docker_service()
            elif key == ord('4'):
                self.config_view.render()
            elif key == ord('5'):
                self.logs_view.render()
            elif key == ord('r') or key == ord('R'):
                self.state.last_updated = __import__("datetime").datetime.now()
            elif key in [ord('q'), ord('Q'), 27]:
                running = False

        ui.clear()
        stdscr.addstr(ui.height // 2, (ui.width - 20) // 2, "Goodbye!", curses.A_BOLD)
        stdscr.refresh()

    def _show_service_menu(self, ui: TerminalUI):
        selected = 0
        while True:
            ui.clear()
            ui.print_header("Select systemd service")

            y = 3
            for i, svc in enumerate(SYSTEMD_SERVICES):
                s = get_service_status(svc)
                color = Color.status_color(s.status)
                marker = "▶ " if i == selected else "  "
                ui.print_line(y + i, f"  {marker}[{i+1}] {svc:20} {color}{s.status}{Color.ENDC}")

            y += len(SYSTEMD_SERVICES) + 2
            ui.print_line(y, f"  {Color.DIM}[↑↓] Select  [ENTER] Manage  [ESC/Q] Back{Color.ENDC}")

            ui.print_status_bar("  Service selection")
            curses.doupdate()

            key = ui.stdscr.getch()
            if key == curses.KEY_UP or key == ord('k'):
                selected = max(0, selected - 1)
            elif key == curses.KEY_DOWN or key == ord('j'):
                selected = min(len(SYSTEMD_SERVICES) - 1, selected + 1)
            elif key in [curses.KEY_ENTER, 10, 13]:
                self.service_view.render_systemd_service(SYSTEMD_SERVICES[selected])
                break
            elif key in [27, ord('q'), ord('Q')]:
                break
            elif key in [ord(str(i)) for i in range(1, 7)]:
                idx = int(chr(key)) - 1
                if idx < len(SYSTEMD_SERVICES):
                    self.service_view.render_systemd_service(SYSTEMD_SERVICES[idx])
                    break
