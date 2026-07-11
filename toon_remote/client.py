"""Client for the local HTTP JSON API exposed by a rooted Eneco Toon.

A rooted Toon serves a small, unauthenticated JSON API on port 80. All values
come back as strings; this module parses them into typed dataclasses.

Temperatures on the wire are integer centidegrees (2050 == 20.50 C).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Optional

import requests


class Scene(enum.IntEnum):
    """Thermostat program presets, in the order Toon numbers them."""

    COMFORT = 0
    HOME = 1
    SLEEP = 2
    AWAY = 3


@dataclass
class ThermostatInfo:
    """Parsed result of ``getThermostatInfo``."""

    current_temp: float          # measured room temperature, C
    setpoint: float              # target temperature, C
    program_state: int           # 0 off, 1 on, 2 temporary override
    active_state: int            # active Scene, or -1 when none
    next_setpoint: float         # setpoint of the next scheduled program, C
    next_time: int               # unix time of the next program, 0 if none
    burner_info: int             # 0 off, 1 heating, 2 hot water, 3 preheat
    modulation_level: int        # burner modulation, 0-100
    raw: dict[str, Any]

    @property
    def active_scene(self) -> Optional[Scene]:
        try:
            return Scene(self.active_state)
        except ValueError:
            return None

    @property
    def is_heating(self) -> bool:
        return self.burner_info == 1


@dataclass
class PowerUsage:
    """Parsed result of ``GetCurrentUsage``. Fields are ``None`` when unknown."""

    power_usage_w: Optional[float]        # instantaneous electricity draw, W
    power_production_w: Optional[float]   # instantaneous production, W
    gas_usage: Optional[float]
    raw: dict[str, Any]


def _centi(value: Any) -> float:
    """Convert wire centidegrees (or centi-anything) to a float."""
    return int(value) / 100.0


def _opt_float(value: Any) -> Optional[float]:
    if value in (None, "null", "NaN", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ToonError(RuntimeError):
    """Raised when the Toon returns a non-ok result."""


class ToonLocal:
    """Talk to a rooted Toon over its local HTTP API.

    >>> toon = ToonLocal()            # host comes from config, or pass it in
    >>> toon.get_thermostat().current_temp
    22.12
    """

    def __init__(self, host: str | None = None, *, timeout: float = 8.0) -> None:
        from . import config
        self.host = config.require_host(host)
        self.timeout = timeout
        self._base = f"http://{self.host}"
        self._session = requests.Session()

    # -- low level -----------------------------------------------------------

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        resp = self._session.get(
            f"{self._base}{path}", params=params, timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("result") == "error":
            raise ToonError(data.get("error", "unknown error"))
        return data

    # -- reads ---------------------------------------------------------------

    def get_thermostat(self) -> ThermostatInfo:
        d = self._get("/happ_thermstat", action="getThermostatInfo")
        return ThermostatInfo(
            current_temp=_centi(d["currentTemp"]),
            setpoint=_centi(d["currentSetpoint"]),
            program_state=int(d["programState"]),
            active_state=int(d["activeState"]),
            next_setpoint=_centi(d.get("nextSetpoint", 0)),
            next_time=int(d.get("nextTime", 0)),
            burner_info=int(d.get("burnerInfo", 0)),
            modulation_level=int(d.get("currentModulationLevel", 0)),
            raw=d,
        )

    def get_power_usage(self) -> PowerUsage:
        d = self._get("/happ_pwrusage", action="GetCurrentUsage")
        pu = d.get("powerUsage", {})
        pp = d.get("powerProduction", {})
        gu = d.get("gasUsage", {})
        return PowerUsage(
            power_usage_w=_opt_float(pu.get("value")),
            power_production_w=_opt_float(pp.get("value")),
            gas_usage=_opt_float(gu.get("value")),
            raw=d,
        )

    def get_devices(self) -> dict[str, Any]:
        """Return the raw Z-Wave device map (smart plugs, meters, etc.)."""
        return self._get("/hdrv_zwave", action="getDevices.json")

    # -- writes --------------------------------------------------------------

    def set_setpoint(self, celsius: float) -> None:
        """Set a manual target temperature (a temporary hold)."""
        self._get(
            "/happ_thermstat",
            action="setSetpoint",
            Setpoint=int(round(celsius * 100)),
        )

    def set_scene(self, scene: Scene) -> None:
        """Switch to one of the Comfort/Home/Sleep/Away program presets."""
        self._get(
            "/happ_thermstat",
            action="changeSchemeState",
            state="2",
            temperatureState=int(scene),
        )

    def resume_program(self) -> None:
        """Cancel a manual hold and return to the schedule."""
        self._get("/happ_thermstat", action="changeSchemeState", state="1")
