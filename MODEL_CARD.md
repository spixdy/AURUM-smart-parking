# Model card

**Task** Predict occupancy ratio (occupied / capacity) of a car park from time of day and weekday.

**Training data** `occupancy_birmingham.csv`: 35,717 readings, 30 car parks, 4 Oct – 19 Dec 2016,
07:46–16:30 daily. `parking_sessions.csv`: 10,000 sessions used only for dwell-time ratios.

**Evaluation** Time-based split (train on the first 80% of days, test on the final 20%, never shuffled):
R² **0.84**, mean absolute error **7.6 percentage points** of capacity.

**Condition effects** (dwell-time ratios measured from sessions): rain ×1.15, public holiday ×0.86,
exam/peak-event day ×1.30. The campus event count had no measurable effect and is not used. These
are applied as multipliers (occupancy ≈ arrivals × dwell time); they are not separately validated
against occupancy.

**Uncertainty** The 80% range is ±1.28 σ of training residuals (σ = 0.072 of capacity). It is not a
calibrated prediction interval.

## Limitations
- Different city, country and year: Delhi traffic, climate, holidays and parking behaviour differ.
- Delhi capacities and the place-to-lot mapping are assumptions.
- Only 07:00–17:30; outside this window the model holds the nearest in-window value and flags it.
- Only 11 weeks of history: no seasonality, no yearly holidays, no special events.
- Camera data (`bay_annotations.xml`) is 30 labelled frames, used for display, not for training.

## Path to production
1. Collect real Delhi counts via MQTT for several months (all hours).
2. Add weather and holiday features from real feeds.
3. Retrain per place (`python -m aurum.model train`), evaluate with the same time-split, compare to the
   baseline "same hour last week".
4. Monitor forecast vs actual (Grafana *Live* dashboard) and retrain on a schedule.
