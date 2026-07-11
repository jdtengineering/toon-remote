"""Launcher for the Toon Remote GUI (see toon/app.py).

    pip install -e ".[gui]"      # Pillow (+ Tk, which ships with Python)
    python scripts/remote.py     # click the screen to tap; set IP in Config…
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from toon_remote.app import main

if __name__ == "__main__":
    raise SystemExit(main())
