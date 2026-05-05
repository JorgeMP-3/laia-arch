"""
Server configuration and state management
"""

import os
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

HOME = Path.home()
SERVICIOS_BASE = HOME / "servidor"
LAIA_ARCH = HOME / "laia-arch"
HERMES_RUNTIME = HOME / ".hermes"
DOCKER_COMPOSE_PATH = SERVICIOS_BASE / "tienda" / "docker-compose.yml"
NGINX_CONFIG_PATH = SERVICIOS_BASE / "nginx" / "laia.conf"
SYSTEMD_SERVICES = ["nginx", "postgresql", "cloudflared", "hermes", "workspace-ui", "pm2-familiamp"]
PM2_SERVICES = ["arete-backend"]

@dataclass
class ServiceStatus:
    name: str
    status: str
    active: bool = False
    uptime: Optional[str] = None
    memory: Optional[str] = None
    cpu: Optional[str] = None
    pid: Optional[int] = None

@dataclass
class DockerContainer:
    name: str
    image: str
    status: str
    ports: str
    created: str

@dataclass
class ServerState:
    hostname: str = ""
    os_info: str = ""
    uptime: str = ""
    cpu_cores: int = 0
    memory_total: str = ""
    memory_used: str = ""
    memory_free: str = ""
    disk_total: str = ""
    disk_used: str = ""
    disk_free: str = ""
    services: List[ServiceStatus] = field(default_factory=list)
    docker_containers: List[DockerContainer] = field(default_factory=list)
    endpoint_health: Dict[str, str] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

