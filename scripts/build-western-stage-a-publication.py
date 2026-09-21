#!/usr/bin/env python3
"""Build the frozen Western Stage-A publication package without rerunning retrieval."""

from __future__ import annotations

import csv
from hashlib import sha256
from html import escape
import json
import math
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# The managed project environment contains the scientific runtime, while the
# bundled base runtime supplies Pillow for offline raster export.
try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:
    base_site_packages = Path(sys.base_prefix) / "Lib" / "site-packages"
    if str(base_site_packages) not in sys.path:
        sys.path.append(str(base_site_packages))
    from PIL import Image, ImageDraw, ImageFont

from western.formal_eval import (  # noqa: E402
    pairwise_retrieval_statistics,
    retrieval_metrics,
)


PACKAGE_VERSION = "western-stage-a-publication-v0.1.5"
RUN_ID = "western-formal-v0.1.2-stage-a-20260918-01"
RUN_ROOT = (
    REPOSITORY_ROOT
    / "research"
    / "experiments"
    / "western_formal_v0_1"
    / "runs"
    / RUN_ID
)
RAW_PATH = RUN_ROOT / "stage_a_raw_results.jsonl"
RETRIEVAL_PATH = RUN_ROOT / "stage_a_retrieval.jsonl"
BENCHMARK_PATH = REPOSITORY_ROOT / "research" / "benchmarks" / "western_pilot_v0_1" / "benchmark.jsonl"
OUTPUT_ROOT = (
    REPOSITORY_ROOT
    / "research"
    / "experiments"
    / "western_formal_v0_1"
    / "stage_a_publication_v0_1_5"
)
TABLE_ROOT = OUTPUT_ROOT / "tables"
FIGURE_ROOT = OUTPUT_ROOT / "figures"

EXPECTED = {
    "stage_a_source_sha256": "91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e",
    "protocol_identity": "western_formal_v0.1.2",
    "protocol_sha256": "af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192",
    "corpus_chunks_sha256": "8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b",
    "source_registry_sha256": "722273140906b238e88cfdab4ddbb12d73c478f686ae23d0f501738ee6820703",
    "benchmark_sha256": "29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6",
    "benchmark_manifest_sha256": "bd8fc5105329d5d325fa8910b8a642bac6ddc954a25df6b9e299158aa29a22ae",
}

CONDITION_DEFINITIONS = {
    "R0": "lexical retrieval; top 4",
    "R1": "dense SiliconFlow BAAI/bge-m3; top 4",
    "R2": (
        "lexical + dense reciprocal-rank fusion "
        "(RRF = 1/(60 + lexical_rank) + 1/(60 + dense_rank)); top 4"
    ),
    "R3": "R2 candidate/rerank depth 12; BAAI/bge-reranker-v2-m3; top 4",
}

EXPECTED_HEADLINE = {
    "R0": (0.42857142857142855, 0.8909090909090909, 0.5952380952380952, 0.4503968253968254),
    "R1": (0.6349206349206349, 0.8909090909090909, 0.7857142857142857, 0.6051587301587302),
    "R2": (0.5396825396825397, 0.8909090909090909, 0.7380952380952381, 0.5734126984126984),
    "R3": (0.5238095238095238, 0.8363636363636363, 0.6904761904761905, 0.5813492063492064),
}

EXPECTED_PAIRWISE = {
    "R0_vs_R1": (0.20634920634920634, 0.08333333333333333, 0.3333333333333333, 0.03857421875),
    "R0_vs_R2": (0.09523809523809523, 0.011904761904761904, 0.19047619047619047, 0.03125),
    "R0_vs_R3": (0.10714285714285714, 0.011904761904761904, 0.21825396825396823, 0.2890625),
}

COLORS = {
    "chunk_recall": "#3366A8",
    "source_recall": "#5B8E3E",
    "hit": "#D17B2F",
    "mrr": "#7A5AA6",
    "ink": "#20262E",
    "muted": "#5E6975",
    "grid": "#D9DEE5",
    "background": "#FFFFFF",
}


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def assert_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-15):
        raise RuntimeError(f"{label} mismatch: expected {expected!r}, actual {actual!r}")


