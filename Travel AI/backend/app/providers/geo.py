"""Shared geo helpers for provider adapters."""

from __future__ import annotations

import re
from typing import Optional, Tuple

_COORD_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$"
)


def parse_lat_lng(value: str) -> Optional[Tuple[float, float]]:
    match = _COORD_RE.fullmatch(value)
    if not match:
        return None
    latitude = float(match.group(1))
    longitude = float(match.group(2))
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return None
    return latitude, longitude
