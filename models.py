from dataclasses import dataclass
from enum import Enum
import hashlib


class Weather(str, Enum):
    CLEAR = "clear"
    RAIN = "rain"
    FOG = "fog"
    SNOW = "snow"


class Lighting(str, Enum):
    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"


class AgentMix(str, Enum):
    MOSTLY_VEHICLES = "mostly_vehicles"
    MIXED_VRU = "mixed_vru"
    HIGH_CYCLIST = "high_cyclist"
    HIGH_PEDESTRIAN = "high_pedestrian"
    EMERGENCY_VEHICLE_PRESENT = "emergency_vehicle_present"


class ManeuverType(str, Enum):
    LANE_CHANGE = "lane_change"
    TURN = "turn"
    MERGE = "merge"
    STOP = "stop"


class RoadType(str, Enum):
    HIGHWAY = "highway"
    URBAN = "urban"
    RESIDENTIAL = "residential"


class EgoSpeedBucket(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Order here defines the canonical field order used for hashing, pairwise
# coverage enumeration, and any tuple/row conversion elsewhere in the project.
SCHEMA_FIELDS = (
    "weather",
    "lighting",
    "agent_mix",
    "maneuver_type",
    "road_type",
    "ego_speed_bucket",
)

FIELD_ENUMS = {
    "weather": Weather,
    "lighting": Lighting,
    "agent_mix": AgentMix,
    "maneuver_type": ManeuverType,
    "road_type": RoadType,
    "ego_speed_bucket": EgoSpeedBucket,
}


@dataclass(frozen=True)
class Scenario:
    weather: Weather
    lighting: Lighting
    agent_mix: AgentMix
    maneuver_type: ManeuverType
    road_type: RoadType
    ego_speed_bucket: EgoSpeedBucket

    def as_tuple(self):
        return tuple(getattr(self, field) for field in SCHEMA_FIELDS)

    def as_dict(self):
        return {field: getattr(self, field).value for field in SCHEMA_FIELDS}

    @classmethod
    def from_values(cls, values):
        # Accepts either enum members or raw strings for each field, so callers
        # loading rows back from storage don't need their own conversion logic.
        kwargs = {}
        for field in SCHEMA_FIELDS:
            enum_cls = FIELD_ENUMS[field]
            raw = values[field]
            kwargs[field] = raw if isinstance(raw, enum_cls) else enum_cls(raw)
        return cls(**kwargs)


def scenario_hash(scenario: Scenario) -> str:
    payload = "|".join(value.value for value in scenario.as_tuple())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