def verify_sources() -> dict[str, Any]:
    for path in (RAW_PATH, RETRIEVAL_PATH):
        actual = file_sha256(path)
        if actual != EXPECTED["stage_a_source_sha256"]:
            raise RuntimeError(f"Frozen Stage-A SHA256 mismatch for {path}: {actual}")
    if RAW_PATH.read_bytes() != RETRIEVAL_PATH.read_bytes():
        raise RuntimeError("Frozen Stage-A raw and retrieval aliases are not byte-identical")

    protocol_path = REPOSITORY_ROOT / "research" / "experiments" / "western_formal_v0_1" / "protocol_v0_1_2" / "protocol.json"
    benchmark_manifest_path = BENCHMARK_PATH.with_name("benchmark_manifest.json")
    corpus_root = REPOSITORY_ROOT / "research" / "corpus" / "west_v0_1"
    checks = {
        protocol_path: EXPECTED["protocol_sha256"],
        BENCHMARK_PATH: EXPECTED["benchmark_sha256"],
        benchmark_manifest_path: EXPECTED["benchmark_manifest_sha256"],
        corpus_root / "chunks.jsonl": EXPECTED["corpus_chunks_sha256"],
        corpus_root / "source_registry.json": EXPECTED["source_registry_sha256"],
    }
    for path, expected in checks.items():
        actual = file_sha256(path)
        if actual != expected:
            raise RuntimeError(f"Frozen input SHA256 mismatch for {path}: {actual}")

    records = read_jsonl(RETRIEVAL_PATH)
    if len(records) != 192:
        raise RuntimeError(f"Expected 192 Stage-A records, found {len(records)}")
    if any(not row.get("retrieval_success", True) for row in records):
        raise RuntimeError("Frozen Stage A contains an unexpected technical failure")
    return {
        "records": records,
        "cases": read_jsonl(BENCHMARK_PATH),
    }


