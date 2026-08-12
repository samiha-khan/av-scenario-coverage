import pytest

from models import Scenario, SCHEMA_FIELDS, scenario_hash


def test_as_tuple_matches_schema_field_order(sample_scenario):
    values = sample_scenario.as_tuple()
    assert values == tuple(getattr(sample_scenario, field) for field in SCHEMA_FIELDS)


def test_as_dict_uses_plain_string_values(sample_scenario):
    data = sample_scenario.as_dict()
    assert data["weather"] == "clear"
    assert all(isinstance(value, str) for value in data.values())


def test_from_values_accepts_raw_strings(sample_scenario):
    rebuilt = Scenario.from_values(sample_scenario.as_dict())
    assert rebuilt == sample_scenario


def test_from_values_accepts_enum_members(sample_scenario):
    rebuilt = Scenario.from_values(
        {field: getattr(sample_scenario, field) for field in SCHEMA_FIELDS}
    )
    assert rebuilt == sample_scenario


def test_from_values_rejects_invalid_value(sample_scenario):
    data = sample_scenario.as_dict()
    data["weather"] = "hurricane"
    with pytest.raises(ValueError):
        Scenario.from_values(data)


def test_scenario_hash_is_deterministic(sample_scenario):
    assert scenario_hash(sample_scenario) == scenario_hash(sample_scenario)


def test_scenario_hash_is_sha256_hex(sample_scenario):
    digest = scenario_hash(sample_scenario)
    assert len(digest) == 64
    int(digest, 16)


def test_scenario_hash_differs_for_different_scenarios(sample_scenario):
    other = Scenario.from_values({**sample_scenario.as_dict(), "weather": "rain"})
    assert scenario_hash(sample_scenario) != scenario_hash(other)
