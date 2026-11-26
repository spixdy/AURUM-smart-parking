"""Occupancy model: training, persistence and prediction.

The model is a gradient-boosted regressor that learns occupancy ratio (occupied / capacity)
from time of day, weekday and car-park identity. Rain, public-holiday and peak-event effects
are applied afterwards as multipliers measured from the parking-session dataset (dwell-time
ratios: occupancy is roughly arrivals x dwell time).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from . import places
from .config import DATA, MODEL_PATH

WINDOW = (7.0, 17.5)  # hours the training data covers
SLOT_STEP = 0.5
FEATURES = ["t", "dow", "lot"]
MAX_RATIO = 0.99


@dataclass(frozen=True)
class Prediction:
    place_id: str
    ratio: float
    vehicles: int
    low: int
    high: int
    capacity: int
    in_window: bool

    @property
    def status(self) -> str:
        r = self.ratio
        if r < 0.5:
            return "Calm · easy parking"
        if r < 0.75:
            return "Moderately busy"
        if r < 0.9:
            return "Very busy"
        return "Near capacity"


def load_occupancy(path: str | Path = DATA / "occupancy_birmingham.csv") -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["LastUpdated"])
    d = d[(d.Occupancy >= 0) & (d.Capacity > 0)].copy()
    d["ratio"] = (d.Occupancy / d.Capacity).clip(0, 1.05)
    d["t"] = d.LastUpdated.dt.hour + d.LastUpdated.dt.minute / 60
    d["dow"] = d.LastUpdated.dt.dayofweek
    d["lot"] = d.SystemCodeNumber.astype("category")
    return d


def behaviour_modifiers(path: str | Path = DATA / "parking_sessions.csv") -> dict[str, float]:
    """Dwell-time ratios for rain / holiday / exam (peak-event) days."""
    b = pd.read_csv(path)

    def ratio(mask: pd.Series) -> float:
        return round(float(b[mask].duration_hours.mean() / b[~mask].duration_hours.mean()), 3)

    return {
        "rain": ratio(b.weather == "Rainy"),
        "holiday": ratio(b.is_holiday == 1),
        "peak_event": ratio(b.is_exam_day == 1),
    }


def _regressor() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.06, categorical_features=[2], random_state=7
    )


def _frame(t, dow, lot_code) -> pd.DataFrame:
    return pd.DataFrame({"t": t, "dow": dow, "lot": lot_code})


def train(
    occupancy_csv: str | Path = DATA / "occupancy_birmingham.csv",
    sessions_csv: str | Path = DATA / "parking_sessions.csv",
    out: str | Path = MODEL_PATH,
) -> dict:
    """Train, evaluate on the final 20% of days, refit on everything, save the bundle."""
    d = load_occupancy(occupancy_csv)
    codes = d.lot.cat.codes
    cut = d.LastUpdated.quantile(0.8)
    tr, te = d.LastUpdated <= cut, d.LastUpdated > cut
    probe = _regressor().fit(_frame(d.t[tr], d.dow[tr], codes[tr]), d.ratio[tr])
    pred = probe.predict(_frame(d.t[te], d.dow[te], codes[te])).clip(0, 1)
    metrics = {
        "holdout_mae": round(float(mean_absolute_error(d.ratio[te], pred)), 4),
        "holdout_r2": round(float(r2_score(d.ratio[te], pred)), 4),
        "train_rows": int(tr.sum()),
        "test_rows": int(te.sum()),
        "lots": int(d.lot.nunique()),
    }
    full = _regressor().fit(_frame(d.t, d.dow, codes), d.ratio)
    resid = d.ratio - full.predict(_frame(d.t, d.dow, codes)).clip(0, 1)
    bundle = {
        "model": full,
        "lots": list(d.lot.cat.categories),
        "sigma": round(float(resid.std()), 4),
        "mods": behaviour_modifiers(sessions_csv),
        "metrics": metrics,
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out)
    return metrics


class Forecaster:
    def __init__(self, bundle: dict):
        self._m = bundle["model"]
        self._lots = bundle["lots"]
        self.sigma: float = bundle["sigma"]
        self.mods: dict[str, float] = bundle["mods"]
        self.metrics: dict = bundle["metrics"]

    @classmethod
    def load(cls, path: str | Path = MODEL_PATH, train_if_missing: bool = True) -> Forecaster:
        if not Path(path).exists():
            if not train_if_missing:
                raise FileNotFoundError(f"{path} not found; run `python -m aurum.model train`")
            train(out=path)
        return cls(joblib.load(path))

    def multiplier(self, rain: bool = False, holiday: bool = False, peak_event: bool = False) -> float:
        m = 1.0
        for on, key in ((rain, "rain"), (holiday, "holiday"), (peak_event, "peak_event")):
            if on:
                m *= self.mods[key]
        return m

    def _base(self, place_id: str, t: np.ndarray, dow: int) -> np.ndarray:
        code = self._lots.index(places.get(place_id).archetype)
        tt = np.clip(t, *WINDOW)
        return np.clip(self._m.predict(_frame(tt, dow, code)), 0, MAX_RATIO)

    def predict(self, place_id: str, when: datetime, **cond: bool) -> Prediction:
        t = when.hour + when.minute / 60
        return self.curve(place_id, when.date(), times=[t], **cond)[0]

    def curve(self, place_id: str, day: date, times=None, **cond: bool) -> list[Prediction]:
        p = places.get(place_id)
        ts = np.asarray(times if times is not None else np.arange(WINDOW[0], WINDOW[1] + 1e-9, SLOT_STEP), float)
        ratios = np.minimum(self._base(place_id, ts, day.weekday()) * self.multiplier(**cond), MAX_RATIO)
        half = 1.28 * self.sigma * p.capacity  # ~80% interval
        out = []
        for t, r in zip(ts, ratios, strict=True):
            v = round(float(r) * p.capacity)
            out.append(Prediction(
                place_id, float(r), v, max(0, round(v - half)), min(p.capacity, round(v + half)),
                p.capacity, bool(WINDOW[0] <= t <= WINDOW[1]),
            ))
        return out

    def week_matrix(self, place_id: str, **cond: bool) -> np.ndarray:
        """7 x 22 matrix of occupancy ratios (Mon..Sun, 07:00..17:30)."""
        ts = np.arange(WINDOW[0], WINDOW[1] + 1e-9, SLOT_STEP)
        m = self.multiplier(**cond)
        return np.array([np.minimum(self._base(place_id, ts, d) * m, MAX_RATIO) for d in range(7)])


def export_web_grid(fc: Forecaster, path: str | Path) -> None:
    """Compact per-place grid used by the static website."""
    grid = {p.id: (fc.week_matrix(p.id) * 100).round().astype(int).tolist() for p in places.PLACES}
    Path(path).write_text(json.dumps({"sigma": fc.sigma, "mods": fc.mods, "grid": grid}))


def main() -> None:
    ap = argparse.ArgumentParser(description="AURUM model tools")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("train", help="train and save the model")
    sub.add_parser("export-web", help="write web/model_export.json")
    args = ap.parse_args()
    if args.cmd == "train":
        print(json.dumps(train(), indent=2))
    else:
        export_web_grid(Forecaster.load(), Path("web/model_export.json"))
        print("wrote web/model_export.json")


if __name__ == "__main__":
    main()
