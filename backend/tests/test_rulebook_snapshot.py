import json

from scripts.export_rulebook import OUTPUT, reference_catalog


def test_bundled_rulebook_matches_authoritative_catalog():
    assert json.loads(OUTPUT.read_text()) == reference_catalog(), (
        "Rulebook snapshot is stale. Run .venv/bin/python scripts/export_rulebook.py"
    )


def test_reference_catalog_has_no_live_or_environment_dependent_metadata():
    assert set(reference_catalog()) == {
        "schemaVersion",
        "pieces",
        "specialAbilities",
        "victoryModes",
        "gambit",
    }
