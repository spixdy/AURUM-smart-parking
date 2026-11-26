"""MQTT subscriber: validates readings and stores them in SQL (and InfluxDB if configured)."""
from __future__ import annotations

import logging

from .config import MqttSettings
from .db import Database
from .influx import InfluxWriter
from .mqtt_io import make_client, parse_message

log = logging.getLogger("aurum.ingest")


def handle_message(db: Database, influx: InfluxWriter, topic: str, payload: bytes, prefix: str) -> bool:
    """Store one message. Returns False (and logs) if it is invalid; never raises on bad input."""
    try:
        r = parse_message(topic, payload, prefix)
    except ValueError as e:
        log.warning("rejected message on %s: %s", topic, e)
        return False
    db.add_reading(r)
    try:
        influx.write_reading(r.place_id, r.ts, r.occupied, r.capacity)
    except Exception:  # InfluxDB being down must not stop SQL ingestion
        log.exception("influx write failed")
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s, db, influx = MqttSettings(), Database(), InfluxWriter()
    client = make_client(s, "aurum-ingest")

    def on_connect(c, _u, _f, rc, _p=None):
        log.info("connected to %s:%s (%s)", s.host, s.port, rc)
        c.subscribe(f"{s.prefix}/+/occupancy", qos=1)

    client.on_connect = on_connect
    client.on_message = lambda _c, _u, m: handle_message(db, influx, m.topic, m.payload, s.prefix)
    client.connect(s.host, s.port, keepalive=60)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
