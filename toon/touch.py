"""Inject touch events into a rooted Toon's screen over SSH.

The Toon's UI is Qt (`qt-gui -platform linuxfb -plugin Tslib`) reading the
TSC2007 touchscreen at /dev/input/touchscreen0 through tslib. tslib applies the
calibration in /etc/pointercal, so we invert it to turn a screen pixel into the
raw ADC coordinates the device reports, then stream a realistic tap.

Getting a tap to register took matching the *real* device's event shape:
  - BTN_TOUCH=1 is sent FIRST in the pen-down frame (not last),
  - pressure is realistic (~380, not maxed out),
  - samples arrive ~every 10ms and the touch is held a few hundred ms
    (tslib's variance/dejitter/dropchain filters drop anything sloppier).
"""

from __future__ import annotations

import struct
import time

from .ssh import ToonSSH

# tslib /etc/pointercal:  sx = (a*rx + b*ry + c)/s ;  sy = (d*rx + e*ry + f)/s
POINTERCAL = (13399, -2, -1084648, 12, -8590, 32873042, 65536)

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
SYN_REPORT, BTN_TOUCH = 0, 0x14a
ABS_X, ABS_Y, ABS_PRESSURE = 0, 1, 24

TOUCH_DEV = "/dev/input/touchscreen0"


def pixel_to_raw(px: float, py: float, cal=POINTERCAL) -> tuple[int, int]:
    """Invert the tslib calibration: screen pixel -> raw touchscreen coords."""
    a, b, c, d, e, f, s = cal
    det = a * e - b * d
    X, Y = px * s - c, py * s - f
    rx = (e * X - b * Y) / det
    ry = (-d * X + a * Y) / det
    return int(round(rx)), int(round(ry))


def _ev(typ: int, code: int, val: int) -> bytes:
    # input_event: timeval{long,long} + u16 type + u16 code + s32 value (16B LE)
    return struct.pack("<llHHi", 0, 0, typ, code, val)


class ToonTouch:
    def __init__(self, ssh: ToonSSH) -> None:
        self.ssh = ssh

    def tap(self, px: float, py: float, *, hold: float = 0.35,
            pressure: int = 380) -> tuple[int, int]:
        """Tap the screen at pixel (px, py). Returns the raw coords used."""
        rx, ry = pixel_to_raw(px, py)
        chan = self.ssh._transport.open_session(timeout=10)
        chan.exec_command(f"cat > {TOUCH_DEV}")
        # pen down -- BTN_TOUCH first, matching the real device's frame order
        chan.sendall(_ev(EV_KEY, BTN_TOUCH, 1) + _ev(EV_ABS, ABS_X, rx)
                     + _ev(EV_ABS, ABS_Y, ry) + _ev(EV_ABS, ABS_PRESSURE, pressure)
                     + _ev(EV_SYN, SYN_REPORT, 0))
        for i in range(max(1, int(hold / 0.01))):  # ~10ms sample cadence
            time.sleep(0.01)
            chan.sendall(_ev(EV_ABS, ABS_X, rx + (i % 3) - 1)
                         + _ev(EV_ABS, ABS_Y, ry + ((i + 1) % 3) - 1)
                         + _ev(EV_ABS, ABS_PRESSURE, pressure)
                         + _ev(EV_SYN, SYN_REPORT, 0))
        # pen up
        chan.sendall(_ev(EV_KEY, BTN_TOUCH, 0) + _ev(EV_ABS, ABS_PRESSURE, 0)
                     + _ev(EV_SYN, SYN_REPORT, 0))
        chan.shutdown_write()
        chan.recv_exit_status()
        return rx, ry