def recompute(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    headline = retrieval_metrics(source["records"], source["cases"])
    pairwise = pairwise_retrieval_statistics(source["records"], source["cases"])
    if headline["frozen_eligible_case_count"] != 42:
        raise RuntimeError("Headline retrieval denominator is not 42")

    keys = (
        "aggregate_primary_gold_chunk_recall_at_4",
        "aggregate_primary_source_recall_at_4",
        "hit_at_4",
        "mrr",
    )
    for condition, expected_values in EXPECTED_HEADLINE.items():
        row = headline["by_condition"][condition]
        if row["case_count"] != 42 or row["technical_missing_eligible_cases_excluded"] != 0:
            raise RuntimeError(f"Unexpected denominator or missingness for {condition}")
        for key, expected in zip(keys, expected_values, strict=True):
            assert_close(row[key], expected, f"{condition} {key}")

    for comparison, expected_values in EXPECTED_PAIRWISE.items():
        row = pairwise["comparisons"][comparison]
        actual_values = (
            row["mean_paired_recall_difference"],
            row["bootstrap_95_percent_ci"][0],
            row["bootstrap_95_percent_ci"][1],
            row["mcnemar"]["exact_two_sided_p"],
        )
        if row["paired_n"] != 42 or row["technical_missing_pairs_excluded"] != 0:
            raise RuntimeError(f"Unexpected paired denominator or missingness for {comparison}")
        for label, actual, expected in zip(
            ("mean difference", "CI lower", "CI upper", "McNemar p"),
            actual_values,
            expected_values,
            strict=True,
        ):
            assert_close(actual, expected, f"{comparison} {label}")
    return headline, pairwise


def write_tables(headline: dict[str, Any], pairwise: dict[str, Any]) -> tuple[Path, Path]:
    TABLE_ROOT.mkdir(parents=True, exist_ok=True)
    headline_path = TABLE_ROOT / "stage_a_headline_metrics.csv"
    with headline_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "condition",
                "retrieval_definition",
                "n_cases",
                "primary_gold_chunk_recall_at_4",
                "primary_source_recall_at_4",
                "hit_at_4",
                "mrr",
            ],
        )
        writer.writeheader()
        for condition in ("R0", "R1", "R2", "R3"):
            row = headline["by_condition"][condition]
            writer.writerow(
                {
                    "condition": condition,
                    "retrieval_definition": CONDITION_DEFINITIONS[condition],
                    "n_cases": row["case_count"],
                    "primary_gold_chunk_recall_at_4": repr(row["aggregate_primary_gold_chunk_recall_at_4"]),
                    "primary_source_recall_at_4": repr(row["aggregate_primary_source_recall_at_4"]),
                    "hit_at_4": repr(row["hit_at_4"]),
                    "mrr": repr(row["mrr"]),
                }
            )

    pairwise_path = TABLE_ROOT / "stage_a_pairwise_vs_r0.csv"
    with pairwise_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "comparison",
                "n_paired_cases",
                "frozen_eligible_cases",
                "technical_missing_pairs_excluded",
                "mean_chunk_recall_difference",
                "bootstrap_ci_lower_95",
                "bootstrap_ci_upper_95",
                "r0_hit_comparison_miss",
                "r0_miss_comparison_hit",
                "discordant_pairs",
                "mcnemar_p_exact_two_sided",
            ],
        )
        writer.writeheader()
        for condition in ("R1", "R2", "R3"):
            row = pairwise["comparisons"][f"R0_vs_{condition}"]
            mcnemar = row["mcnemar"]
            writer.writerow(
                {
                    "comparison": f"{condition} - R0",
                    "n_paired_cases": row["paired_n"],
                    "frozen_eligible_cases": row["frozen_eligible_n"],
                    "technical_missing_pairs_excluded": row["technical_missing_pairs_excluded"],
                    "mean_chunk_recall_difference": repr(row["mean_paired_recall_difference"]),
                    "bootstrap_ci_lower_95": repr(row["bootstrap_95_percent_ci"][0]),
                    "bootstrap_ci_upper_95": repr(row["bootstrap_95_percent_ci"][1]),
                    "r0_hit_comparison_miss": mcnemar["r0_hit_comparison_miss"],
                    "r0_miss_comparison_hit": mcnemar["r0_miss_comparison_hit"],
                    "discordant_pairs": mcnemar["discordant_pairs"],
                    "mcnemar_p_exact_two_sided": repr(mcnemar["exact_two_sided_p"]),
                }
            )
    return headline_path, pairwise_path


def read_csv_numbers(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def svg_text(x: float, y: float, value: str, size: int, *, anchor: str = "middle", weight: str = "normal", color: str | None = None) -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{color or COLORS["ink"]}">{escape(value)}</text>'
    )


