"""Build web/index.html from web/site_template.html using the trained model."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aurum import places  # noqa: E402
from aurum.model import Forecaster  # noqa: E402


def build() -> int:
    fc = Forecaster.load()
    grid = [
        "".join(f"{min(int(round(v * 100)), 99):02d}" for row in fc.week_matrix(p.id) for v in row)
        for p in places.PLACES
    ]
    data = {
        "s": fc.sigma,
        "m": fc.mods,
        "p": [[p.name, p.area, p.capacity] for p in places.PLACES],
        "g": grid,
    }
    tpl = (ROOT / "web" / "site_template.html").read_text(encoding="utf-8")
    html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    (ROOT / "web" / "index.html").write_text(html, encoding="utf-8")
    return len(html)


if __name__ == "__main__":
    print(f"web/index.html written ({build()} bytes)")
