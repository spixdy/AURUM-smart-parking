import random
from datetime import datetime
from zoneinfo import ZoneInfo

from aurum import places, vision
from aurum.simulator import backfill_times, make_reading
from test_model import fc

IST = ZoneInfo("Asia/Kolkata")


def test_simulated_readings_are_valid_and_reproducible():
    f, when = fc(), datetime(2026, 11, 2, 13, 0, tzinfo=IST)
    for p in places.PLACES:
        a = make_reading(f, p, when, random.Random(5))
        b = make_reading(f, p, when, random.Random(5))
        assert a == b and 0 <= a.occupied <= a.capacity == p.capacity


def test_backfill_stays_inside_window_and_not_in_future():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=IST)
    ts = list(backfill_times(now, 2))
    assert ts and all(7 <= t.hour + t.minute / 60 <= 17.5 and t <= now for t in ts)
    assert len({t.date() for t in ts}) == 3


def test_vision_counts_match_annotation_file():
    v = vision.bay_counts()
    assert len(v) == 30 and int(v.bays.sum()) == 903
    assert int(v.free.sum()) == 273 and int(v.occupied.sum()) == 624 and int(v.partial.sum()) == 6
    assert v.occupancy.between(0, 1).all()