def write_headline_svg(rows: list[dict[str, Any]], path: Path) -> None:
    width, height = 1200, 760
    left, right, top, bottom = 100, 40, 90, 125
    plot_w, plot_h = width - left - right, height - top - bottom
    metrics = [
        ("primary_gold_chunk_recall_at_4", "Aggregate chunk recall@4", COLORS["chunk_recall"]),
        ("primary_source_recall_at_4", "Aggregate source recall@4", COLORS["source_recall"]),
        ("hit_at_4", "Hit@4", COLORS["hit"]),
        ("mrr", "MRR", COLORS["mrr"]),
    ]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="7in" height="4.43in" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{COLORS["background"]}"/>',
        svg_text(width / 2, 38, "Stage A headline retrieval metrics", 26, weight="bold"),
        svg_text(width / 2, 66, "Frozen Western pilot; n = 42; recalls aggregate primary-gold items", 17, color=COLORS["muted"]),
    ]
    for tick in range(0, 11, 2):
        value = tick / 10
        y = top + plot_h * (1 - value)
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
        parts.append(svg_text(left - 14, y + 6, f"{value:.1f}", 15, anchor="end", color=COLORS["muted"]))
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="{COLORS["ink"]}" stroke-width="2"/>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="{COLORS["ink"]}" stroke-width="2"/>')
    group_w = plot_w / len(rows)
    bar_w = 40
    gap = 8
    total_bars = len(metrics) * bar_w + (len(metrics) - 1) * gap
    for index, row in enumerate(rows):
        center = left + group_w * (index + 0.5)
        start = center - total_bars / 2
        for metric_index, (key, _, color) in enumerate(metrics):
            value = float(row[key])
            x = start + metric_index * (bar_w + gap)
            y = top + plot_h * (1 - value)
            parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w}" height="{top + plot_h - y:.2f}" fill="{color}"/>')
        parts.append(svg_text(center, top + plot_h + 32, row["condition"], 19, weight="bold"))
    legend_y = height - 48
    legend_total = 1060
    legend_x = (width - legend_total) / 2
    item_w = legend_total / len(metrics)
    for index, (_, label, color) in enumerate(metrics):
        x = legend_x + index * item_w
        parts.append(f'<rect x="{x:.2f}" y="{legend_y - 16}" width="20" height="20" fill="{color}"/>')
        parts.append(svg_text(x + 30, legend_y, label, 15, anchor="start"))
    parts.append(svg_text(left, top - 18, "Metric value", 17, anchor="start", weight="bold"))
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_pairwise_svg(rows: list[dict[str, Any]], path: Path) -> None:
    width, height = 1200, 650
    left, right, top, bottom = 210, 65, 105, 105
    plot_w, plot_h = width - left - right, height - top - bottom
    x_min, x_max = -0.05, 0.40

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_w

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="7in" height="3.79in" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{COLORS["background"]}"/>',
        svg_text(width / 2, 38, "Paired primary-gold chunk-recall differences", 25, weight="bold"),
        svg_text(width / 2, 67, "Comparison minus R0; 95% paired bootstrap confidence intervals", 17, color=COLORS["muted"]),
    ]
    ticks = [-0.05, 0.0, 0.1, 0.2, 0.3, 0.4]
    for value in ticks:
        x = sx(value)
        parts.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
        parts.append(svg_text(x, top + plot_h + 31, f"{value:.2f}", 15, color=COLORS["muted"]))
    zero_x = sx(0)
    parts.append(f'<line x1="{zero_x:.2f}" y1="{top}" x2="{zero_x:.2f}" y2="{top + plot_h}" stroke="{COLORS["ink"]}" stroke-width="2"/>')
    row_gap = plot_h / len(rows)
    for index, row in enumerate(rows):
        y = top + row_gap * (index + 0.5)
        mean = float(row["mean_chunk_recall_difference"])
        lower = float(row["bootstrap_ci_lower_95"])
        upper = float(row["bootstrap_ci_upper_95"])
        parts.append(svg_text(left - 22, y + 6, row["comparison"], 19, anchor="end", weight="bold"))
        parts.append(f'<line x1="{sx(lower):.2f}" y1="{y:.2f}" x2="{sx(upper):.2f}" y2="{y:.2f}" stroke="{COLORS["chunk_recall"]}" stroke-width="6"/>')
        parts.append(f'<line x1="{sx(lower):.2f}" y1="{y - 12:.2f}" x2="{sx(lower):.2f}" y2="{y + 12:.2f}" stroke="{COLORS["chunk_recall"]}" stroke-width="4"/>')
        parts.append(f'<line x1="{sx(upper):.2f}" y1="{y - 12:.2f}" x2="{sx(upper):.2f}" y2="{y + 12:.2f}" stroke="{COLORS["chunk_recall"]}" stroke-width="4"/>')
        parts.append(f'<circle cx="{sx(mean):.2f}" cy="{y:.2f}" r="11" fill="{COLORS["chunk_recall"]}" stroke="#FFFFFF" stroke-width="3"/>')
        parts.append(svg_text(sx(upper) + 18, y + 6, f"{mean:.3f} [{lower:.3f}, {upper:.3f}]", 15, anchor="start", color=COLORS["muted"]))
    parts.append(svg_text(left + plot_w / 2, height - 28, "Mean paired chunk-recall difference", 17, weight="bold"))
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def get_font(size: int, *, bold: bool = False) -> Any:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def centered_text(draw: Any, xy: tuple[float, float], value: str, font: Any, fill: str, *, anchor: str = "mm") -> None:
    draw.text(xy, value, font=font, fill=fill, anchor=anchor)


