import random

from models import Scenario

# Baseline failure probability for scenarios that don't match any entry in
# HARD_COMBINATIONS below.
BASELINE_FAILURE_PROBABILITY = 0.02

# Standard deviation of the gaussian noise added to a scenario's base failure
# probability before it's clamped back into [0, 1] and sampled. This is what
# keeps evaluate_scenario's outcomes non-deterministic run to run.
NOISE_STD_DEV = 0.1

# Synthetic ground truth: scenarios matching one of these partial parameter
# patterns are treated as inherently difficult, independent of any real
# classifier. Each "conditions" dict only needs to specify the fields
# relevant to that failure mode; fields left unspecified may take any value.
# Entries may overlap (a scenario can match more than one); the highest
# matching base_failure_probability wins.
HARD_COMBINATIONS = (
    {
        "conditions": {
            "lighting": "night",
            "weather": "fog",
            "agent_mix": "high_cyclist",
            "maneuver_type": "merge",
        },
        "base_failure_probability": 0.85,
    },
    {
        "conditions": {
            "lighting": "night",
            "agent_mix": "high_cyclist",
        },
        "base_failure_probability": 0.5,
    },
    {
        "conditions": {
            "weather": "snow",
            "road_type": "highway",
            "ego_speed_bucket": "high",
        },
        "base_failure_probability": 0.65,
    },
    {
        "conditions": {
            "lighting": "night",
            "agent_mix": "high_pedestrian",
            "road_type": "residential",
        },
        "base_failure_probability": 0.55,
    },
    {
        "conditions": {
            "agent_mix": "emergency_vehicle_present",
            "maneuver_type": "lane_change",
        },
        "base_failure_probability": 0.45,
    },
    {
        "conditions": {
            "weather": "rain",
            "lighting": "dusk",
            "maneuver_type": "turn",
            "road_type": "urban",
        },
        "base_failure_probability": 0.4,
    },
)


def _matches(scenario_values, conditions):
    return all(scenario_values[field] == value for field, value in conditions.items())


def base_failure_probability(scenario: Scenario) -> float:
    values = scenario.as_dict()
    matched = [
        entry["base_failure_probability"]
        for entry in HARD_COMBINATIONS
        if _matches(values, entry["conditions"])
    ]
    if not matched:
        return BASELINE_FAILURE_PROBABILITY
    return max(matched)


def evaluate_scenario(scenario: Scenario, rng: random.Random) -> bool:
    probability = base_failure_probability(scenario)
    noisy_probability = min(1.0, max(0.0, probability + rng.gauss(0.0, NOISE_STD_DEV)))
    passed = rng.random() >= noisy_probability
    return passed
