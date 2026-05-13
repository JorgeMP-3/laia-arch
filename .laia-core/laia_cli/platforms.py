"""
Shared platform registry for LAIA Agent.

Single source of truth for platform metadata consumed by both
skills_config (label display) and tools_config (default toolset
resolution).  Import ``PLATFORMS`` from here instead of maintaining
duplicate dicts in each module.
"""

from collections import OrderedDict
from typing import NamedTuple


class PlatformInfo(NamedTuple):
    """Metadata for a single platform entry."""
    label: str
    default_toolset: str


# Ordered so that TUI menus are deterministic.
PLATFORMS: OrderedDict[str, PlatformInfo] = OrderedDict([
    ("cli",            PlatformInfo(label="🖥️  CLI",            default_toolset="laia-cli")),
    ("telegram",       PlatformInfo(label="📱 Telegram",        default_toolset="laia-telegram")),
    ("discord",        PlatformInfo(label="💬 Discord",         default_toolset="laia-discord")),
    ("slack",          PlatformInfo(label="💼 Slack",           default_toolset="laia-slack")),
    ("whatsapp",       PlatformInfo(label="📱 WhatsApp",        default_toolset="laia-whatsapp")),
    ("signal",         PlatformInfo(label="📡 Signal",          default_toolset="laia-signal")),
    ("bluebubbles",    PlatformInfo(label="💙 BlueBubbles",     default_toolset="laia-bluebubbles")),
    ("email",          PlatformInfo(label="📧 Email",           default_toolset="laia-email")),
    ("homeassistant",  PlatformInfo(label="🏠 Home Assistant",  default_toolset="laia-homeassistant")),
    ("mattermost",     PlatformInfo(label="💬 Mattermost",      default_toolset="laia-mattermost")),
    ("matrix",         PlatformInfo(label="💬 Matrix",          default_toolset="laia-matrix")),
    ("dingtalk",       PlatformInfo(label="💬 DingTalk",        default_toolset="laia-dingtalk")),
    ("feishu",         PlatformInfo(label="🪽 Feishu",          default_toolset="laia-feishu")),
    ("wecom",          PlatformInfo(label="💬 WeCom",           default_toolset="laia-wecom")),
    ("wecom_callback", PlatformInfo(label="💬 WeCom Callback",  default_toolset="laia-wecom-callback")),
    ("weixin",         PlatformInfo(label="💬 Weixin",          default_toolset="laia-weixin")),
    ("qqbot",          PlatformInfo(label="💬 QQBot",           default_toolset="laia-qqbot")),
    ("yuanbao",        PlatformInfo(label="🤖 Yuanbao",         default_toolset="laia-yuanbao")),
    ("webhook",        PlatformInfo(label="🔗 Webhook",         default_toolset="laia-webhook")),
    ("api_server",     PlatformInfo(label="🌐 API Server",      default_toolset="laia-api-server")),
    ("cron",           PlatformInfo(label="⏰ Cron",            default_toolset="laia-cron")),
])


def platform_label(key: str, default: str = "") -> str:
    """Return the display label for a platform key, or *default*."""
    info = PLATFORMS.get(key)
    return info.label if info is not None else default
