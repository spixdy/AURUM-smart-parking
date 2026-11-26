"""Sensor simulator: generates plausible occupancy readings from the model plus noise.

Default: publish live readings to the MQTT broker. ``--offline`` writes straight to the database
(no broker needed). ``--backfill N`` writes N days of history so dashboards have data immediately.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import places
from .config import MqttSettings
from .db import Database, Reading
from .influx import InfluxWriter
from .model import WINDOW, Forecaster
from .mqtt_io import make_client, topic_for

IST = ZoneInfo("Asia/Kolkata")


def make_reading(fc: Forecaster, place: places.Place, when: datetime, rng: random.Random) -> Reading:
    base = fc.predict(place.id, when).ratio
    ratio = min(1.0, max(0.0, base + rng.gauss(0, fc.sigma)))
    return Reading(place.id, when, round(ratio * place.capacity), place.capacity, "simulator")


def backfill_times(now: datetime, days: int, step_min: int = 10):
    """Historic timestamps (IST) inside the operating window for the last ``days`` days, up to now."""
    for back in range(days, -1, -1):
        t = (now - timedelta(days=back)).replace(hour=int(WINDOW[0]), minute=0, second=0, microsecond=0)
        while t.hour + t.minute / 60 <= WINDOW[1]:
            if t <= now:
                yield t
            t += timedelta(minutes=step_min)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = run forever)")
    ap.add_argument("--interval", type=float, default=10.0, help="seconds between live ticks")
    ap.add_argument("--offline", action="store_true", help="write to the database, skip MQTT")
    ap.add_argument("--backfill", type=int, default=0, metavar="DAYS", help="write DAYS of history, then exit")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    fc, rng = Forecaster.load(), random.Random(a.seed)

    if a.backfill:
        db, influx = Database(), InfluxWriter()
        for when in backfill_times(datetime.now(IST), a.backfill):
            for p in places.PLACES:
                r = make_reading(fc, p, when, rng)
                db.add_reading(r)
                influx.write_reading(r.place_id, r.ts, r.occupied, r.capacity)
        print(f"database now holds {db.count()} readings")
        return

    s = MqttSettings()
    db = Database() if a.offline else None
    influx = InfluxWriter()
    client = None
    if not a.offline:
        client = make_client(s, f"aurum-sim-{random.randint(0, 9999)}")
        client.connect(s.host, s.port, keepalive=60)
        client.loop_start()
    n = 0
    try:
        while not a.ticks or n < a.ticks:
            when = datetime.now(IST)
            for p in places.PLACES:
                r = make_reading(fc, p, when, rng)
                if db:
                    db.add_reading(r)
                    influx.write_reading(r.place_id, r.ts, r.occupied, r.capacity)
                else:
                    body = {"place_id": r.place_id, "occupied": r.occupied, "capacity": r.capacity,
                            "ts": r.ts.isoformat()}
                    client.publish(topic_for(s, p.id), json.dumps(body), qos=1)
            n += 1
            print(f"tick {n} at {when:%H:%M:%S}")
            time.sleep(a.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if client:
            client.loop_stop()
            client.disconnect()


if __name__ == "__main__":
    main()
