"""Live remote control for a rooted Toon: view the screen and click to tap.

Opens a window mirroring the Toon's 800x480 screen (refreshing ~1 fps -- the
Toon's 200 MHz CPU is the limit) and turns your mouse clicks into touch events
on the device.

    pip install -e ".[screenshot]"     # Pillow + Tk (Tk ships with Python)
    python scripts/remote.py [--host 192.168.1.178]
"""

from __future__ import annotations

import argparse
import os
import queue
import threading
import time
import tkinter as tk

from PIL import Image, ImageTk

from toon.ssh import ToonSSH
from toon.touch import ToonTouch

W, H = 800, 480
N = W * H * 4


class Remote:
    def __init__(self, host: str) -> None:
        self.ssh = ToonSSH(host, compress=True).connect()
        self.touch = ToonTouch(self.ssh)
        self.frames: queue.Queue = queue.Queue(maxsize=1)
        self.running = True

        self.root = tk.Tk()
        self.root.title(f"Toon @ {host}")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(self.root, width=W, height=H, highlightthickness=0,
                                bg="black", cursor="crosshair")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.status = tk.Label(self.root, text="connecting…", anchor="w")
        self.status.pack(fill="x")
        self._imgtk = None

        threading.Thread(target=self._grab_loop, daemon=True).start()
        self.root.after(50, self._pump)

    def _grab(self) -> Image.Image:
        raw = self.ssh.read_binary(f"dd if=/dev/fb0 bs={N} count=1 2>/dev/null")
        raw = raw[:N].ljust(N, b"\0")
        return Image.frombytes("RGB", (W, H), raw, "raw", "BGRX")

    def _grab_loop(self) -> None:
        while self.running:
            try:
                img = self._grab()
                if self.frames.full():
                    self.frames.get_nowait()
                self.frames.put(img)
            except Exception as exc:  # keep the viewer alive on transient errors
                self.status.config(text=f"grab error: {exc}")
                time.sleep(1.0)

    def _pump(self) -> None:
        try:
            img = self.frames.get_nowait()
            self._imgtk = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self._imgtk)
        except queue.Empty:
            pass
        if self.running:
            self.root.after(100, self._pump)

    def on_click(self, ev: "tk.Event") -> None:
        x, y = ev.x, ev.y
        self.status.config(text=f"tap ({x}, {y})…")

        def do() -> None:
            try:
                self.touch.tap(x, y)
                self.status.config(text=f"tapped ({x}, {y})")
            except Exception as exc:
                self.status.config(text=f"tap failed: {exc}")

        threading.Thread(target=do, daemon=True).start()

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            self.running = False
            self.ssh.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default=os.environ.get("TOON_HOST", "192.168.1.178"))
    args = p.parse_args()
    Remote(args.host).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
