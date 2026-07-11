"""Tap the Toon's screen at a pixel coordinate (scripted, no GUI).

    python scripts/tap.py 620 235 [--host 192.168.1.178] [--shot after.png]

With --shot it also saves a screenshot ~1.3s after the tap so you can see the
result.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from toon.ssh import ToonSSH
from toon.touch import ToonTouch


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--host", default=os.environ.get("TOON_HOST", "192.168.1.178"))
    p.add_argument("--shot", help="save a screenshot here after tapping")
    args = p.parse_args()

    with ToonSSH(args.host, compress=True) as ssh:
        rx, ry = ToonTouch(ssh).tap(args.x, args.y)
        print(f"tapped ({args.x}, {args.y}) -> raw ({rx}, {ry})")
        if args.shot:
            from screenshot import grab  # sibling script
            time.sleep(1.3)
            grab(ssh).save(args.shot)
            print(f"saved {args.shot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
