import tempfile
from datetime import date, datetime
from pathlib import Path

from aurum import model, places

_cache: dict = {}


def fc() -> model.Forecaster:
    if "fc" not in _cache:
        out = Path(tempfile.mkdtemp()) / "m.joblib"
        _cache["metrics"] = model.train(out=out)
        _cache["fc"] = model.Forecaster.load(out)
    return _cache["fc"]


MON_1PM = datetime(2026, 11, 2, 13, 0)


def test_holdout_accuracy_meets_floor():
    fc()
    assert _cache["metrics"]["holdout_r2"] > 0.80
    assert _cache["metrics"]["holdout_mae"] < 0.10


def test_predictions_within_bounds_for_every_place_and_slot():
    f = fc()
    for p in places.PLACES:
        for day in range(7):
            for pr in f.curve(p.id, date(2026, 11, 2 + day)):
                assert 0 <= pr.low <= pr.vehicles <= pr.high <= p.capacity
                assert 0 <= pr.ratio <= model.MAX_RATIO


def test_rain_raises_and_holiday_lowers_occupancy():
    f = fc()
    base = f.predict("cp", MON_1PM).ratio
    assert f.predict("cp", MON_1PM, rain=True).ratio >= base
    assert f.predict("cp", MON_1PM, holiday=True).ratio <= base


def test_stacked_conditions_never_exceed_cap():
    f = fc()
    for p in places.PLACES:
        assert f.predict(p.id, MON_1PM, rain=True, peak_event=True).ratio <= model.MAX_RATIO


def test_outside_window_is_flagged_and_still_valid():
    f = fc()
    night = f.predict("igi", datetime(2026, 11, 2, 23, 30))
    assert night.in_window is False and 0 <= night.vehicles <= night.capacity
    assert f.predict("igi", MON_1PM).in_window is True


def test_curve_has_22_half_hour_slots_and_week_matrix_shape():
    f = fc()
    assert len(f.curve("qutub", date(2026, 11, 2))) == 22
    assert f.week_matrix("qutub").shape == (7, 22)


def test_weekday_office_vs_weekend_pattern():
    f = fc()
    mon, sat = f.predict("nehru", MON_1PM).ratio, f.predict("nehru", datetime(2026, 11, 7, 13)).ratio
    assert mon > sat  # office hub is busier on weekdays


def test_unknown_place_rejected():
    try:
        fc().predict("atlantis", MON_1PM)
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_missing_model_without_autotrain_raises():
    try:
        model.Forecaster.load("/nonexistent/model.joblib", train_if_missing=False)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")