def write_headline_png(rows: list[dict[str, Any]], path: Path) -> None:
    width, height = 2100, 1329
    image = Image.new("RGB", (width, height), COLORS["background"])
    draw = ImageDraw.Draw(image)
    left, right, top, bottom = 175, 70, 165, 220
    plot_w, plot_h = width - left - right, height - top - bottom
    metrics = [
        ("primary_gold_chunk_recall_at_4", "Aggregate chunk recall@4", COLORS["chunk_recall"]),
        ("primary_source_recall_at_4", "Aggregate source recall@4", COLORS["source_recall"]),
        ("hit_at_4", "Hit@4", COLORS["hit"]),
        ("mrr", "MRR", COLORS["mrr"]),
    ]
    centered_text(draw, (width / 2, 55), "Stage A headline retrieval metrics", get_font(46, bold=True), COLORS["ink"])
    centered_text(draw, (width / 2, 112), "Frozen Western pilot; n = 42; recalls aggregate primary-gold items", get_font(30), COLORS["muted"])
    for tick in range(0, 11, 2):
        value = tick / 10
        y = top + plot_h * (1 - value)
        draw.line((left, y, left + plot_w, y), fill=COLORS["grid"], width=2)
        draw.text((left - 25, y), f"{value:.1f}", font=get_font(26), fill=COLORS["muted"], anchor="rm")
    draw.line((left, top, left, top + plot_h), fill=COLORS["ink"], width=4)
    draw.line((left, top + plot_h, left + plot_w, top + plot_h), fill=COLORS["ink"], width=4)
    group_w = plot_w / len(rows)
    bar_w, gap = 70, 14
    total_bars = len(metrics) * bar_w + (len(metrics) - 1) * gap
    for index, row in enumerate(rows):
        center = left + group_w * (index + 0.5)
        start = center - total_bars / 2
        for metric_index, (key, _, color) in enumerate(metrics):
            value = float(row[key])
            x = start + metric_index * (bar_w + gap)
            y = top + plot_h * (1 - value)
            draw.rectangle((x, y, x + bar_w, top + plot_h), fill=color)
        centered_text(draw, (center, top + plot_h + 50), row["condition"], get_font(32, bold=True), COLORS["ink"])
    legend_y = height - 70
    item_w = 480
    legend_x = (width - item_w * len(metrics)) / 2
    for index, (_, label, color) in enumerate(metrics):
        x = legend_x + index * item_w
        draw.rectangle((x, legend_y - 20, x + 34, legend_y + 14), fill=color)
        draw.text((x + 52, legend_y), label, font=get_font(26), fill=COLORS["ink"], anchor="lm")
    draw.text((left, top - 28), "Metric value", font=get_font(28, bold=True), fill=COLORS["ink"], anchor="ls")
    image.save(path, format="PNG", dpi=(300, 300), optimize=True)


