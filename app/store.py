"""Tiny JSON store for the AmmaCare demo. One family's data in one file."""
import json
import os
import threading
from datetime import datetime

_PATH = os.path.join(os.path.dirname(__file__), "..", "data.json")
_LOCK = threading.Lock()

DEFAULT_PROFILE = {
    "parent_name": "Amma (Leela)",
    "parent_place": "Kochi, Kerala",
    "language": "Malayalam",
    "child_name": "Son in Dubai",
    "medicines": [
        {"name": "BP tablet (Amlodipine 5mg)", "dose": "1 tablet", "times": ["08:00"]},
        {"name": "Sugar tablet (Metformin)", "dose": "1 tablet", "times": ["08:00", "20:00"]},
    ],
    "memory": {
        "last_medicine": "BP tablet (Amlodipine 5mg)",
        "preferred_pharmacy": "Sevana Medicals, Kochi",
        "regular_clinic": "Dr. Sharma's clinic",
        "emergency_contact": "Neighbour Ravi — +91 98XXXXXX01",
    },
}


def load() -> dict:
    if not os.path.exists(_PATH):
        save({"profile": DEFAULT_PROFILE, "tasks": [], "alerts": [],
              "checkins": [], "messages": []})
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def save(data: dict) -> None:
    with _LOCK:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
