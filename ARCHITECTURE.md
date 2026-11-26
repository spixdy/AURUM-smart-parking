# Architecture

## Data flow
1. **Sensors** (or `aurum.simulator`) publish JSON to `aurum/parking/<place_id>/occupancy` on an MQTT broker.
2. **`aurum.ingest`** subscribes, validates each message (`aurum.mqtt_io.parse_message`) and writes to
   SQL (`aurum.db`) and, when `INFLUX_URL`/`INFLUX_TOKEN` are set, to InfluxDB (`aurum.influx`).
   Invalid messages are logged and dropped. An InfluxDB outage never blocks SQL storage.
3. **Grafana** reads InfluxDB (time-series) and PostgreSQL (tables, latest values).
4. **Streamlit** loads the trained model, forecasts any place/date/time, and overlays live readings.

## Message contract
Topic `aurum/parking/<place_id>/occupancy`, payload:
```json
{"place_id": "igi", "occupied": 1840, "capacity": 3500, "ts": "2026-11-02T13:00:00+05:30"}
```
`capacity` and `ts` are optional (defaults: catalogue capacity, receive time). `occupied` must be
0 – 110% of capacity.

## Storage
| Table | Key | Purpose |
|---|---|---|
| `readings` | (place_id, ts, source) | sensor/simulator readings; re-sent readings overwrite |
| `forecasts` | (place_id, target_ts) | reserved for storing issued forecasts |

SQLite is the default (`data/aurum.db`). Set `DATABASE_URL=postgresql://…` for PostgreSQL; the schema
is created automatically.

## Model
HistGradientBoostingRegressor on (time of day, weekday, lot) → occupancy ratio. Rain, holiday and
peak-event multipliers come from dwell-time ratios in the parking-session data. See `MODEL_CARD.md`.
