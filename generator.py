import random

from models import SCHEMA_FIELDS, FIELD_ENUMS, Scenario


def _validate_weights(weights):
    if weights is None:
        return
    for field, value_weights in weights.items():
        if field not in FIELD_ENUMS:
            raise ValueError(f"unknown schema field in weights: {field}")
        valid_values = {member.value for member in FIELD_ENUMS[field]}
        for value in value_weights:
            if value not in valid_values:
                raise ValueError(f"unknown value '{value}' for field '{field}'")


def generate_scenario(rng: random.Random, weights=None) -> Scenario:
    values = {}
    for field in SCHEMA_FIELDS:
        members = list(FIELD_ENUMS[field])
        field_weights = None
        if weights and field in weights:
            # Unspecified values in a partial weight dict default to 1.0
            # rather than being excluded from sampling.
            field_weights = [weights[field].get(member.value, 1.0) for member in members]
        values[field] = rng.choices(members, weights=field_weights, k=1)[0]
    return Scenario(**values)


def generate_scenarios(n, seed=None, weights=None):
    _validate_weights(weights)
    rng = random.Random(seed)
    return [generate_scenario(rng, weights) for _ in range(n)]