def write_pairwise_png(rows: list[dict[str, Any]], path: Path) -> None:
    width, height = 2100, 1137
    image = Image.new("RGB", (width, height), COLORS["background"])
    draw = ImageDraw.Draw(image)
    left, right, top, bottom = 360, 115, 175, 180
    plot_w, plot_h = width - left - right, height - top - bottom
    x_min, x_max = -0.05, 0.40

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_w

    centered_text(draw, (width / 2, 55), "Paired primary-gold chunk-recall differences", get_font(44, bold=True), COLORS["ink"])
    centered_text(draw, (width / 2, 112), "Comparison minus R0; 95% paired bootstrap confidence intervals", get_font(29), COLORS["muted"])
    for value in (-0.05, 0.0, 0.1, 0.2, 0.3, 0.4):
        x = sx(value)
        draw.line((x, top, x, top + plot_h), fill=COLORS["grid"], width=2)
        centered_text(draw, (x, top + plot_h + 47), f"{value:.2f}", get_font(25), COLORS["muted"])
    draw.line((sx(0), top, sx(0), top + plot_h), fill=COLORS["ink"], width=4)
    row_gap = plot_h / len(rows)
    for index, row in enumerate(rows):
        y = top + row_gap * (index + 0.5)
        mean = float(row["mean_chunk_recall_difference"])
        lower = float(row["bootstrap_ci_lower_95"])
        upper = float(row["bootstrap_ci_upper_95"])
        draw.text((left - 38, y), row["comparison"], font=get_font(32, bold=True), fill=COLORS["ink"], anchor="rm")
        draw.line((sx(lower), y, sx(upper), y), fill=COLORS["chunk_recall"], width=10)
        draw.line((sx(lower), y - 18, sx(lower), y + 18), fill=COLORS["chunk_recall"], width=7)
        draw.line((sx(upper), y - 18, sx(upper), y + 18), fill=COLORS["chunk_recall"], width=7)
        radius = 17
        draw.ellipse((sx(mean) - radius, y - radius, sx(mean) + radius, y + radius), fill=COLORS["chunk_recall"], outline="#FFFFFF", width=4)
        draw.text((sx(upper) + 28, y), f"{mean:.3f} [{lower:.3f}, {upper:.3f}]", font=get_font(24), fill=COLORS["muted"], anchor="lm")
    centered_text(draw, (left + plot_w / 2, height - 42), "Mean paired chunk-recall difference", get_font(28, bold=True), COLORS["ink"])
    image.save(path, format="PNG", dpi=(300, 300), optimize=True)


def write_figures(headline_path: Path, pairwise_path: Path) -> None:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    headline_rows = read_csv_numbers(headline_path)
    pairwise_rows = read_csv_numbers(pairwise_path)
    write_headline_svg(headline_rows, FIGURE_ROOT / "stage_a_headline_metrics.svg")
    write_headline_png(headline_rows, FIGURE_ROOT / "stage_a_headline_metrics.png")
    write_pairwise_svg(pairwise_rows, FIGURE_ROOT / "stage_a_paired_recall_difference.svg")
    write_pairwise_png(pairwise_rows, FIGURE_ROOT / "stage_a_paired_recall_difference.png")


def markdown_headline_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Condition | Aggregate primary-gold chunk recall@4 | Aggregate primary-source recall@4 | Hit@4 | MRR |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f'| {row["condition"]} | {float(row["primary_gold_chunk_recall_at_4"]):.6f} | '
            f'{float(row["primary_source_recall_at_4"]):.6f} | {float(row["hit_at_4"]):.6f} | '
            f'{float(row["mrr"]):.6f} |'
        )
    return "\n".join(lines)


def markdown_pairwise_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Comparison | Paired n | Mean recall difference | Bootstrap 95% CI | Exact two-sided McNemar p |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        mean = float(row["mean_chunk_recall_difference"])
        lower = float(row["bootstrap_ci_lower_95"])
        upper = float(row["bootstrap_ci_upper_95"])
        p_value = float(row["mcnemar_p_exact_two_sided"])
        lines.append(
            f'| {row["comparison"]} | {row["n_paired_cases"]} | {mean:+.7f} | '
            f'[{lower:.7f}, {upper:.7f}] | {p_value:.8g} |'
        )
    return "\n".join(lines)


