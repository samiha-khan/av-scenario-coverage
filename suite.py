import json
from pathlib import Path

from models import SCHEMA_FIELDS, Scenario

SUITE_PATH = Path(__file__).resolve().parent / "scenarios" / "reference_suite.json"


def load_suite(path=SUITE_PATH):
    """Load a scenario suite: a JSON list of objects with one key per schema field."""
    rows = json.loads(Path(path).read_text())
    return [Scenario.from_values(row) for row in rows]


def save_suite(scenarios, path=SUITE_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{field: scenario.as_dict()[field] for field in SCHEMA_FIELDS} for scenario in scenarios]
    path.write_text(json.dumps(rows, indent=2) + "\n")
