"""
LAIA Server Control Panel
Terminal-based server monitoring and management system
"""

import sys
import os

def main():
    if not os.path.exists("/home/familiamp"):
        print("ERROR: Home directory /home/familiamp not found")
        sys.exit(1)

    try:
        import curses
    except ImportError:
        print("ERROR: Missing required dependency: curses (ncurses)")
        print("Install on Ubuntu/Debian: sudo apt install python3-curses")
        sys.exit(1)

    from ui import ServerControlPanel
    app = ServerControlPanel()
    app.run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
        sys.exit(0)
