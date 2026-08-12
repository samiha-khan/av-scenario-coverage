import pytest

from models import Scenario

DEFAULT_SCENARIO_VALUES = {
    "weather": "clear",
    "lighting": "day",
    "agent_mix": "mostly_vehicles",
    "maneuver_type": "lane_change",
    "road_type": "urban",
    "ego_speed_bucket": "medium",
}


@pytest.fixture
def make_scenario():
    def _make(**overrides):
        return Scenario.from_values({**DEFAULT_SCENARIO_VALUES, **overrides})

    return _make


@pytest.fixture
def sample_scenario(make_scenario):
    return make_scenario()