def write_results_and_readme(headline_path: Path, pairwise_path: Path) -> None:
    headline_rows = read_csv_numbers(headline_path)
    pairwise_rows = read_csv_numbers(pairwise_path)
    results = f"""# Stage A Results — W-RQ1

## Analysis population

This analysis addresses only W-RQ1: how retrieval strategies affect gold-evidence retrieval within the frozen MediRAG-West pilot corpus. It uses the frozen run `{RUN_ID}` and does not constitute a new experimental run. All 192 retrieval cells completed without a Stage-A technical failure. The benchmark contains 48 cases across four topic domains; the headline retrieval analysis includes the 42 supported or partially supported cases with non-empty primary gold evidence. The evidence base is a 16-review, 271-chunk pilot corpus, so the findings are pilot-specific.

## Headline retrieval metrics

{markdown_headline_table(headline_rows)}

R1 measured higher on the headline retrieval metrics in this frozen pilot. This is a descriptive result within the frozen corpus and benchmark; it is not a general retrieval-architecture ranking.

![Stage A headline retrieval metrics](figures/stage_a_headline_metrics.png)

## Paired comparisons against R0

Each comparison uses the successful-pair intersection (`n = 42`) with technical failures excluded rather than imputed as zero. Confidence intervals use the frozen 10,000-resample paired percentile bootstrap with seed `20260815`. McNemar p-values are exact and two-sided.

{markdown_pairwise_table(pairwise_rows)}

The effect estimates, confidence intervals, and exact p-values are reported descriptively. No significance stars, binary significance verdicts, rankings, or multiplicity correction have been added.

![Paired primary-gold chunk-recall differences](figures/stage_a_paired_recall_difference.png)

## Interpretation

Within this frozen pilot, the observed R1-minus-R0 paired mean primary-gold chunk-recall difference was positive, with a 95% bootstrap interval above zero. R2-minus-R0 and R3-minus-R0 also had positive observed paired mean differences and bootstrap intervals above zero. The exact two-sided McNemar p-values describe paired Hit@4 discordance and are presented separately from the recall effect estimates. These observations do not establish that any method is generally preferable outside this pilot.

## Latency limitation

Retrieval latency was confounded by cache state and execution order and is not cleanly interpretable in this frozen pilot. No speed ranking or comparative latency claim is made.

## Reproducibility

The authoritative source is `runs/{RUN_ID}/stage_a_retrieval.jsonl`, SHA256 `{EXPECTED["stage_a_source_sha256"]}`; its byte-identical raw alias is `stage_a_raw_results.jsonl`. Tables and figures are regenerated by `scripts/build-western-stage-a-publication.py`, which calls the existing frozen metric implementations in `backend/western/formal_eval.py` and fails closed on source-hash or result mismatches. `provenance.json` records the complete input and method anchors.
"""
    (OUTPUT_ROOT / "STAGE_A_RESULTS_v0.1.5.md").write_text(results, encoding="utf-8")

    readme = f"""# Western Stage-A publication package v0.1.5

This directory is a derived publication package for frozen Western Formal Study Stage A. It addresses W-RQ1 only. The frozen Stage-A raw retrieval evidence remains authoritative, and generating this package does not constitute a new experimental run or rerun retrieval.

W-RQ2 and W-RQ3 semantic estimates remain unavailable in this study version. No Stage-B generation content or Stage-C qualification output is used here.

## Regeneration

From the repository root, using the existing project environment:

```text
.venv\\Scripts\\python.exe scripts\\build-western-stage-a-publication.py
```

The builder verifies all frozen input hashes, calls the existing Stage-A metric implementations, checks the recomputed values against the sealed results, and then recreates the CSV, SVG, PNG, Markdown, and provenance outputs. The PNG exports are 300 dpi. The figures are generated from the publication CSV tables after those tables are derived from frozen Stage-A data.

## Interpretation boundary

The package describes retrieval outcomes within a 16-review, 271-chunk, four-topic pilot corpus and a 48-case benchmark. The headline denominator is 42. Latency is intentionally excluded from comparative conclusions because cache state and execution order confound it. The package contains no answer-quality, clinical-quality, W-RQ2, or W-RQ3 inference.
"""
    (OUTPUT_ROOT / "README.md").write_text(readme, encoding="utf-8")


