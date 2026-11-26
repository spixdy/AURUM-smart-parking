import pandas as pd

from aurum import places
from aurum.config import DATA, MqttSettings


def test_place_ids_unique_and_capacities_positive():
    ids = [p.id for p in places.PLACES]
    assert len(ids) == len(set(ids)) == 12
    assert all(p.capacity > 0 for p in places.PLACES)


def test_every_archetype_exists_in_training_data():
    lots = set(pd.read_csv(DATA / "occupancy_birmingham.csv").SystemCodeNumber)
    assert {p.archetype for p in places.PLACES} <= lots


def test_delhi_coordinates_are_in_delhi():
    for p in places.PLACES:
        assert 28.3 < p.lat < 28.9 and 76.8 < p.lon < 77.5, p.name


def test_unknown_place_raises_keyerror():
    try:
        places.get("nowhere")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_mqtt_tls_inferred_from_port():
    import os

    os.environ.pop("MQTT_TLS", None)
    os.environ["MQTT_PORT"] = "8883"
    assert MqttSettings().tls is True
    os.environ["MQTT_PORT"] = "1883"
    assert MqttSettings().tls is False
    os.environ.pop("MQTT_PORT")
