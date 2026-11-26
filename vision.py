"""Camera-frame occupancy from the annotated parking images (CVAT polygons)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from .config import DATA

LABELS = ("free_parking_space", "not_free_parking_space", "partially_free_parking_space")


def bay_counts(xml_path: str | Path = DATA / "bay_annotations.xml") -> pd.DataFrame:
    rows = []
    for img in ET.parse(xml_path).getroot().iter("image"):
        n = {lab: 0 for lab in LABELS}
        for poly in img.iter("polygon"):
            lab = poly.attrib.get("label")
            if lab in n:
                n[lab] += 1
        total = sum(n.values())
        # a partially free bay is counted as half occupied
        occ = n["not_free_parking_space"] + 0.5 * n["partially_free_parking_space"]
        rows.append({
            "image": img.attrib["name"], "free": n[LABELS[0]], "occupied": n[LABELS[1]],
            "partial": n[LABELS[2]], "bays": total, "occupancy": round(occ / total, 3) if total else 0.0,
        })
    return pd.DataFrame(rows)
