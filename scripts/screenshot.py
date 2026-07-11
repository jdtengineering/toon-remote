"""Grab the Toon's screen over SSH and save it as a PNG.

The Toon renders to a raw 800x480 32bpp framebuffer (fb0 = background UI,
fb1 = foreground overlay). It has no base64/gzip, so we stream the raw bytes
straight through the SSH channel and decode them with Pillow here.

    python scripts/screenshot.py [--host 192.168.1.50] [-o toon.png] [--fb fb0]

Requires Pillow (pip install pillow).
"""

from __future__ import annotations

import argparse
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from toon_remote import config
from toon_remote.ssh import ToonSSH

WIDTH, HEIGHT = 800, 480
FRAME_BYTES = WIDTH * HEIGHT * 4


def grab(ssh: ToonSSH, fb: str = "fb0") -> Image.Image:
    raw = ssh.read_binary(f"dd if=/dev/{fb} bs={FRAME_BYTES} count=1 2>/dev/null")
    raw = raw[:FRAME_BYTES].ljust(FRAME_BYTES, b"\0")
    # i.MX stores each pixel as little-endian 0xAARRGGBB -> bytes B,G,R,A.
    # Decode as opaque RGB (BGRX) since the framebuffer alpha is unused.
    return Image.frombytes("RGB", (WIDTH, HEIGHT), raw, "raw", "BGRX")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default=config.get_host())
    p.add_argument("-o", "--out", default="toon.png", help="output PNG path")
    p.add_argument("--fb", default="fb0", choices=["fb0", "fb1"],
                   help="framebuffer layer (fb0 = UI, fb1 = overlay)")
    args = p.parse_args(argv)

    with ToonSSH(args.host) as ssh:
        img = grab(ssh, args.fb)
    img.save(args.out)
    print(f"Saved {args.fb} -> {args.out} ({img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
