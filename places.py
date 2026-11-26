"""Catalogue of Delhi parking locations.

Capacities are indicative planning figures, not official counts. ``archetype`` names the
Birmingham car park whose demand pattern the model borrows for that place until real Delhi
sensor data is available.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    area: str
    capacity: int
    archetype: str
    lat: float
    lon: float
    kind: str


PLACES: tuple[Place, ...] = (
    Place("cp", "Connaught Place Inner Circle", "Central Delhi", 1200, "BHMNCPLDH01", 28.6315, 77.2167, "Commercial"),
    Place("citywalk", "Select Citywalk", "Saket", 1500, "BHMBRCBRG01", 28.5284, 77.2193, "Mall"),
    Place("promenade", "DLF Promenade", "Vasant Kunj", 1800, "Bull Ring", 28.5413, 77.1565, "Mall"),
    Place("khan", "Khan Market", "Lodhi Road", 600, "BHMBCCSNH01", 28.6003, 77.2270, "Market"),
    Place("indiagate", "India Gate Lawns", "Rajpath", 900, "BHMBCCTHL01", 28.6129, 77.2295, "Leisure"),
    Place("nehru", "Nehru Place Business Hub", "South Delhi", 1000, "BHMEURBRD01", 28.5491, 77.2533, "Office"),
    Place("ndls", "New Delhi Railway Station", "Paharganj", 1100, "BHMBRTARC01", 28.6429, 77.2192, "Transit"),
    Place("igi", "IGI Airport Terminal 3", "Aerocity", 3500, "BHMMBMMBX01", 28.5562, 77.1000, "Transit"),
    Place("mandapam", "Bharat Mandapam", "Pragati Maidan", 2500, "BHMNCPNST01", 28.6177, 77.2431, "Events"),
    Place("hauzkhas", "Hauz Khas Village", "South Delhi", 450, "Others-CCCPS133", 28.5535, 77.1930, "Leisure"),
    Place("qutub", "Qutub Minar", "Mehrauli", 500, "BHMBCCPST01", 28.5245, 77.1855, "Heritage"),
    Place("redfort", "Red Fort · Chandni Chowk", "Old Delhi", 700, "Others-CCCPS105a", 28.6562, 77.2410, "Heritage"),
)
BY_ID = {p.id: p for p in PLACES}


def get(place_id: str) -> Place:
    try:
        return BY_ID[place_id]
    except KeyError:
        raise KeyError(f"unknown place id: {place_id!r}") from None
