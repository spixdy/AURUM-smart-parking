import json
from datetime import UTC, datetime

from aurum.db import Database, Reading
from aurum.influx import InfluxWriter, line
from aurum.config import InfluxSettings
from aurum.ingest import handle_message
from aurum.mqtt_io import parse_message

PFX = "aurum/parking"
TOPIC = f"{PFX}/igi/occupancy"
TS = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)


def msg(**kw):
    base = {"place_id": "igi", "occupied": 1800, "capacity": 3500, "ts": TS.isoformat()}
    base.update(kw)
    return json.dumps(base).encode()


def rejects(topic, payload):
    try:
        parse_message(topic, payload, PFX)
    except ValueError:
        return True
    return False


def test_valid_message_parses():
    r = parse_message(TOPIC, msg(), PFX)
    assert (r.place_id, r.occupied, r.capacity, r.ts) == ("igi", 1800, 3500, TS)


def test_defaults_capacity_and_assumes_utc_for_naive_ts():
    r = parse_message(TOPIC, json.dumps({"occupied": 10, "ts": "2026-11-02T13:00:00"}).encode(), PFX)
    assert r.capacity == 3500 and r.ts.tzinfo is not None


def test_bad_messages_are_rejected():
    assert rejects("evil/topic", msg())
    assert rejects(f"{PFX}/atlantis/occupancy", msg())
    assert rejects(f"{PFX}/igi/occupancy/extra", msg())
    assert rejects(TOPIC, b"not json")
    assert rejects(TOPIC, b"[1,2]")
    assert rejects(TOPIC, msg(occupied=-1))
    assert rejects(TOPIC, msg(occupied=99999))
    assert rejects(TOPIC, msg(occupied="lots"))
    assert rejects(TOPIC, msg(occupied=True))
    assert rejects(TOPIC, msg(capacity=0))
    assert rejects(TOPIC, msg(ts="yesterday"))
    assert rejects(TOPIC, msg(place_id="cp"))
    assert rejects(TOPIC, b"x" * 5000)
    assert rejects(TOPIC, b"\xff\xfe")


def test_database_upsert_latest_and_count():
    db = Database("sqlite:///:memory:")
    db.add_reading(Reading("igi", TS, 100, 3500))
    db.add_reading(Reading("igi", TS, 120, 3500))  # same key -> replaced
    db.add_reading(Reading("cp", TS, 5, 1200))
    assert db.count() == 2
    assert db.latest()["igi"].occupied == 120
    assert [r.occupied for r in db.readings("igi")] == [120]


def test_database_rejects_unknown_table_and_sql_injection_in_place_id():
    db = Database("sqlite:///:memory:")
    try:
        db.count("readings; DROP TABLE readings")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    assert db.readings("x' OR '1'='1") == []
    db.add_reading(Reading("igi", TS, 1, 3500))
    assert db.count() == 1


def test_ingest_stores_valid_and_drops_invalid():
    db = Database("sqlite:///:memory:")
    w = InfluxWriter(InfluxSettings())
    assert handle_message(db, w, TOPIC, msg(), PFX) is True
    assert handle_message(db, w, TOPIC, b"garbage", PFX) is False
    assert db.count() == 1


def test_influx_failure_does_not_block_sql_storage():
    class Boom:
        def write_reading(self, *a):
            raise RuntimeError("influx down")

    db = Database("sqlite:///:memory:")
    assert handle_message(db, Boom(), TOPIC, msg(), PFX) is True
    assert db.count() == 1


def test_line_protocol_escaping_and_types():
    s = line("occupancy", {"place": "a b,c"}, {"occupied": 5, "ratio": 0.5}, TS)
    assert s == f"occupancy,place=a\\ b\\,c occupied=5i,ratio=0.5 {int(TS.timestamp())}"


def test_influx_writer_posts_expected_request_and_is_noop_when_disabled():
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

    class Sess:
        def post(self, url, **kw):
            calls.append((url, kw))
            return Resp()

    InfluxWriter(InfluxSettings(), Sess()).write_reading("igi", TS, 1, 2)
    assert calls == []
    on = InfluxSettings.__new__(InfluxSettings)
    object.__setattr__(on, "url", "http://influx:8086/")
    object.__setattr__(on, "token", "tok")
    object.__setattr__(on, "org", "aurum")
    object.__setattr__(on, "bucket", "parking")
    InfluxWriter(on, Sess()).write_reading("igi", TS, 1, 2)
    url, kw = calls[0]
    assert url == "http://influx:8086/api/v2/write"
    assert kw["headers"]["Authorization"] == "Token tok" and kw["params"]["bucket"] == "parking"
