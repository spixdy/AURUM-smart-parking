"""Runtime settings, read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL_PATH = ROOT / "models" / "occupancy_model.joblib"


def _bool(v: str | None, default: bool) -> bool:
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MqttSettings:
    host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("MQTT_PORT", "1883")))
    username: str | None = field(default_factory=lambda: os.getenv("MQTT_USERNAME") or None)
    password: str | None = field(default_factory=lambda: os.getenv("MQTT_PASSWORD") or None)
    prefix: str = field(default_factory=lambda: os.getenv("MQTT_TOPIC_PREFIX", "aurum/parking"))

    @property
    def tls(self) -> bool:
        return _bool(os.getenv("MQTT_TLS"), self.port in (8883, 8084))


@dataclass(frozen=True)
class InfluxSettings:
    url: str | None = field(default_factory=lambda: os.getenv("INFLUX_URL") or None)
    token: str | None = field(default_factory=lambda: os.getenv("INFLUX_TOKEN") or None)
    org: str = field(default_factory=lambda: os.getenv("INFLUX_ORG", "aurum"))
    bucket: str = field(default_factory=lambda: os.getenv("INFLUX_BUCKET", "parking"))

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.token)


def database_url() -> str:
    return os.getenv("DATABASE_URL", f"sqlite:///{DATA / 'aurum.db'}")
