from __future__ import annotations

import html
from pathlib import Path

from PIL import Image, ImageDraw

from .data import CLASSES, resolve_image


def draw_predictions(
    image: Image.Image, boxes, labels, scores=None, threshold=0.0, *, color="#137dc5"
) -> Image.Image:
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    for index, (box, label) in enumerate(zip(boxes, labels, strict=True)):
        if scores is not None and scores[index] < threshold:
            continue
        name = CLASSES[label]
        if scores is not None:
            name += f" {scores[index]:.2f}"
        draw.rectangle(box, outline=color, width=2)
        text_box = draw.textbbox((box[0], max(0, box[1] - 13)), name)
        draw.rectangle(text_box, fill=color)
        draw.text((box[0], max(0, box[1] - 13)), name, fill="white")
    return canvas


def evaluation_report(
    output: Path, root: Path, records: list[dict], predictions: list[dict], metrics: dict
):
    output.mkdir(parents=True, exist_ok=True)
    by_id = {item["image_id"]: item for item in predictions}
    cards = []
    for record in records:
        prediction = by_id[record["id"]]
        with Image.open(resolve_image(root, record["file"])) as image:
            truth = draw_predictions(image, record["boxes"], record["labels"])
            predicted = draw_predictions(
                image,
                prediction["boxes"],
                prediction["labels"],
                prediction["scores"],
                metrics["threshold"],
                color="#b55e19",
            )
        pair = Image.new("RGB", (truth.width * 2, truth.height))
        pair.paste(truth, (0, 0))
        pair.paste(predicted, (truth.width, 0))
        filename = f"image-{record['id']}.jpg"
        pair.save(output / filename, quality=92)
        cards.append(
            f'<article><h2>{html.escape(record["file"])}</h2><p>Left: ground truth. Right: predictions.</p><img src="{filename}" alt="Ground truth and predicted piece boxes"></article>'
        )
    rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{value['support']}</td><td>{value['precision']:.3f}</td><td>{value['recall']:.3f}</td></tr>"
        for name, value in metrics["per_class"].items()
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Chass Scanner Baseline</title>
<style>body{{font:16px/1.5 sans-serif;background:#f5e6ca;color:#1a365d;margin:32px auto;max-width:1100px;padding:0 20px}}article{{background:#ead8b5;padding:20px;margin:24px 0;border-radius:12px}}h2{{font-size:14px;overflow-wrap:anywhere}}img{{width:100%;height:auto}}td,th{{padding:8px;text-align:left}}table{{border-collapse:collapse}}tr{{border-bottom:1px solid #c6b38d}}</style>
<h1>Chass Scanner: piece detection baseline</h1><p>mAP@0.5: {metrics["map50"]:.3f}; precision: {metrics["precision"]:.3f}; recall: {metrics["recall"]:.3f}; threshold: {metrics["threshold"]:.2f}.</p>
<p>These are bounding-box metrics, not 64-square board accuracy. This small dataset does not establish reliability on other chess sets.</p><table><tr><th>Class</th><th>Support</th><th>Precision</th><th>Recall</th></tr>{rows}</table>{"".join(cards)}</html>"""
    (output / "index.html").write_text(page)
