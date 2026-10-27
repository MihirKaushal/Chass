"""Export an allowlisted model service bundle, never datasets, user photos, or secrets."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def export(output: Path):
    selection_file = ROOT / "artifacts/improvements/experiment-v1/selection.json"
    selection = json.loads(selection_file.read_text())
    models = {
        "detector": ROOT / "artifacts/chess-v2-baseline/best.pt",
        "classifier": ROOT / "artifacts/crop-classifier-v1/best.pt",
    }
    for name, path in models.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != selection[f"{name}_sha256"]:
            raise ValueError(f"{name} differs from the validated model selection.")
    # Refuse an existing destination rather than overwrite files or leave stale secrets behind.
    output.mkdir(parents=True, exist_ok=False)
    (output / "models").mkdir()
    for name, path in models.items():
        shutil.copyfile(path, output / "models" / f"{name}.pt")
    shutil.copyfile(selection_file, output / "models/selection.json")
    for name in ("Dockerfile", "requirements.txt"):
        shutil.copyfile(ROOT / "deploy" / name, output / name)
    for folder in (ROOT, ROOT / "ml"):
        destination = output / "scanner" / folder.relative_to(ROOT)
        destination.mkdir(parents=True, exist_ok=True)
        for path in folder.glob("*.py"):
            if path.name != "prepare_deployment.py":
                shutil.copyfile(path, destination / path.name)
    (output / "README.md").write_text(
        "# Chass Scanner Service\n\n"
        "Set SCANNER_SERVICE_TOKEN as a runtime secret. Use one worker. "
        "Inference is experimental; images are not persisted.\n"
        "Training data attribution and model limitations: see scanner/ml/IMPROVEMENTS.md "
        "and CHESS_V2_MODEL_CARD.md in the Chass source repository.\n"
    )
    for name in ("IMPROVEMENTS.md", "CHESS_V2_MODEL_CARD.md"):
        shutil.copyfile(ROOT / "ml" / name, output / "scanner/ml" / name)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/deployment")
    args = parser.parse_args()
    print(
        f"Prepared {export(args.output)}. Review before uploading; no network upload was performed."
    )
