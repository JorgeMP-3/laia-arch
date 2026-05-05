#!/usr/bin/env python3
"""
LAIA Server Control Panel - Main Entry Point
"""

import sys
import os
from pathlib import Path

LAIA_PANEL_DIR = Path(__file__).parent.resolve()

def check_dependencies():
    missing = []
    try:
        import curses
    except ImportError:
        missing.append("curses (ncurses)")
    return missing

def main():
    missing = check_dependencies()
    if missing:
        print("ERROR: Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall on Ubuntu/Debian: sudo apt install python3-curses")
        print("Install on Fedora/RHEL:   sudo dnf install python3-curses")
        sys.exit(1)

    if not os.path.exists("/home/familiamp"):
        print("ERROR: Home directory /home/familiamp not found")
        sys.exit(1)

    try:
        from ui.app import ServerControlPanel
        app = ServerControlPanel()
        app.run()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
