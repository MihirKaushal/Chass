import html

from PIL import Image, ImageDraw

from .data import CLASSES, save_json
from .report import draw_predictions


def write_review(output, rows, summary):
    output.mkdir(parents=True, exist_ok=True)
    previews = output / "previews"
    previews.mkdir(exist_ok=True)
    cards, queue = [], []
    # Put uncertain labels first; successful fixes remain available below them.
    reviewed = sorted(
        (row for row in rows if row["issues"] or row["changes"]),
        key=lambda row: (not bool(row["issues"]), row["key"]),
    )
    for index, row in enumerate(reviewed):
        try:
            with Image.open(row["path"]) as source:
                image = source.convert("RGB")
            if row["rotation"] != "none":
                image = image.transpose(
                    Image.Transpose.ROTATE_270
                    if row["rotation"] == "cw"
                    else Image.Transpose.ROTATE_90
                )
            annotations = row["annotations"]
            boxes = [
                [
                    a["bbox"][0],
                    a["bbox"][1],
                    a["bbox"][0] + a["bbox"][2],
                    a["bbox"][1] + a["bbox"][3],
                ]
                for a in annotations
            ]
            image = draw_predictions(image, boxes, [CLASSES.index(a["label"]) for a in annotations])
            draw = ImageDraw.Draw(image)
            for annotation in annotations:
                x, y, _, _ = annotation["bbox"]
                draw.text((x, y + 12), str(annotation["id"]), fill="#ff6400")
            image.thumbnail((1100, 1100))
            image.save(previews / f"{index}.jpg", quality=88)
            preview = f'<img src="previews/{index}.jpg" loading="lazy" alt="Piece boxes and original annotation IDs">'
        except (OSError, ValueError):
            preview = "<p>Preview unavailable; inspect the source file manually.</p>"
        status = (
            "Excluded: needs review"
            if row["issues"]
            else "Duplicate removed"
            if row.get("duplicate_of")
            else "Corrected"
        )
        details = html.escape("\n".join(row["issues"]) or "No unresolved flagged issue.")
        events = html.escape(str(row["changes"]))
        cards.append(
            f'<article class="{"excluded" if row["issues"] else "corrected"}"><h2>{html.escape(row["key"])}</h2><strong>{status}</strong><pre>{details}</pre>{preview}<details><summary>Correction log</summary><pre>{events}</pre></details></article>'
        )
        if row["issues"]:
            queue.append(
                {
                    "source_key": row["key"],
                    "sha256": row["sha256"],
                    "reasons": row["issues"],
                    "rotation": row["rotation"],
                    "preview": f"previews/{index}.jpg",
                    "source_annotation_ids": [a["id"] for a in row["annotations"]],
                }
            )
    save_json(output / "review_queue.json", queue)
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Chass dataset curation</title>
<style>body{{background:#f5e6ca;color:#1a365d;font:16px/1.5 sans-serif;max-width:1100px;margin:32px auto;padding:0 20px}}article{{background:#ead8b5;padding:20px;margin:20px 0;border-radius:12px}}h2{{font-size:15px;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}img{{max-width:100%;height:auto}}summary{{cursor:pointer}}.excluded{{border-left:5px solid #a42d32}}</style>
<h1>Chass dataset curation</h1><p>{summary["kept_images"]} images retained; {summary["removed_copy_images"]} copies removed; {summary["quarantined_images"]} images excluded pending review.</p>
<p>Raw files are unchanged. Excluded images are not used in any training/evaluation split. This is not an exhaustive semantic verification of every label.</p>
<p>Blue boxes show retained labels; orange numbers are original annotation IDs. The queue is in review_queue.json. Reviewed policy changes must be recorded in a new version before rebuilding.</p>{"".join(cards)}</html>"""
    (output / "index.html").write_text(page)
