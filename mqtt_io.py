"""MQTT helpers: topic layout, message validation and client construction.

Works with any MQTT 3.1.1/5 broker, including HiveMQ Cloud and EMQX Cloud (TLS on 8883).
Topic:   <prefix>/<place_id>/occupancy
Payload: {"place_id": "igi", "occupied": 1840, "capacity": 3500, "ts": "2026-11-02T13:00:00+05:30"}
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from . import places
from .config import MqttSettings
from .db import Reading


def topic_for(settings: MqttSettings, place_id: str) -> str:
    return f"{settings.prefix}/{place_id}/occupancy"


def parse_message(topic: str, payload: bytes | str, prefix: str = "aurum/parking") -> Reading:
    """Validate an incoming message. Raises ValueError with a readable reason on bad input."""
    parts = topic.split("/")
    pre = prefix.split("/")
    if len(parts) != len(pre) + 2 or parts[: len(pre)] != pre or parts[-1] != "occupancy":
        raise ValueError(f"unexpected topic: {topic!r}")
    place_id = parts[-2]
    if place_id not in places.BY_ID:
        raise ValueError(f"unknown place: {place_id!r}")
    if len(payload) > 2048:
        raise ValueError("payload too large")
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"payload is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    if data.get("place_id", place_id) != place_id:
        raise ValueError("place_id in payload does not match topic")
    occ, cap = data.get("occupied"), data.get("capacity", places.get(place_id).capacity)
    if isinstance(occ, bool) or not isinstance(occ, int | float) or occ != occ:
        raise ValueError("occupied must be a number")
    if isinstance(cap, bool) or not isinstance(cap, int | float) or cap <= 0:
        raise ValueError("capacity must be a positive number")
    occ, cap = int(occ), int(cap)
    if not 0 <= occ <= cap * 1.1:
        raise ValueError(f"occupied {occ} out of range for capacity {cap}")
    raw = data.get("ts")
    try:
        ts = datetime.fromisoformat(raw) if raw else datetime.now(UTC)
    except (TypeError, ValueError) as e:
        raise ValueError("ts must be an ISO-8601 timestamp") from e
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return Reading(place_id, ts, occ, cap, "mqtt")


def make_client(settings: MqttSettings, client_id: str):
    """Create a paho-mqtt (>=2.0) client configured for the given broker."""
    import paho.mqtt.client as mqtt

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if settings.username:
        c.username_pw_set(settings.username, settings.password)
    if settings.tls:
        c.tls_set()  # verifies the broker certificate against the system CA store
    return c
