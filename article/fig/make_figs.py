#!/usr/bin/env python3
"""Draw article/fig PNGs from committed results. No network.

Figure 2 is b3's registered primary endpoint.
Figure 3 counts Turbo bundles, not data items.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "article" / "fig"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

INK = (28, 25, 21)
MUTED = (90, 84, 74)
PAPER = (247, 244, 238)
RULE = (214, 208, 198)
FRESH = (15, 110, 86)
PUBLIC = (180, 83, 9)
RELEASE = (159, 18, 57)
COMMIT = (37, 99, 168)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTB if bold else FONT, size)


def parse_utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def stamp(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M")


def load_json(path: Path):
    return json.loads(path.read_text())


def bundle_latencies() -> list[dict]:
    batches = ROOT / "results" / "batches"
    rows = []

    # Phase 1 probes: one bundle. Earliest receipt and block time are in the inclusion note.
    rows.append(
        {
            "name": "probes",
            "bundle": "ppP0MDrvyDX0uCeDTVww7FC4iGbkcbZiIazuQrcSIWE",
            "receipt": parse_utc("2026-10-17T09:12:54Z"),
            "block": parse_utc("2026-10-17T09:21:32Z"),
            "height": 2023095,
        }
    )

    b1 = load_json(batches / "b1" / "inclusion_manifest.json")
    tx = load_json(batches / "b1" / "txids.json")
    cap = load_json(batches / "cap" / "txids.json")
    receipts = [
        parse_utc(tx["items"]["manifest"]["uploaded_utc"]),
        parse_utc(tx["items"]["generator-ciphertext"]["uploaded_utc"]),
        parse_utc(cap["items"]["manifest"]["uploaded_utc"]),
        parse_utc(cap["items"]["generator-ciphertext"]["uploaded_utc"]),
    ]
    rows.append(
        {
            "name": "b1+cap",
            "bundle": b1["turbo"]["bundle_id"],
            "receipt": min(receipts),
            "block": datetime.fromtimestamp(int(b1["block"]["timestamp"]), timezone.utc),
            "height": b1["block"]["height"],
        }
    )

    def v2_bundle(batch: str, partner: str, bundle: str, block_ts: int, height: int) -> dict:
        times = []
        for name in (batch, partner):
            doc = load_json(batches / name / "txids.json")
            for item in doc["items"].values():
                # Result uploads are later and are not this seal bundle.
                if item["uploaded_utc"] > "2026-10-18T12:00:00Z" and name in ("b2", "b3"):
                    continue
                times.append(parse_utc(item["uploaded_utc"]))
        return {
            "name": f"{batch}+{partner}",
            "bundle": bundle,
            "receipt": min(times),
            "block": datetime.fromtimestamp(block_ts, timezone.utc),
            "height": height,
        }

    rows.append(v2_bundle("b2", "cap2", "VWHJrEUcS-d9EXMzzJr9k6Qr2WKQLR9iwiMfm4nglgo", 1792267559, 2023391))
    rows.append(v2_bundle("b3", "cap3", "J67Udct-eWBqCnNfoT9c_d0baY48io8tHlJ8uD_ZVys", 1792311062, 2023739))
    for row in rows:
        row["seconds"] = int((row["block"] - row["receipt"]).total_seconds())
    return rows


def draw_fig1() -> None:
    width, height = 1400, 720
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((48, 28), "Commit, release, rebuild", font=font(28, True), fill=INK)
    draw.text(
        (48, 68),
        "Each row is one batch. The red mark is the drand release round. Times are UTC.",
        font=font(16),
        fill=MUTED,
    )
    # One sealed dot, at the L1 time. Receipt and block are both written under it.
    # Receipt and block are minutes apart, so two dots overlap on this scale.
    events = [
        (
            "b1  v1",
            [
                ("sealed", parse_utc("2026-10-17T15:21:00Z"), COMMIT, "receipt 10-17 15:05"),
                ("release", parse_utc("2026-10-18T09:00:00Z"), RELEASE, "10-18 09:00"),
                ("index", parse_utc("2026-10-18T19:48:40Z"), FRESH, "10-18 19:48"),
            ],
        ),
        (
            "b2  v2",
            [
                ("sealed", parse_utc("2026-10-17T20:05:59Z"), COMMIT, "receipt 10-17 20:02"),
                ("release", parse_utc("2026-10-19T00:00:00Z"), RELEASE, "10-19 00:00"),
                ("index", parse_utc("2026-10-19T06:06:42Z"), FRESH, "10-19 06:06"),
            ],
        ),
        (
            "b3  v2",
            [
                ("sealed", parse_utc("2026-10-18T08:11:02Z"), COMMIT, "receipt 10-18 08:04"),
                ("release", parse_utc("2026-10-19T12:00:00Z"), RELEASE, "10-19 12:00"),
                ("index", parse_utc("2026-10-19T18:19:24Z"), FRESH, "10-19 18:19"),
            ],
        ),
    ]
    t0 = parse_utc("2026-10-17T09:00:00Z")
    t1 = parse_utc("2026-10-20T00:00:00Z")
    span = (t1 - t0).total_seconds()
    left, right = 180, 1340

    def x_of(moment: datetime) -> int:
        return int(left + (moment - t0).total_seconds() / span * (right - left))

    for hour, label in (
        (parse_utc("2026-10-17T12:00:00Z"), "17 Oct 12:00"),
        (parse_utc("2026-10-18T00:00:00Z"), "18 Oct"),
        (parse_utc("2026-10-18T12:00:00Z"), "18 Oct 12:00"),
        (parse_utc("2026-10-19T00:00:00Z"), "19 Oct"),
        (parse_utc("2026-10-19T12:00:00Z"), "19 Oct 12:00"),
    ):
        x = x_of(hour)
        draw.line((x, 140, x, 640), fill=RULE, width=1)
        draw.text((x - 40, 116), label, font=font(12), fill=MUTED)

    for index, (name, points) in enumerate(events):
        y = 210 + index * 150
        draw.text((36, y - 10), name, font=font(18, True), fill=INK)
        draw.line((left, y, right, y), fill=INK, width=3)
        for label, moment, color, caption in points:
            x = x_of(moment)
            radius = 8
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
            draw.text((x - 28, y - 36), label, font=font(14, True), fill=color)
            draw.text((x - 58, y + 16), caption, font=font(12), fill=MUTED)
    draw.text(
        (48, 670),
        "The sealed dot is the L1 block time. The line under it is the Turbo receipt. Release is the drand round. Index is the results record, after the run.",
        font=font(14),
        fill=MUTED,
    )
    image.save(OUT / "fig1_timeline.png")


def draw_fig2() -> None:
    scores = load_json(ROOT / "results" / "batches" / "b3" / "scores.json")
    order = [
        "qwen3-4b-instruct-2507",
        "gemma-3-4b-it",
        "ministral-3-3b-instruct-2512",
        "falcon3-1b-instruct",
    ]
    short = ["Qwen3-4B", "Gemma-3-4B", "Ministral-3-3B", "Falcon3-1B"]
    width, height = 1400, 780
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((48, 24), "b3 registered scores: fresh arithmetic vs public GSM8K", font=font(26, True), fill=INK)
    draw.text(
        (48, 64),
        "Primary endpoint. Invalid and truncated answers count as wrong. Bars are accuracy. Lines are Wilson 95% intervals. n = 80 for both series.",
        font=font(15),
        fill=MUTED,
    )
    plot_left, plot_right = 120, 1320
    plot_top, plot_bottom = 160, 620
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=INK, width=2)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill=INK, width=2)
    for tick in (0, 0.25, 0.5, 0.75, 1.0):
        y = plot_bottom - int(tick * (plot_bottom - plot_top))
        draw.line((plot_left, y, plot_right, y), fill=RULE, width=1)
        draw.text((48, y - 8), f"{tick:.2f}", font=font(13), fill=MUTED)
    slot = (plot_right - plot_left) / len(order)
    legend_y = 660
    draw.rectangle((48, legend_y, 72, legend_y + 18), fill=FRESH)
    draw.text((80, legend_y - 2), "fresh arith_word", font=font(15), fill=INK)
    draw.rectangle((320, legend_y, 344, legend_y + 18), fill=PUBLIC)
    draw.text((352, legend_y - 2), "public GSM8K-test indexes 0..79", font=font(15), fill=INK)
    draw.text((48, 710), "These two sets were not built as matched templates. A gap is not a contamination estimate.", font=font(14), fill=MUTED)
    summary = []
    for index, model in enumerate(order):
        block = scores["models"][model]
        fresh = block["families"]["arith_word"]
        public = block["gsm8k"]
        summary.append((short[index], fresh, public))
        center = plot_left + slot * index + slot / 2
        bar_w = 36
        for shift, series, color in ((-28, fresh, FRESH), (28, public, PUBLIC)):
            acc = float(series["accuracy"])
            low, high = series["wilson95"]
            x = center + shift
            y = plot_bottom - int(acc * (plot_bottom - plot_top))
            draw.rectangle((x - bar_w / 2, y, x + bar_w / 2, plot_bottom), fill=color)
            y0 = plot_bottom - int(float(high) * (plot_bottom - plot_top))
            y1 = plot_bottom - int(float(low) * (plot_bottom - plot_top))
            draw.line((x, y0, x, y1), fill=INK, width=3)
            draw.line((x - 6, y0, x + 6, y0), fill=INK, width=3)
            draw.line((x - 6, y1, x + 6, y1), fill=INK, width=3)
            draw.text((x - 22, y - 22), f"{series['correct']}/{series['n']}", font=font(12), fill=INK)
        draw.text((center - 70, plot_bottom + 12), short[index], font=font(15, True), fill=INK)
    image.save(OUT / "fig2_fresh_vs_public.png")
    (OUT / "fig2_numbers.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")


def draw_fig3(rows: list[dict]) -> None:
    width, height = 1400, 720
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((48, 24), "Receipt to L1 inclusion, one point per bundle", font=font(26, True), fill=INK)
    ordered = sorted(rows, key=lambda row: row["seconds"])
    draw.text(
        (48, 64),
        "Latency is the L1 block timestamp minus the earliest Turbo receipt in that bundle. n = 4 bundles. Result and index uploads are not in this sample.",
        font=font(15),
        fill=MUTED,
    )
    plot_left, plot_right = 120, 1100
    plot_top, plot_bottom = 160, 560
    xmax = 1000
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=INK, width=2)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill=INK, width=2)
    for tick in (0, 200, 400, 600, 800, 1000):
        x = plot_left + int(tick / xmax * (plot_right - plot_left))
        draw.line((x, plot_top, x, plot_bottom), fill=RULE, width=1)
        draw.text((x - 16, plot_bottom + 10), str(tick), font=font(13), fill=MUTED)
    draw.text((plot_left, plot_bottom + 36), "seconds", font=font(14), fill=MUTED)
    n = len(ordered)
    points = []
    for index, row in enumerate(ordered, start=1):
        x = plot_left + int(row["seconds"] / xmax * (plot_right - plot_left))
        y = plot_bottom - int(index / n * (plot_bottom - plot_top))
        points.append((x, y))
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=COMMIT)
    if points:
        stair = [(plot_left, plot_bottom)]
        previous_y = plot_bottom
        for x, y in points:
            stair.append((x, previous_y))
            stair.append((x, y))
            previous_y = y
        stair.append((plot_right, previous_y))
        draw.line(stair, fill=RELEASE, width=3)
    for tick, label in ((0, "0"), (0.5, "0.5"), (1, "1")):
        y = plot_bottom - int(tick * (plot_bottom - plot_top))
        draw.text((70, y - 8), label, font=font(13), fill=MUTED)
    draw.text((40, 300), "ECDF", font=font(14), fill=MUTED)
    draw.text((1120, 150), "Bundles", font=font(16, True), fill=INK)
    y_label = 184
    for row in ordered:
        draw.text((1120, y_label), f"{row['name']}", font=font(15, True), fill=INK)
        draw.text((1120, y_label + 20), f"{row['seconds']} s", font=font(15), fill=MUTED)
        y_label += 52
    draw.text((1120, y_label + 8), "Not in sample:", font=font(14, True), fill=INK)
    draw.text((1120, y_label + 30), "14 result/index", font=font(14), fill=MUTED)
    draw.text((1120, y_label + 50), "uploads", font=font(14), fill=MUTED)
    draw.text((1120, y_label + 78), "Pending in sample: 0", font=font(14), fill=MUTED)
    image.save(OUT / "fig3_inclusion_ecdf.png")


def draw_cover() -> None:
    width, height = 1400, 600
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 12), fill=INK)
    draw.text((56, 40), "SealedBench", font=font(22, True), fill=MUTED)
    boxes = [
        (70, 160, 430, 460, COMMIT, "Sealed", "Generator ciphertext\nand manifest on Arweave\nbefore the round"),
        (520, 160, 880, 460, RELEASE, "Release", "One drand quicknet\nbeacon decrypts it\nand seeds the exam"),
        (970, 160, 1330, 460, FRESH, "Rebuilt", "Questions, frozen models,\nand scores anyone\ncan check"),
    ]
    for x0, y0, x1, y1, color, title, body in boxes:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=8, outline=color, width=4)
        draw.rectangle((x0, y0, x1, y0 + 14), fill=color)
        draw.text((x0 + 24, y0 + 40), title, font=font(36, True), fill=INK)
        draw.multiline_text((x0 + 24, y0 + 110), body, font=font(20), fill=MUTED, spacing=8)
    draw.polygon([(450, 290), (500, 310), (450, 330)], fill=INK)
    draw.polygon([(900, 290), (950, 310), (900, 330)], fill=INK)
    draw.text((56, 520), "Commit the exam before the questions exist.  b1, b2, and b3 are separate rounds.", font=font(18), fill=INK)
    image.save(OUT / "cover_1400x600.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = bundle_latencies()
    draw_fig1()
    draw_fig2()
    draw_fig3(rows)
    draw_cover()
    report = {
        "bundles": [
            {
                "name": row["name"],
                "bundle": row["bundle"],
                "seconds": row["seconds"],
                "receipt": row["receipt"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "block": row["block"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "height": row["height"],
            }
            for row in rows
        ]
    }
    (OUT / "fig3_numbers.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
