"""Minimal InfluxDB 2.x writer over the HTTP line-protocol API (no extra dependency)."""
from __future__ import annotations

from datetime import datetime

import requests

from .config import InfluxSettings


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")


def line(measurement: str, tags: dict[str, str], fields: dict[str, float | int], ts: datetime) -> str:
    t = ",".join(f"{_esc(k)}={_esc(str(v))}" for k, v in sorted(tags.items()))
    f = ",".join(f"{_esc(k)}={v}i" if isinstance(v, int) and not isinstance(v, bool) else f"{_esc(k)}={v}"
                 for k, v in fields.items())
    return f"{_esc(measurement)},{t} {f} {int(ts.timestamp())}"


class InfluxWriter:
    def __init__(self, settings: InfluxSettings | None = None, session: requests.Session | None = None):
        self.s = settings or InfluxSettings()
        self.http = session or requests.Session()

    @property
    def enabled(self) -> bool:
        return self.s.enabled

    def write_reading(self, place_id: str, ts: datetime, occupied: int, capacity: int) -> None:
        if not self.enabled:
            return
        body = line(
            "occupancy", {"place": place_id},
            {"occupied": int(occupied), "capacity": int(capacity), "ratio": round(occupied / capacity, 4)}, ts,
        )
        r = self.http.post(
            f"{self.s.url.rstrip('/')}/api/v2/write",
            params={"org": self.s.org, "bucket": self.s.bucket, "precision": "s"},
            headers={"Authorization": f"Token {self.s.token}"},
            data=body.encode(), timeout=10,
        )
        r.raise_for_status()
