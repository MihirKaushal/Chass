"""Generate the frontend's offline Rulebook data from the authoritative Python catalog."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.catalog import catalog_payload  # noqa: E402

OUTPUT = ROOT / "frontend/src/generated/rulebookCatalog.json"


def reference_catalog():
    catalog = catalog_payload()
    # No live engine availability, game state, or environment-dependent metadata.
    return {
        key: catalog[key]
        for key in ("schemaVersion", "pieces", "specialAbilities", "victoryModes", "gambit")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(reference_catalog(), indent=2, ensure_ascii=True) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != content:
            parser.exit(
                1, "Rulebook snapshot is stale. Run .venv/bin/python scripts/export_rulebook.py\n"
            )
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(content)


if __name__ == "__main__":
    main()