class ConfigManager:
    def __init__(self):
        self.nginx_template = NGINX_CONFIG_PATH
        self.docker_compose = DOCKER_COMPOSE_PATH

    def read_nginx_config(self) -> str:
        try:
            return NGINX_CONFIG_PATH.read_text()
        except Exception as e:
            return f"Error reading nginx config: {e}"

    def read_docker_compose(self) -> str:
        try:
            return DOCKER_COMPOSE_PATH.read_text()
        except Exception as e:
            return f"Error reading docker-compose: {e}"

    def apply_nginx_config(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["sudo", "cp", str(NGINX_CONFIG_PATH), "/etc/nginx/sites-available/laia"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                return False, result.stderr

            result = subprocess.run(["sudo", "nginx", "-t"], capture_output=True, text=True)
            if result.returncode != 0:
                return False, result.stderr

            result = subprocess.run(["sudo", "systemctl", "reload", "nginx"], capture_output=True, text=True)
            if result.returncode != 0:
                return False, result.stderr

            return True, "Nginx config applied successfully"
        except Exception as e:
            return False, str(e)

    def validate_nginx_config(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(["sudo", "nginx", "-t"], capture_output=True, text=True)
            if result.returncode == 0:
                return True, "Nginx config is valid"
            return False, result.stderr
        except Exception as e:
            return False, str(e)

def run_command(cmd: List[str], timeout: int = 10) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def run_command_sudo(cmd: List[str], timeout: int = 10) -> tuple[int, str, str]:
    return run_command(["sudo"] + cmd, timeout)

def get_system_info() -> Dict[str, Any]:
    info = {}

    code, out, _ = run_command(["hostname"])
    info["hostname"] = out if code == 0 else "unknown"

    code, out, _ = run_command(["cat", "/proc/uptime"])
    if code == 0:
        try:
            seconds = float(out.split()[0])
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            mins = int((seconds % 3600) // 60)
            info["uptime"] = f"{days}d {hours}h {mins}m"
        except:
            info["uptime"] = "unknown"
    else:
        info["uptime"] = "unknown"

    code, out, _ = run_command(["nproc"])
    info["cpu_cores"] = int(out) if code == 0 else 0

    code, out, _ = run_command(["free", "-b"])
    if code == 0:
        lines = out.split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 3:
                total = int(parts[1])
                used = int(parts[2])
                free = int(parts[3])
                info["memory_total"] = f"{total / (1024**3):.1f} GiB"
                info["memory_used"] = f"{used / (1024**3):.1f} GiB"
                info["memory_free"] = f"{free / (1024**3):.1f} GiB"
    else:
        info["memory_total"] = "unknown"
        info["memory_used"] = "unknown"
        info["memory_free"] = "unknown"

    code, out, _ = run_command(["df", "-B1", "/"])
    if code == 0:
        lines = out.split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 4:
                total = int(parts[1])
                used = int(parts[2])
                free = int(parts[3])
                info["disk_total"] = f"{total / (1024**3):.0f} GiB"
                info["disk_used"] = f"{used / (1024**3):.1f} GiB"
                info["disk_free"] = f"{free / (1024**3):.1f} GiB"
    else:
        info["disk_total"] = "unknown"
        info["disk_used"] = "unknown"
        info["disk_free"] = "unknown"

    return info

def get_service_status(service_name: str) -> ServiceStatus:
    status = ServiceStatus(name=service_name, status="unknown")

    if service_name == "pm2-familiamp":
        code, out, _ = run_command(["systemctl", "is-active", service_name])
        status.active = (code == 0 and out == "active")
        status.status = out if status.active else "inactive"
        if not status.active:
            code, out, _ = run_command(["systemctl", "is-failed", service_name])
            if code == 0 and out == "failed":
                status.status = "failed"
        return status

    code, out, _ = run_command(["systemctl", "is-active", service_name])
    status.active = (code == 0 and out == "active")
    status.status = out if status.active else "inactive"

    if not status.active:
        code, out, _ = run_command(["systemctl", "is-failed", service_name])
        if code == 0 and out == "failed":
            status.status = "failed"

    if status.active:
        code, out, _ = run_command(["systemctl", "show", service_name, "-p", "ActiveEnterTimestamp", "--value"])
        if code == 0 and out:
            status.uptime = out[:out.find(".")] if "." in out else out

        if service_name in ["hermes", "workspace-ui", "nginx", "postgresql", "cloudflared"]:
            code, out, _ = run_command(["ps", "-p", "$(systemctl show -p MainPID --value " + service_name + " 2>/dev/null)", "-o", "pid=,rss=,cpu=", "--no-headers"])
            if code == 0 and out:
                parts = out.split()
                if len(parts) >= 2:
                    status.pid = int(parts[0])
                    status.memory = f"{int(parts[1]) / 1024:.1f} MiB"
                    status.cpu = f"{float(parts[2]):.1f}%" if len(parts) > 2 else "0%"

    return status

def get_pm2_status() -> List[ServiceStatus]:
    services = []
    code, out, _ = run_command(["bash", "-c", "source ~/.nvm/nvm.sh && pm2 jlist 2>/dev/null || echo '[]'"])
    if code == 0 and out:
        try:
            data = json.loads(out)
            for proc in data:
                status = ServiceStatus(
                    name=proc.get("name", "unknown"),
                    status="online" if proc.get("pm2_env", {}).get("status") == "online" else "stopped",
                    active=proc.get("pm2_env", {}).get("status") == "online",
                    uptime=proc.get("pm2_env", {}).get("node_uptime", 0),
                    memory=f"{proc.get('monit', {}).get('memory', 0) / (1024*1024):.1f} MiB",
                    cpu=f"{proc.get('monit', {}).get('cpu', 0):.1f}%",
                    pid=proc.get("pid", 0)
                )
                services.append(status)
        except json.JSONDecodeError:
            pass
    return services

def get_docker_containers() -> List[DockerContainer]:
    containers = []
    code, out, _ = run_command(["bash", "-c", "sg docker -c \"docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'\""])
    if code != 0:
        code, out, _ = run_command(["bash", "-c", "docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"])
    if code == 0 and out:
        for line in out.split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 4:
                    containers.append(DockerContainer(
                        name=parts[0],
                        image=parts[1],
                        status=parts[2],
                        ports=parts[3],
                        created=""
                    ))
    return containers

def get_endpoint_health() -> Dict[str, str]:
    endpoints = {
        "arete-backend:8000": "http://localhost:8000/health",
        "workspace-ui:8077": "http://localhost:8077/",
        "wordpress:9000": "http://localhost:9000/",
        "nginx:80": "http://localhost/",
    }
    health = {}
    for name, url in endpoints.items():
        code, out, _ = run_command(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url], timeout=5)
        health[name] = out if code == 0 else "error"
    return health

def docker_action(action: str, container: Optional[str] = None) -> tuple[bool, str]:
    if container:
        cmd_str = f"sg docker -c \"docker {action} {container}\""
    else:
        cmd_str = f"sg docker -c \"docker {action}\""
    code, out, err = run_command(["bash", "-c", cmd_str])
    if code == 0:
        return True, out if out else f"{action} completed"
    return False, err if err else f"{action} failed"

def systemd_action(action: str, service: str) -> tuple[bool, str]:
    if service == "pm2-familiamp":
        if action == "restart":
            code, out, err = run_command(["sudo", "systemctl", "restart", "pm2-familiamp"])
        elif action == "stop":
            code, out, err = run_command(["sudo", "systemctl", "stop", "pm2-familiamp"])
        elif action == "start":
            code, out, err = run_command(["sudo", "systemctl", "start", "pm2-familiamp"])
        else:
            return False, f"Action {action} not supported for pm2"
        if code == 0:
            return True, f"pm2 service {action}d"
        return False, err

    valid_actions = ["start", "stop", "restart", "reload", "status"]
    if action not in valid_actions:
        return False, f"Action {action} not supported"

    cmd = ["sudo", "systemctl", action, service]
    if action == "status":
        code, out, err = run_command(cmd)
        return (True, out) if code == 0 else (False, err)

    code, _, err = run_command(cmd)
    if code == 0:
        return True, f"Service {service} {action}d"
    return False, err

def pm2_action(action: str, app_name: str = "arete-backend") -> tuple[bool, str]:
    cmd = ["bash", "-c", f"source ~/.nvm/nvm.sh && pm2 {action} {app_name}"]
    if action == "logs":
        return True, f"Run: pm2 logs {app_name}"
    code, out, err = run_command(cmd, timeout=30)
    if code == 0:
        return True, out if out else f"PM2 {action} completed"
    return False, err if err else f"PM2 {action} failed"

def get_logs(service: str, lines: int = 50) -> tuple[bool, str]:
    if service in ["hermes", "workspace-ui", "nginx", "cloudflared", "postgresql"]:
        code, out, err = run_command(["sudo", "journalctl", f"-u{service}", f"-n{lines}", "--no-pager"], timeout=10)
        return (code == 0, out if code == 0 else err)
    elif service == "arete-backend":
        return pm2_action("logs", "arete-backend")
    elif service in ["tienda_wordpress", "tienda_db", "tienda_phpmyadmin"]:
        cmd = ["bash", "-c", f"sg docker -c \"docker logs {service} -n{lines}\""] if os.path.exists("/var/run/docker.sock") else ["bash", "-c", f"docker logs {service} -n{lines}"]
        code, out, err = run_command(cmd, timeout=10)
        return (code == 0, out if code == 0 else err)
    return False, f"Unknown service: {service}"
