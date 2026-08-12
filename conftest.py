import pytest

from models import (
    Scenario,
    Weather,
    Lighting,
    AgentMix,
    ManeuverType,
    RoadType,
    EgoSpeedBucket,
)


@pytest.fixture
def sample_scenario():
    return Scenario(
        weather=Weather.CLEAR,
        lighting=Lighting.DAY,
        agent_mix=AgentMix.MOSTLY_VEHICLES,
        maneuver_type=ManeuverType.LANE_CHANGE,
        road_type=RoadType.URBAN,
        ego_speed_bucket=EgoSpeedBucket.MEDIUM,
    )
