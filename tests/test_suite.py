from generator import generate_scenarios
from suite import load_suite, save_suite


def test_save_and_load_round_trip(tmp_path):
    scenarios = generate_scenarios(20, seed=5)
    path = tmp_path / "nested" / "suite.json"
    save_suite(scenarios, path)
    assert load_suite(path) == scenarios


def test_saved_suite_is_human_readable_json(tmp_path):
    path = tmp_path / "suite.json"
    save_suite(generate_scenarios(1, seed=0), path)
    text = path.read_text()
    assert '"weather":' in text
    assert text.endswith("\n")
