"""The detection results the README quotes: computed fresh, compared with the committed
docs/RESULTS.md, and held to the targets from the plan."""

from pathlib import Path

import pytest

from app.detection.findings import band
from app.evaluation import SAMPLE_FILES, evaluate_file, to_markdown

RESULTS = Path(__file__).resolve().parents[2] / "docs" / "RESULTS.md"


@pytest.fixture(scope="module")
def results():
    return {name: evaluate_file(name) for name in SAMPLE_FILES}


def test_committed_results_are_up_to_date(results):
    fresh = to_markdown([results[name] for name in SAMPLE_FILES])
    assert RESULTS.read_text() == fresh, "docs/RESULTS.md is out of date: run `make evaluate`"


def test_every_attack_is_caught_and_every_high_incident_is_real(results):
    for result in results.values():
        assert all(a.caught for a in result.attacks), result.name
        assert result.high_incidents_with_attack == result.high_incidents, result.name


def test_no_lookalike_reaches_high(results):
    for result in results.values():
        for lookalike in result.lookalikes:
            assert band(lookalike.highest_confidence) != "High", (result.name, lookalike.name)


def test_isolation_forest_finds_attacks_on_its_own(results):
    day = results["acme-web-day.ndjson.gz"]
    assert day.ml_ran
    assert day.ml_attacks >= 3
    assert not results["acme-web-small.ndjson"].ml_ran  # too few active user-hours
