"""Allow ``python -m ctl`` to launch the app."""

from .app import main

raise SystemExit(main())
