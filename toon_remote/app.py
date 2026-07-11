"""Toon Remote — a GUI to view the Toon's screen and control it by clicking.

Mirrors the Toon's 800x480 screen (~1 fps; the 200 MHz CPU is the limit) and
turns mouse clicks into touch events. Connection settings (IP + SSH password)
are entered in the Config dialog and saved on disk via :mod:`toon.config`.
"""

from __future__ import annotations

import argparse
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from . import config
from .ssh import ToonSSH
from .touch import ToonTouch

W, H = 800, 480
N = W * H * 4


class ConfigDialog(tk.Toplevel):
    """Modal dialog to set the Toon host + SSH password. Result in ``self.result``."""

    def __init__(self, parent, host: str = "", password: str = "") -> None:
        super().__init__(parent)
        self.title("Toon connection")
        self.resizable(False, False)
        self.result = None

        frm = ttk.Frame(self, padding=16)
        frm.grid()
        ttk.Label(frm, text="Toon IP address").grid(row=0, column=0, sticky="w")
        self.host_var = tk.StringVar(value=host)
        ttk.Entry(frm, textvariable=self.host_var, width=26).grid(
            row=1, column=0, columnspan=2, pady=(0, 8))
        ttk.Label(frm, text="SSH password").grid(row=2, column=0, sticky="w")
        self.pw_var = tk.StringVar(value=password)
        ttk.Entry(frm, textvariable=self.pw_var, width=26, show="*").grid(
            row=3, column=0, columnspan=2, pady=(0, 12))
        ttk.Button(frm, text="Save", command=self._save).grid(row=4, column=1, sticky="e")
        ttk.Button(frm, text="Cancel", command=self.destroy).grid(row=4, column=0, sticky="e")

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.transient(parent)
        self.grab_set()

    def _save(self) -> None:
        host = self.host_var.get().strip()
        if not host:
            messagebox.showerror("Toon", "Please enter the Toon's IP address.")
            return
        config.save(host, self.pw_var.get().strip() or config.DEFAULT_PASSWORD)
        self.result = (host, self.pw_var.get().strip() or config.DEFAULT_PASSWORD)
        self.destroy()


class Remote:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.ssh: ToonSSH | None = None
        self.touch: ToonTouch | None = None
        self.frames: queue.Queue = queue.Queue(maxsize=1)
        self.running = True

        root.title("Toon Remote")
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0,
                                bg="black", cursor="crosshair")
        self.canvas.pack()
        bar = ttk.Frame(root)
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text="not connected", anchor="w")
        self.status.pack(side="left", fill="x", expand=True, padx=6, pady=3)
        ttk.Button(bar, text="Config…", command=self.open_config).pack(side="right")
        self.canvas.bind("<Button-1>", self.on_click)
        self._imgtk = None

        threading.Thread(target=self._grab_loop, daemon=True).start()
        self.root.after(50, self._pump)

    # -- connection ----------------------------------------------------------

    def connect(self, host: str, password: str) -> bool:
        self._teardown_ssh()
        self._set_status(f"connecting to {host}…")
        try:
            ssh = ToonSSH(host, password=password, compress=True).connect()
        except Exception as exc:
            self._set_status(f"connect failed: {exc}")
            return False
        self.ssh = ssh
        self.touch = ToonTouch(ssh)
        self.root.title(f"Toon Remote — {host}")
        self._set_status(f"connected to {host}")
        return True

    def _teardown_ssh(self) -> None:
        if self.ssh is not None:
            try:
                self.ssh.close()
            except Exception:
                pass
        self.ssh = self.touch = None

    def open_config(self) -> None:
        dlg = ConfigDialog(self.root, host=config.get_host() or "",
                           password=config.get_password())
        self.root.wait_window(dlg)
        if dlg.result:
            host, pw = dlg.result
            self.connect(host, pw)

    # -- screen streaming ----------------------------------------------------

    def _grab(self) -> Image.Image:
        raw = self.ssh.read_binary(f"dd if=/dev/fb0 bs={N} count=1 2>/dev/null")
        raw = raw[:N].ljust(N, b"\0")
        return Image.frombytes("RGB", (W, H), raw, "raw", "BGRX")

    def _grab_loop(self) -> None:
        while self.running:
            if self.ssh is None:
                time.sleep(0.2)
                continue
            try:
                img = self._grab()
                if self.frames.full():
                    self.frames.get_nowait()
                self.frames.put(img)
            except Exception as exc:
                self._set_status(f"grab error: {exc}")
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

    # -- input ---------------------------------------------------------------

    def on_click(self, ev: "tk.Event") -> None:
        if self.touch is None:
            self._set_status("not connected — open Config…")
            return
        x, y = ev.x, ev.y
        self._set_status(f"tap ({x}, {y})…")

        def do() -> None:
            try:
                self.touch.tap(x, y)
                self._set_status(f"tapped ({x}, {y})")
            except Exception as exc:
                self._set_status(f"tap failed: {exc}")

        threading.Thread(target=do, daemon=True).start()

    def _set_status(self, text: str) -> None:
        try:
            self.status.config(text=text)
        except Exception:
            pass

    def shutdown(self) -> None:
        self.running = False
        self._teardown_ssh()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Toon Remote — screen viewer + touch control")
    p.add_argument("--host", default=None,
                   help="Toon IP (default: saved config / TOON_HOST)")
    p.add_argument("--selftest", action="store_true",
                   help="verify imports/bundle and exit (no GUI)")
    args = p.parse_args(argv)

    if args.selftest:
        # Reaching here means Pillow, paramiko and Tk all imported cleanly.
        print("toon-remote selftest OK")
        return 0

    root = tk.Tk()
    app = Remote(root)
    host = config.get_host(args.host)
    if host:
        app.connect(host, config.get_password())
    else:
        app.open_config()  # first-run: ask for IP + password
    try:
        root.mainloop()
    finally:
        app.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
