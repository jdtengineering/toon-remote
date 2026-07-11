"""Tiny CLI for the local Toon client.

Examples:
    toon --host 192.168.1.178 status
    toon --host 192.168.1.178 set-temp 20.5
    toon --host 192.168.1.178 scene home
    toon --host 192.168.1.178 resume
"""

from __future__ import annotations

import argparse
import json
import os

from .client import Scene, ToonLocal

DEFAULT_HOST = os.environ.get("TOON_HOST", "192.168.1.178")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="toon", description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST, help="Toon IP address")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="show thermostat + power usage")
    sub.add_parser("devices", help="dump the raw Z-Wave device map")
    p_temp = sub.add_parser("set-temp", help="set a manual target temperature")
    p_temp.add_argument("celsius", type=float)
    p_scene = sub.add_parser("scene", help="switch program preset")
    p_scene.add_argument("name", choices=[s.name.lower() for s in Scene])
    sub.add_parser("resume", help="return to the schedule")

    args = parser.parse_args(argv)
    toon = ToonLocal(args.host)

    if args.cmd == "status":
        t = toon.get_thermostat()
        p = toon.get_power_usage()
        print(f"Temperature : {t.current_temp:.2f} C")
        print(f"Setpoint    : {t.setpoint:.2f} C")
        scene = t.active_scene.name.title() if t.active_scene else "manual/none"
        print(f"Scene       : {scene}")
        print(f"Heating     : {'yes' if t.is_heating else 'no'}"
              f" (modulation {t.modulation_level}%)")
        if p.power_usage_w is not None:
            print(f"Power       : {p.power_usage_w:.0f} W")
        if p.gas_usage is not None:
            print(f"Gas         : {p.gas_usage}")
    elif args.cmd == "devices":
        print(json.dumps(toon.get_devices(), indent=2))
    elif args.cmd == "set-temp":
        toon.set_setpoint(args.celsius)
        print(f"Setpoint -> {args.celsius:.2f} C")
    elif args.cmd == "scene":
        toon.set_scene(Scene[args.name.upper()])
        print(f"Scene -> {args.name}")
    elif args.cmd == "resume":
        toon.resume_program()
        print("Resumed schedule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