def write_provenance() -> None:
    provenance = {
        "artifact_type": "western_stage_a_derived_publication_package",
        "package_version": PACKAGE_VERSION,
        "created_from_stage_a_run_id": RUN_ID,
        "stage_a_source_paths": [
            str(RETRIEVAL_PATH.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
            str(RAW_PATH.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        ],
        "stage_a_analysis_input_path": str(RETRIEVAL_PATH.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        "stage_a_byte_identical_alias_path": str(RAW_PATH.relative_to(REPOSITORY_ROOT)).replace("\\", "/"),
        "stage_a_source_relationship": "stage_a_retrieval.jsonl and stage_a_raw_results.jsonl are byte-identical aliases/copies; analysis reads stage_a_retrieval.jsonl only",
        "stage_a_source_sha256": EXPECTED["stage_a_source_sha256"],
        "stage_a_source_record_count": 192,
        "stage_a_technical_failure_count": 0,
        "protocol_identity": EXPECTED["protocol_identity"],
        "protocol_sha256": EXPECTED["protocol_sha256"],
        "corpus_chunks_sha256": EXPECTED["corpus_chunks_sha256"],
        "source_registry_sha256": EXPECTED["source_registry_sha256"],
        "benchmark_sha256": EXPECTED["benchmark_sha256"],
        "benchmark_manifest_sha256": EXPECTED["benchmark_manifest_sha256"],
        "analysis_denominator": {
            "benchmark_total_cases": 48,
            "definition": "supported or partially_supported cases with non-empty primary gold evidence",
            "excluded_insufficient_cases": 6,
            "excluded_insufficient_handling": "not scored as retrieval failures for headline primary-gold metrics",
            "n_cases": 42,
            "technical_missingness": "successful-pair intersection; technical failures excluded without zero imputation",
        },
        "conditions": CONDITION_DEFINITIONS,
        "metric_implementation_references": {
            "headline": "backend/western/formal_eval.py:retrieval_metrics",
            "paired": "backend/western/formal_eval.py:pairwise_retrieval_statistics",
            "bootstrap": "backend/western/formal_eval.py:_bootstrap_mean_ci",
        },
        "metric_definitions": {
            "aggregate_primary_gold_chunk_recall_at_4": "total retrieved primary-gold chunks divided by total primary-gold chunks across the headline denominator",
            "aggregate_primary_source_recall_at_4": "total retrieved primary-gold sources divided by total primary-gold sources across the headline denominator",
            "hit_at_4": "fraction of headline cases with at least one primary-gold chunk retrieved in the top four",
            "mrr": "mean reciprocal rank of the first retrieved primary-gold chunk; zero when none is retrieved",
            "paired_mean_chunk_recall_difference": "case-level comparison recall minus R0 recall, averaged over the successful-pair intersection",
            "mcnemar": "exact two-sided McNemar calculation over paired Hit@4 discordance",
        },
        "bootstrap_configuration": {
            "method": "paired percentile bootstrap of case-level recall differences",
            "resamples": 10000,
            "seed": 20260815,
            "lower_index": 250,
            "upper_index": 9750,
        },
        "source_code_script_path": "scripts/build-western-stage-a-publication.py",
        "source_code_script_sha256": file_sha256(Path(__file__).resolve()),
        "semantic_or_generation_outputs_used": False,
        "package_generation_mode": "offline_derived_analysis",
        "network_calls_used": False,
        "provider_calls_used": False,
        "stage_a_rerun": False,
    }
    (OUTPUT_ROOT / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    source = verify_sources()
    headline, pairwise = recompute(source)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    headline_path, pairwise_path = write_tables(headline, pairwise)
    write_figures(headline_path, pairwise_path)
    write_results_and_readme(headline_path, pairwise_path)
    write_provenance()
    print(f"Built {PACKAGE_VERSION} from {RUN_ID}")
    print(f"Verified Stage-A SHA256: {EXPECTED['stage_a_source_sha256']}")
    print("Stage A rerun: false; provider calls: false")


if __name__ == "__main__":
    main()
