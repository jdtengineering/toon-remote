# toon

Local client for a **rooted Eneco Toon** thermostat, talking directly to the
device over its LAN HTTP API — no cloud, no OAuth.

My Toon lives at `192.168.1.178`.

## What a rooted Toon exposes

A rooted Toon serves a small, **unauthenticated** JSON API on port 80. Anyone
on the LAN can read and control it, so keep it on a trusted network. Every value
comes back as a string; temperatures are integer centidegrees (`2250` = 22.50 °C).

Endpoints discovered on this device:

| Endpoint | Purpose |
| --- | --- |
| `GET /happ_thermstat?action=getThermostatInfo` | current temp, setpoint, scene, burner state |
| `GET /happ_thermstat?action=setSetpoint&Setpoint=2050` | manual hold at 20.50 °C |
| `GET /happ_thermstat?action=changeSchemeState&state=2&temperatureState=N` | switch to a scene (N = Comfort 0 / Home 1 / Sleep 2 / Away 3) |
| `GET /happ_thermstat?action=changeSchemeState&state=1` | resume the schedule |
| `GET /happ_pwrusage?action=GetCurrentUsage` | live electricity / gas usage (needs a P1 meter linked) |
| `GET /hdrv_zwave?action=getDevices.json` | Z-Wave device map (smart plugs, the `HAE_METER_v2` P1 meter, …) |

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

## Use it as a library

```python
from toon import ToonLocal, Scene

toon = ToonLocal("192.168.1.178")

info = toon.get_thermostat()
print(info.current_temp, info.setpoint, info.active_scene)

toon.set_setpoint(20.5)     # manual hold
toon.set_scene(Scene.HOME)  # switch preset
toon.resume_program()       # back to the schedule
```

## Use it from the shell

```powershell
toon --host 192.168.1.178 status
toon --host 192.168.1.178 set-temp 20.5
toon --host 192.168.1.178 scene home
toon --host 192.168.1.178 resume
```

`--host` defaults to the `TOON_HOST` environment variable (falling back to
`192.168.1.178`).

## Screenshot the Toon's screen

The Toon renders to a raw 800×480 framebuffer. With SSH access you can grab it
and view it on the PC:

```powershell
pip install -e ".[screenshot]"
python scripts/screenshot.py -o toon.png
```

## SSH access

The Toon runs an ancient Dropbear that only offers legacy crypto. From the shell,
add this to `~/.ssh/config` (already done on Jim's machine as `Host toon`):

```
Host toon 192.168.1.178
  HostName 192.168.1.178
  User root
  HostKeyAlgorithms +ssh-rsa
  KexAlgorithms +diffie-hellman-group14-sha1,diffie-hellman-group1-sha1
  Ciphers +aes128-cbc,3des-cbc
```

Then `ssh toon` (password `toon`). From Python use `toon.ssh.ToonSSH` — note
**paramiko must be `<4`**; v4/v5 dropped the SHA-1 algorithms the Toon needs.

## Notes

- `getThermostatInfo.burnerInfo`: `0` off, `1` heating, `2` hot water, `3` preheat.
- `programState`: `0` off, `1` following the schedule, `2` temporary override.
- The P1 usage fields read `null` until a smart meter is linked and reporting.

## Roadmap

- [ ] Poll history endpoints (`happ_pwrusage` graph data) for logging.
- [ ] Read Z-Wave smart-plug state and toggle plugs.
- [ ] Home Assistant / MQTT bridge.
