#!/usr/bin/env python3
"""
render-phase-ii-western-publication-v0_2_1.py

Deterministic publication figure and table renderer for:
Phase II Western Manuscript v0.2.1

Generates:
- Figures 1, 2, 3 (SVG and 300 DPI PNG)
- Tables 1, 2, 3 (Markdown and CSV)
- Supplementary Tables S1, S2, S3 (Markdown and CSV)
- Source Data package with README.md
- Comprehensive captions document (CAPTIONS_v0.2.1.md)

Outputs are completely reproducible and offline, relying strictly on
frozen tracked CSV and manifest inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
from pathlib import Path
import shutil
import sys
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# Set stdout to UTF-8
sys.stdout.reconfigure(encoding="utf-8")

# Repository root
REPO_ROOT = Path(__file__).resolve().parent.parent

# Authoritative input paths
STAGE_A_TABLES = REPO_ROOT / "research" / "experiments" / "western_formal_v0_1" / "stage_a_publication_v0_1_5" / "tables"
STAGE_C2_TABLES = REPO_ROOT / "research" / "experiments" / "western_semantic_followup_v0_2" / "tables"

# Default output package root
DEFAULT_OUTPUT = REPO_ROOT / "research" / "manuscripts" / "phase_ii_western_v0_2_1" / "publication_package"

# Visual design constants
COLORS = {
    "background": "#FFFFFF",
    "ink": "#1F242D",
    "muted": "#5A6578",
    "subtle": "#8C96A5",
    "grid": "#E2E6EC",
    "border": "#CBD2DC",
    "box_bg": "#FFFFFF",
    "container_a_bg": "#F8FAFC",
    "container_b_bg": "#F9FAFB",
    "accent_point": "#2B4C7E",  # Color-blind safe deep slate/indigo
    "accent_line": "#3B629B",
    "terminal_stop": "#64748B",
    "reuse_flow": "#1E3A8A",
}

# Typography helper
def get_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))

# --- Programmatic Verification ---

def verify_source_data() -> dict[str, Any]:
    # Stage A headline
    stage_a_headline = read_csv(STAGE_A_TABLES / "stage_a_headline_metrics.csv")
    stage_a_pairwise = read_csv(STAGE_A_TABLES / "stage_a_pairwise_vs_r0.csv")

    # Semantic follow-up
    w_rq2_coverage = read_csv(STAGE_C2_TABLES / "w_rq2_primary_coverage_by_condition.csv")
    w_rq2_pairwise = read_csv(STAGE_C2_TABLES / "w_rq2_primary_pairwise_vs_r0.csv")
    w_rq2_presence = read_csv(STAGE_C2_TABLES / "w_rq2_unsupported_presence_by_condition.csv")
    w_rq2_contradictions = read_csv(STAGE_C2_TABLES / "w_rq2_contradictions_by_condition.csv")
    w_rq2_mcnemar = read_csv(STAGE_C2_TABLES / "w_rq2_unsupported_mcnemar_vs_r0.csv")
    w_rq3_dist = read_csv(STAGE_C2_TABLES / "w_rq3_insufficient_label_distribution.csv")
    w_rq3_cases = read_csv(STAGE_C2_TABLES / "w_rq3_case_by_condition.csv")

    # Verification assertions
    r1_a = [r for r in stage_a_headline if r["condition"] == "R1"][0]
    assert abs(float(r1_a["primary_gold_chunk_recall_at_4"]) - 0.634921) < 1e-5
    assert abs(float(r1_a["hit_at_4"]) - 0.785714) < 1e-5
    assert abs(float(r1_a["mrr"]) - 0.605159) < 1e-5

    r1_vs_r0_a = [r for r in stage_a_pairwise if "R1" in r["comparison"]][0]
    assert abs(float(r1_vs_r0_a["mean_chunk_recall_difference"]) - 0.206349) < 1e-5

    # Semantic coverage means
    cov_means = {r["retrieval_condition"]: float(r["mean"]) for r in w_rq2_coverage}
    assert abs(cov_means["R0"] - 0.543651) < 1e-5
    assert abs(cov_means["R1"] - 0.805556) < 1e-5
    assert abs(cov_means["R2"] - 0.626984) < 1e-5
    assert abs(cov_means["R3"] - 0.710317) < 1e-5

    # Semantic pairwise diffs
    sem_diffs = {r["comparison_condition"]: float(r["mean_difference"]) for r in w_rq2_pairwise}
    assert abs(sem_diffs["R1"] - 0.261905) < 1e-5
    assert abs(sem_diffs["R2"] - 0.083333) < 1e-5
    assert abs(sem_diffs["R3"] - 0.166667) < 1e-5

    # Unsupported presence
    unsupp_counts = {r["retrieval_condition"]: int(r["true_count"]) for r in w_rq2_presence}
    assert unsupp_counts == {"R0": 9, "R1": 5, "R2": 3, "R3": 3}

    # Contradictions
    contra_counts = {r["retrieval_condition"]: int(r["true_count"]) for r in w_rq2_contradictions}
    assert contra_counts == {"R0": 5, "R1": 1, "R2": 2, "R3": 1}

    # W-RQ3 distribution
    r0_w3 = [r for r in w_rq3_dist if r["retrieval_condition"] == "R0"][0]
    assert int(r0_w3["appropriate_abstention"]) == 1
    assert int(r0_w3["appropriate_bounded_insufficiency"]) == 5

    return {
        "stage_a_headline": stage_a_headline,
        "stage_a_pairwise": stage_a_pairwise,
        "w_rq2_coverage": w_rq2_coverage,
        "w_rq2_pairwise": w_rq2_pairwise,
        "w_rq2_presence": w_rq2_presence,
        "w_rq2_contradictions": w_rq2_contradictions,
        "w_rq2_mcnemar": w_rq2_mcnemar,
        "w_rq3_dist": w_rq3_dist,
        "w_rq3_cases": w_rq3_cases,
    }


# --- SVG Utilities ---

def svg_header(width: int, height: int) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{COLORS["background"]}"/>',
    ]

def svg_text(x: float, y: float, text: str, size: int, *, anchor: str = "middle", weight: str = "normal", color: str | None = None) -> str:
    escaped = html.escape(text)
    c = color or COLORS["ink"]
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{c}">{escaped}</text>'
    )

def svg_rect(x: float, y: float, w: float, h: float, *, fill: str = "#FFFFFF", stroke: str = "#CBD2DC", stroke_width: int = 1, rx: int = 0, stroke_dasharray: str = "") -> str:
    dash = f' stroke-dasharray="{stroke_dasharray}"' if stroke_dasharray else ''
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"{dash}/>'

def svg_line(x1: float, y1: float, x2: float, y2: float, *, stroke: str = "#CBD2DC", stroke_width: int = 1, stroke_dasharray: str = "") -> str:
    dash = f' stroke-dasharray="{stroke_dasharray}"' if stroke_dasharray else ''
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{stroke}" stroke-width="{stroke_width}"{dash}/>'


# --- Figure 1: Study Flow ---

def render_figure_1(out_svg: Path, out_png: Path) -> None:
    width, height = 1400, 960

    # SVG rendering
    svg = svg_header(width, height)

    # Title & Subtitle
    svg.append(svg_text(width / 2, 40, "Figure 1: MediRAG Phase II Western Evidence Study Architecture", 24, weight="bold"))
    svg.append(svg_text(width / 2, 68, "Formal pilot evaluation sequence (v0.1.5) and separate post-study evidence-grounded semantic follow-up (v0.2)", 15, color=COLORS["muted"]))

    # Top Common Header: Corpus & Benchmark
    corpus_w, corpus_h = 500, 92
    corpus_x = (width - corpus_w) / 2
    corpus_y = 86
    svg.append(svg_rect(corpus_x, corpus_y, corpus_w, corpus_h, fill="#FFFFFF", stroke=COLORS["border"], stroke_width=2, rx=6))
    svg.append(svg_text(width / 2, corpus_y + 25, "Western Pilot Corpus", 16, weight="bold"))
    svg.append(svg_text(width / 2, corpus_y + 49, "16 PMC Open Access Systematic Reviews (4 Topic Domains)", 13, color=COLORS["muted"]))
    svg.append(svg_text(width / 2, corpus_y + 71, "271 deterministic chunks · structured source provenance", 13, color=COLORS["muted"]))

    # Arrow to Benchmark
    svg.append(svg_line(width / 2, corpus_y + corpus_h, width / 2, corpus_y + corpus_h + 23, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(f'<polygon points="{width/2 - 5},{corpus_y + corpus_h + 17} {width/2 + 5},{corpus_y + corpus_h + 17} {width/2},{corpus_y + corpus_h + 24}" fill="{COLORS["accent_line"]}"/>')

    bench_y = corpus_y + corpus_h + 24
    bench_w, bench_h = 520, 72
    bench_x = (width - bench_w) / 2
    svg.append(svg_rect(bench_x, bench_y, bench_w, bench_h, fill="#FFFFFF", stroke=COLORS["border"], stroke_width=2, rx=6))
    svg.append(svg_text(width / 2, bench_y + 26, "Western Pilot Benchmark (48 Cases)", 16, weight="bold"))
    svg.append(svg_text(width / 2, bench_y + 50, "42 answerable cases (W-RQ1 & W-RQ2) · 6 insufficient-evidence cases (W-RQ3)", 13, color=COLORS["muted"]))

    # Main Containers: Left = Western Formal Study v0.1.5, Right = Semantic Follow-up v0.2
    top_y = 308
    container_h = 630
    container_w = 610
    left_x = 55
    right_x = 735

    # Connector from Benchmark to Container A
    mid_bench_y = 290
    svg.append(svg_line(width / 2, bench_y + bench_h, width / 2, mid_bench_y, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(svg_line(width / 2, mid_bench_y, left_x + container_w / 2, mid_bench_y, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(svg_line(left_x + container_w / 2, mid_bench_y, left_x + container_w / 2, top_y, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(f'<polygon points="{left_x + container_w/2 - 5},{top_y - 7} {left_x + container_w/2 + 5},{top_y - 7} {left_x + container_w/2},{top_y}" fill="{COLORS["accent_line"]}"/>')

    # Container 1: Western Formal Study v0.1.5 (Solid Border)
    svg.append(svg_rect(left_x, top_y, container_w, container_h, fill=COLORS["container_a_bg"], stroke=COLORS["ink"], stroke_width=2, rx=8))
    svg.append(svg_text(left_x + container_w / 2, top_y + 28, "WESTERN FORMAL STUDY v0.1.5", 17, weight="bold", color=COLORS["ink"]))
    svg.append(svg_text(left_x + container_w / 2, top_y + 48, "Historically Closed Study · Defined Stopping Rule", 13, color=COLORS["muted"]))

    # Internal arrow from header to Stage A
    svg.append(svg_line(left_x + container_w / 2, top_y + 54, left_x + container_w / 2, top_y + 75, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(f'<polygon points="{left_x + container_w/2 - 5},{top_y + 68} {left_x + container_w/2 + 5},{top_y + 68} {left_x + container_w/2},{top_y + 75}" fill="{COLORS["accent_line"]}"/>')

    # Stage A
    box_w, box_h = 530, 105
    box_x = left_x + (container_w - box_w) / 2
    box_a_y = top_y + 75
    svg.append(svg_rect(box_x, box_a_y, box_w, box_h, fill="#FFFFFF", stroke=COLORS["border"], stroke_width=1.5, rx=6))
    svg.append(svg_text(left_x + container_w / 2, box_a_y + 26, "Stage A: Evidence Retrieval Experiment", 15, weight="bold"))
    svg.append(svg_text(left_x + container_w / 2, box_a_y + 48, "4 retrieval conditions (R0 lexical, R1 dense, R2 fusion, R3 rerank) × 48 cases", 13, color=COLORS["muted"]))
    svg.append(svg_text(left_x + container_w / 2, box_a_y + 68, "192/192 retrieval cells completed · 0 technical missingness", 13, color=COLORS["muted"]))
    svg.append(svg_text(left_x + container_w / 2, box_a_y + 90, "W-RQ1 estimable: headline recall, Hit@4, and MRR (n = 42)", 12, weight="bold", color=COLORS["ink"]))

    # Arrow A -> B
    svg.append(svg_line(left_x + container_w / 2, box_a_y + box_h, left_x + container_w / 2, box_a_y + box_h + 30, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(f'<polygon points="{left_x + container_w/2 - 5},{box_a_y + box_h + 25} {left_x + container_w/2 + 5},{box_a_y + box_h + 25} {left_x + container_w/2},{box_a_y + box_h + 32}" fill="{COLORS["accent_line"]}"/>')

    # Stage B
    box_b_y = box_a_y + box_h + 32
    svg.append(svg_rect(box_x, box_b_y, box_w, box_h, fill="#FFFFFF", stroke=COLORS["border"], stroke_width=1.5, rx=6))
    svg.append(svg_text(left_x + container_w / 2, box_b_y + 26, "Stage B: Controlled Answer Generation", 15, weight="bold"))
    svg.append(svg_text(left_x + container_w / 2, box_b_y + 48, "Fixed Qwen/Qwen3-8B generator (temp 0, max 256 tokens)", 13, color=COLORS["muted"]))
    svg.append(svg_text(left_x + container_w / 2, box_b_y + 68, "192 primary answers completed · frozen dataset preserved", 13, color=COLORS["muted"]))
    svg.append(svg_text(left_x + container_w / 2, box_b_y + 90, "Supplies generated text; does not estimate semantic quality by itself", 12, color=COLORS["muted"]))

    # Arrow B -> Stage C Terminal
    svg.append(svg_line(left_x + container_w / 2, box_b_y + box_h, left_x + container_w / 2, box_b_y + box_h + 30, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(f'<polygon points="{left_x + container_w/2 - 5},{box_b_y + box_h + 25} {left_x + container_w/2 + 5},{box_b_y + box_h + 25} {left_x + container_w/2},{box_b_y + box_h + 32}" fill="{COLORS["accent_line"]}"/>')

    # Stage C Terminal Box
    box_c_y = box_b_y + box_h + 32
    box_c_h = 140
    svg.append(svg_rect(box_x, box_c_y, box_w, box_c_h, fill="#FFFFFF", stroke=COLORS["terminal_stop"], stroke_width=2, rx=6))
    svg.append(svg_text(left_x + container_w / 2, box_c_y + 28, "Automated Stage C: Evaluator Qualification", 15, weight="bold", color=COLORS["terminal_stop"]))
    svg.append(svg_text(left_x + container_w / 2, box_c_y + 52, "Prospective qualification protocol (Wave 1 & Wave 2)", 13, color=COLORS["muted"]))
    svg.append(svg_text(left_x + container_w / 2, box_c_y + 74, "Reached stopping rule: zero Primary Judges qualified", 13, color=COLORS["muted"]))
    svg.append(svg_text(left_x + container_w / 2, box_c_y + 98, "TERMINATED PROSPECTIVELY (No formal Stage C run)", 14, weight="bold", color=COLORS["ink"]))
    svg.append(svg_text(left_x + container_w / 2, box_c_y + 122, "W-RQ2 and W-RQ3 formal estimates unavailable within v0.1.5", 12, color=COLORS["muted"]))

    # Terminal stop bar at bottom of Stage C
    svg.append(svg_line(box_x + 80, box_c_y + box_c_h + 16, box_x + box_w - 80, box_c_y + box_c_h + 16, stroke=COLORS["terminal_stop"], stroke_width=4))
    svg.append(svg_text(left_x + container_w / 2, box_c_y + box_c_h + 36, "[ Closed Study Boundary — No Further Execution in v0.1.5 ]", 12, weight="bold", color=COLORS["terminal_stop"]))

    # Container 2: Western Semantic Follow-up v0.2 (Dashed Border)
    svg.append(svg_rect(right_x, top_y, container_w, container_h, fill=COLORS["container_b_bg"], stroke=COLORS["reuse_flow"], stroke_width=2, rx=8, stroke_dasharray="8,5"))
    svg.append(svg_text(right_x + container_w / 2, top_y + 32, "SEPARATE WESTERN SEMANTIC FOLLOW-UP v0.2", 17, weight="bold", color=COLORS["reuse_flow"]))
    svg.append(svg_text(right_x + container_w / 2, top_y + 54, "Independent Post-Study Evaluation · Reuses Frozen Answers", 13, color=COLORS["muted"]))

    # Follow-up Evaluator Box
    box_f_y = top_y + 75
    box_f_h = 120
    box_f_w = box_w
    box_f_x = right_x + (container_w - box_f_w) / 2
    svg.append(svg_rect(box_f_x, box_f_y, box_f_w, box_f_h, fill="#FFFFFF", stroke=COLORS["border"], stroke_width=1.5, rx=6))
    svg.append(svg_text(right_x + container_w / 2, box_f_y + 28, "Blinded Evidence-Grounded Semantic Evaluator", 15, weight="bold"))
    svg.append(svg_text(right_x + container_w / 2, box_f_y + 52, "Single evaluator: GPT-5.6 Sol · condition labels concealed during judging", 13, color=COLORS["muted"]))
    svg.append(svg_text(right_x + container_w / 2, box_f_y + 74, "Evaluated solely against frozen expected points & top-4 retrieved passages", 13, color=COLORS["muted"]))
    svg.append(svg_text(right_x + container_w / 2, box_f_y + 98, "Does not reopen or retroactively complete historical Stage C", 13, weight="bold", color=COLORS["reuse_flow"]))

    # REUSE FLOW: Clean orthogonal connector from Stage B to Follow-up Evaluator
    b_out_x = box_x + box_w
    b_out_y = box_b_y + box_h / 2
    f_in_x = box_f_x
    f_in_y = box_f_y + box_f_h / 2
    gap_mid_x = (b_out_x + f_in_x) / 2

    # Draw pathway: horizontal from B -> mid -> vertical -> horizontal into F
    svg.append(svg_line(b_out_x, b_out_y, gap_mid_x, b_out_y, stroke=COLORS["reuse_flow"], stroke_width=2.5, stroke_dasharray="6,4"))
    svg.append(svg_line(gap_mid_x, b_out_y, gap_mid_x, f_in_y, stroke=COLORS["reuse_flow"], stroke_width=2.5, stroke_dasharray="6,4"))
    svg.append(svg_line(gap_mid_x, f_in_y, f_in_x, f_in_y, stroke=COLORS["reuse_flow"], stroke_width=2.5, stroke_dasharray="6,4"))
    svg.append(f'<polygon points="{f_in_x - 8},{f_in_y - 6} {f_in_x - 8},{f_in_y + 6} {f_in_x},{f_in_y}" fill="{COLORS["reuse_flow"]}"/>')

    # Label box on horizontal bridge
    pill_w, pill_h = 110, 42
    pill_x = gap_mid_x - pill_w / 2
    pill_y = (b_out_y + f_in_y) / 2 - pill_h / 2
    svg.append(svg_rect(pill_x, pill_y, pill_w, pill_h, fill="#FFFFFF", stroke=COLORS["reuse_flow"], stroke_width=1.5, rx=6))
    svg.append(svg_text(gap_mid_x, pill_y + 17, "192 Frozen", 11, weight="bold", color=COLORS["reuse_flow"]))
    svg.append(svg_text(gap_mid_x, pill_y + 32, "Answers Reused", 11, weight="bold", color=COLORS["reuse_flow"]))

    # Arrow Evaluator -> Results Split
    svg.append(svg_line(right_x + container_w / 2, box_f_y + box_f_h, right_x + container_w / 2, box_f_y + box_f_h + 30, stroke=COLORS["accent_line"], stroke_width=2))

    # Split: W-RQ2 Box and W-RQ3 Box
    split_y = box_f_y + box_f_h + 30
    sub_w = 250
    sub_h = 250
    sub_gap = 30
    sub_x1 = right_x + (container_w - (sub_w * 2 + sub_gap)) / 2
    sub_x2 = sub_x1 + sub_w + sub_gap

    # Connecting branch
    svg.append(svg_line(sub_x1 + sub_w / 2, split_y, sub_x2 + sub_w / 2, split_y, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(svg_line(sub_x1 + sub_w / 2, split_y, sub_x1 + sub_w / 2, split_y + 15, stroke=COLORS["accent_line"], stroke_width=2))
    svg.append(svg_line(sub_x2 + sub_w / 2, split_y, sub_x2 + sub_w / 2, split_y + 15, stroke=COLORS["accent_line"], stroke_width=2))

    # W-RQ2 Box
    svg.append(svg_rect(sub_x1, split_y + 15, sub_w, sub_h, fill="#FFFFFF", stroke=COLORS["border"], stroke_width=1.5, rx=6))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 40, "W-RQ2: Answerable Cases", 14, weight="bold"))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 60, "42 cases × 4 = 168 cells", 12, color=COLORS["muted"]))
    svg.append(svg_line(sub_x1 + 15, split_y + 72, sub_x1 + sub_w - 15, split_y + 72, stroke=COLORS["grid"]))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 94, "Primary Endpoint:", 12, weight="bold", color=COLORS["ink"]))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 114, "Full evidence coverage score", 12, color=COLORS["ink"]))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 132, "(macro mean + bootstrap CIs)", 11, color=COLORS["muted"]))
    svg.append(svg_line(sub_x1 + 15, split_y + 144, sub_x1 + sub_w - 15, split_y + 144, stroke=COLORS["grid"]))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 166, "Secondary Endpoints:", 12, weight="bold", color=COLORS["ink"]))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 184, "Partial-credit coverage", 11, color=COLORS["muted"]))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 202, "Unsupported-claim presence", 11, color=COLORS["muted"]))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 220, "Contradiction presence", 11, color=COLORS["muted"]))
    svg.append(svg_text(sub_x1 + sub_w / 2, split_y + 242, "Exact McNemar tests vs R0", 11, weight="bold", color=COLORS["accent_point"]))

    # W-RQ3 Box
    svg.append(svg_rect(sub_x2, split_y + 15, sub_w, sub_h, fill="#FFFFFF", stroke=COLORS["border"], stroke_width=1.5, rx=6))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 40, "W-RQ3: Insufficient Cases", 14, weight="bold"))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 60, "6 cases × 4 = 24 cells", 12, color=COLORS["muted"]))
    svg.append(svg_line(sub_x2 + 15, split_y + 72, sub_x2 + sub_w - 15, split_y + 72, stroke=COLORS["grid"]))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 94, "Descriptive Handling Only:", 12, weight="bold", color=COLORS["ink"]))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 116, "4-Category Rubric:", 12, color=COLORS["ink"]))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 138, "1. Appropriate abstention", 11, color=COLORS["muted"]))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 158, "2. Bounded insufficiency", 11, color=COLORS["muted"]))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 178, "3. Substantive unack.", 11, color=COLORS["muted"]))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 198, "4. Overclaim beyond pilot", 11, color=COLORS["muted"]))
    svg.append(svg_line(sub_x2 + 15, split_y + 214, sub_x2 + sub_w - 15, split_y + 214, stroke=COLORS["grid"]))
    svg.append(svg_text(sub_x2 + sub_w / 2, split_y + 236, "No hypothesis testing (n = 6)", 11, weight="bold", color=COLORS["terminal_stop"]))

    # Footer note at bottom of Container B
    svg.append(svg_text(right_x + container_w / 2, top_y + container_h - 22, "Rubric-grounded textual evaluation · Not expert clinician validation · No causal claim", 11, color=COLORS["muted"]))

    svg.append("</svg>")
    out_svg.write_text("\n".join(svg) + "\n", encoding="utf-8")

    # PNG rendering with PIL (High-res export at 2800x1920)
    scale = 2
    img_w, img_h = width * scale, height * scale
    img = Image.new("RGB", (img_w, img_h), COLORS["background"])
    draw = ImageDraw.Draw(img)

    def p_rect(x, y, w, h, fill, outline, width=1, rx=0):
        draw.rounded_rectangle((x * scale, y * scale, (x + w) * scale, (y + h) * scale), radius=rx * scale, fill=fill, outline=outline, width=width * scale)

    def p_text(x, y, text, size, bold=False, color=COLORS["ink"], anchor="mm"):
        draw.text((x * scale, y * scale), text, font=get_font(size * scale, bold=bold), fill=color, anchor=anchor)

    def p_line(x1, y1, x2, y2, color, width=1):
        draw.line((x1 * scale, y1 * scale, x2 * scale, y2 * scale), fill=color, width=width * scale)

    p_text(width / 2, 40, "Figure 1: MediRAG Phase II Western Evidence Study Architecture", 24, bold=True)
    p_text(width / 2, 68, "Formal pilot evaluation sequence (v0.1.5) and separate post-study evidence-grounded semantic follow-up (v0.2)", 15, color=COLORS["muted"])

    # Header Corpus & Benchmark
    p_rect(corpus_x, corpus_y, corpus_w, corpus_h, fill="#FFFFFF", outline=COLORS["border"], width=2, rx=6)
    p_text(width / 2, corpus_y + 25, "Western Pilot Corpus", 16, bold=True)
    p_text(width / 2, corpus_y + 49, "16 PMC Open Access Systematic Reviews (4 Topic Domains)", 13, color=COLORS["muted"])
    p_text(width / 2, corpus_y + 71, "271 deterministic chunks · structured source provenance", 13, color=COLORS["muted"])

    # Arrow Corpus -> Benchmark
    p_line(width / 2, corpus_y + corpus_h, width / 2, corpus_y + corpus_h + 23, COLORS["accent_line"], width=2)
    draw.polygon([( (width/2 - 5)*scale, (corpus_y + corpus_h + 17)*scale ),
                  ( (width/2 + 5)*scale, (corpus_y + corpus_h + 17)*scale ),
                  ( (width/2)*scale, (corpus_y + corpus_h + 24)*scale )], fill=COLORS["accent_line"])

    p_rect(bench_x, bench_y, bench_w, bench_h, fill="#FFFFFF", outline=COLORS["border"], width=2, rx=6)
    p_text(width / 2, bench_y + 26, "Western Pilot Benchmark (48 Cases)", 16, bold=True)
    p_text(width / 2, bench_y + 50, "42 answerable cases (W-RQ1 & W-RQ2) · 6 insufficient-evidence cases (W-RQ3)", 13, color=COLORS["muted"])

    # Connector Benchmark -> Container A
    mid_bench_y = 290
    p_line(width / 2, bench_y + bench_h, width / 2, mid_bench_y, COLORS["accent_line"], width=2)
    p_line(width / 2, mid_bench_y, left_x + container_w / 2, mid_bench_y, COLORS["accent_line"], width=2)
    p_line(left_x + container_w / 2, mid_bench_y, left_x + container_w / 2, top_y, COLORS["accent_line"], width=2)
    draw.polygon([( (left_x + container_w/2 - 5)*scale, (top_y - 7)*scale ),
                  ( (left_x + container_w/2 + 5)*scale, (top_y - 7)*scale ),
                  ( (left_x + container_w/2)*scale, (top_y)*scale )], fill=COLORS["accent_line"])

    # Left container
    p_rect(left_x, top_y, container_w, container_h, fill=COLORS["container_a_bg"], outline=COLORS["ink"], width=2, rx=8)
    p_text(left_x + container_w / 2, top_y + 28, "WESTERN FORMAL STUDY v0.1.5", 17, bold=True)
    p_text(left_x + container_w / 2, top_y + 48, "Historically Closed Study · Defined Stopping Rule", 13, color=COLORS["muted"])

    # Internal arrow from header to Stage A
    p_line(left_x + container_w / 2, top_y + 54, left_x + container_w / 2, top_y + 75, COLORS["accent_line"], width=2)
    draw.polygon([( (left_x + container_w/2 - 5)*scale, (top_y + 68)*scale ),
                  ( (left_x + container_w/2 + 5)*scale, (top_y + 68)*scale ),
                  ( (left_x + container_w/2)*scale, (top_y + 75)*scale )], fill=COLORS["accent_line"])

    # Stage A
    p_rect(box_x, box_a_y, box_w, box_h, fill="#FFFFFF", outline=COLORS["border"], width=2, rx=6)
    p_text(left_x + container_w / 2, box_a_y + 26, "Stage A: Evidence Retrieval Experiment", 15, bold=True)
    p_text(left_x + container_w / 2, box_a_y + 48, "4 retrieval conditions (R0 lexical, R1 dense, R2 fusion, R3 rerank) × 48 cases", 13, color=COLORS["muted"])
    p_text(left_x + container_w / 2, box_a_y + 68, "192/192 retrieval cells completed · 0 technical missingness", 13, color=COLORS["muted"])
    p_text(left_x + container_w / 2, box_a_y + 88, "W-RQ1 estimable: headline recall, Hit@4, and MRR (n = 42)", 12, bold=True, color=COLORS["ink"])

    # Arrow A -> B
    p_line(left_x + container_w / 2, box_a_y + box_h, left_x + container_w / 2, box_a_y + box_h + 30, COLORS["accent_line"], width=2)
    draw.polygon([( (left_x + container_w/2 - 5)*scale, (box_a_y + box_h + 25)*scale ),
                  ( (left_x + container_w/2 + 5)*scale, (box_a_y + box_h + 25)*scale ),
                  ( (left_x + container_w/2)*scale, (box_a_y + box_h + 32)*scale )], fill=COLORS["accent_line"])

    # Stage B
    p_rect(box_x, box_b_y, box_w, box_h, fill="#FFFFFF", outline=COLORS["border"], width=2, rx=6)
    p_text(left_x + container_w / 2, box_b_y + 26, "Stage B: Controlled Answer Generation", 15, bold=True)
    p_text(left_x + container_w / 2, box_b_y + 48, "Fixed Qwen/Qwen3-8B generator (temp 0, max 256 tokens)", 13, color=COLORS["muted"])
    p_text(left_x + container_w / 2, box_b_y + 68, "192 primary answers completed · frozen dataset preserved", 13, color=COLORS["muted"])
    p_text(left_x + container_w / 2, box_b_y + 88, "Supplies generated text; does not estimate semantic quality by itself", 12, color=COLORS["muted"])

    # Arrow B -> Stage C
    p_line(left_x + container_w / 2, box_b_y + box_h, left_x + container_w / 2, box_b_y + box_h + 30, COLORS["accent_line"], width=2)
    draw.polygon([( (left_x + container_w/2 - 5)*scale, (box_b_y + box_h + 25)*scale ),
                  ( (left_x + container_w/2 + 5)*scale, (box_b_y + box_h + 25)*scale ),
                  ( (left_x + container_w/2)*scale, (box_b_y + box_h + 32)*scale )], fill=COLORS["accent_line"])

    # Stage C
    p_rect(box_x, box_c_y, box_w, box_c_h, fill="#FFFFFF", outline=COLORS["terminal_stop"], width=2, rx=6)
    p_text(left_x + container_w / 2, box_c_y + 28, "Automated Stage C: Evaluator Qualification", 15, bold=True, color=COLORS["terminal_stop"])
    p_text(left_x + container_w / 2, box_c_y + 52, "Prospective qualification protocol (Wave 1 & Wave 2)", 13, color=COLORS["muted"])
    p_text(left_x + container_w / 2, box_c_y + 74, "Reached stopping rule: zero Primary Judges qualified", 13, color=COLORS["muted"])
    p_text(left_x + container_w / 2, box_c_y + 98, "TERMINATED PROSPECTIVELY (No formal Stage C run)", 14, bold=True, color=COLORS["ink"])
    p_text(left_x + container_w / 2, box_c_y + 120, "W-RQ2 and W-RQ3 formal estimates unavailable within v0.1.5", 12, color=COLORS["muted"])

    p_line(box_x + 80, box_c_y + box_c_h + 15, box_x + box_w - 80, box_c_y + box_c_h + 15, COLORS["terminal_stop"], width=4)
    p_text(left_x + container_w / 2, box_c_y + box_c_h + 34, "[ Closed Study Boundary — No Further Execution in v0.1.5 ]", 12, bold=True, color=COLORS["terminal_stop"])

    # Right container
    p_rect(right_x, top_y, container_w, container_h, fill=COLORS["container_b_bg"], outline=COLORS["reuse_flow"], width=2, rx=8)
    p_text(right_x + container_w / 2, top_y + 32, "SEPARATE WESTERN SEMANTIC FOLLOW-UP v0.2", 17, bold=True, color=COLORS["reuse_flow"])
    p_text(right_x + container_w / 2, top_y + 54, "Independent Post-Study Evaluation · Reuses Frozen Answers", 13, color=COLORS["muted"])

    # Evaluator box
    p_rect(right_x + (container_w - box_w) / 2, box_f_y, box_w, box_f_h, fill="#FFFFFF", outline=COLORS["border"], width=2, rx=6)
    p_text(right_x + container_w / 2, box_f_y + 26, "Blinded Evidence-Grounded Semantic Evaluator", 15, bold=True)
    p_text(right_x + container_w / 2, box_f_y + 48, "Single evaluator: GPT-5.6 Sol · condition labels concealed during judging", 13, color=COLORS["muted"])
    p_text(right_x + container_w / 2, box_f_y + 68, "Evaluated solely against frozen expected points & top-4 retrieved passages", 13, color=COLORS["muted"])
    p_text(right_x + container_w / 2, box_f_y + 92, "Does not reopen or retroactively complete historical Stage C", 13, bold=True, color=COLORS["reuse_flow"])

    # Flow arrow between containers (orthogonal bridge from Stage B to Evaluator)
    gap_mid_x = (b_out_x + f_in_x) / 2
    p_line(b_out_x, b_out_y, gap_mid_x, b_out_y, COLORS["reuse_flow"], width=2)
    p_line(gap_mid_x, b_out_y, gap_mid_x, f_in_y, COLORS["reuse_flow"], width=2)
    p_line(gap_mid_x, f_in_y, f_in_x, f_in_y, COLORS["reuse_flow"], width=2)
    draw.polygon([( (f_in_x - 8)*scale, (f_in_y - 6)*scale ),
                  ( (f_in_x - 8)*scale, (f_in_y + 6)*scale ),
                  ( f_in_x*scale, f_in_y*scale )], fill=COLORS["reuse_flow"])

    pill_w, pill_h = 110, 42
    pill_x = gap_mid_x - pill_w / 2
    pill_y = (b_out_y + f_in_y) / 2 - pill_h / 2
    p_rect(pill_x, pill_y, pill_w, pill_h, fill="#FFFFFF", outline=COLORS["reuse_flow"], width=2, rx=6)
    p_text(gap_mid_x, pill_y + 15, "192 Frozen", 11, bold=True, color=COLORS["reuse_flow"])
    p_text(gap_mid_x, pill_y + 29, "Answers Reused", 11, bold=True, color=COLORS["reuse_flow"])

    p_line(right_x + container_w / 2, box_f_y + box_f_h, right_x + container_w / 2, box_f_y + box_f_h + 30, COLORS["accent_line"], width=2)
    p_line(sub_x1 + sub_w / 2, split_y, sub_x2 + sub_w / 2, split_y, COLORS["accent_line"], width=2)
    p_line(sub_x1 + sub_w / 2, split_y, sub_x1 + sub_w / 2, split_y + 15, COLORS["accent_line"], width=2)
    p_line(sub_x2 + sub_w / 2, split_y, sub_x2 + sub_w / 2, split_y + 15, COLORS["accent_line"], width=2)

    # Sub-boxes
    p_rect(sub_x1, split_y + 15, sub_w, sub_h, fill="#FFFFFF", outline=COLORS["border"], width=2, rx=6)
    p_text(sub_x1 + sub_w / 2, split_y + 40, "W-RQ2: Answerable Cases", 14, bold=True)
    p_text(sub_x1 + sub_w / 2, split_y + 60, "42 cases × 4 = 168 cells", 12, color=COLORS["muted"])
    p_line(sub_x1 + 15, split_y + 72, sub_x1 + sub_w - 15, split_y + 72, COLORS["grid"])
    p_text(sub_x1 + sub_w / 2, split_y + 92, "Primary Endpoint:", 12, bold=True, color=COLORS["ink"])
    p_text(sub_x1 + sub_w / 2, split_y + 110, "Full evidence coverage score", 12, color=COLORS["ink"])
    p_text(sub_x1 + sub_w / 2, split_y + 128, "(macro mean + bootstrap CIs)", 11, color=COLORS["muted"])
    p_line(sub_x1 + 15, split_y + 140, sub_x1 + sub_w - 15, split_y + 140, COLORS["grid"])
    p_text(sub_x1 + sub_w / 2, split_y + 160, "Secondary Endpoints:", 12, bold=True, color=COLORS["ink"])
    p_text(sub_x1 + sub_w / 2, split_y + 178, "Partial-credit coverage", 11, color=COLORS["muted"])
    p_text(sub_x1 + sub_w / 2, split_y + 196, "Unsupported-claim presence", 11, color=COLORS["muted"])
    p_text(sub_x1 + sub_w / 2, split_y + 214, "Contradiction presence", 11, color=COLORS["muted"])
    p_text(sub_x1 + sub_w / 2, split_y + 236, "Exact McNemar tests vs R0", 11, bold=True, color=COLORS["accent_point"])

    p_rect(sub_x2, split_y + 15, sub_w, sub_h, fill="#FFFFFF", outline=COLORS["border"], width=2, rx=6)
    p_text(sub_x2 + sub_w / 2, split_y + 40, "W-RQ3: Insufficient Cases", 14, bold=True)
    p_text(sub_x2 + sub_w / 2, split_y + 60, "6 cases × 4 = 24 cells", 12, color=COLORS["muted"])
    p_line(sub_x2 + 15, split_y + 72, sub_x2 + sub_w - 15, split_y + 72, COLORS["grid"])
    p_text(sub_x2 + sub_w / 2, split_y + 92, "Descriptive Handling Only:", 12, bold=True, color=COLORS["ink"])
    p_text(sub_x2 + sub_w / 2, split_y + 114, "4-Category Rubric:", 12, color=COLORS["ink"])
    p_text(sub_x2 + sub_w / 2, split_y + 136, "1. Appropriate abstention", 11, color=COLORS["muted"])
    p_text(sub_x2 + sub_w / 2, split_y + 156, "2. Bounded insufficiency", 11, color=COLORS["muted"])
    p_text(sub_x2 + sub_w / 2, split_y + 176, "3. Substantive unack.", 11, color=COLORS["muted"])
    p_text(sub_x2 + sub_w / 2, split_y + 196, "4. Overclaim beyond pilot", 11, color=COLORS["muted"])
    p_line(sub_x2 + 15, split_y + 210, sub_x2 + sub_w - 15, split_y + 210, COLORS["grid"])
    p_text(sub_x2 + sub_w / 2, split_y + 232, "No hypothesis testing (n = 6)", 11, bold=True, color=COLORS["terminal_stop"])

    p_text(right_x + container_w / 2, top_y + container_h - 22, "Rubric-grounded textual evaluation · Not expert clinician validation · No causal claim", 11, color=COLORS["muted"])

    img.save(out_png, format="PNG", dpi=(300, 300), optimize=True)


# --- Figure 2: Stage-A Forest Plot ---

def render_figure_2(rows: list[dict[str, str]], out_svg: Path, out_png: Path) -> None:
    width, height = 1200, 560
    left, right, top, bottom = 220, 320, 110, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    x_min, x_max = -0.05, 0.40

    def sx(val: float) -> float:
        return left + (val - x_min) / (x_max - x_min) * plot_w

    # SVG
    svg = svg_header(width, height)
    svg.append(svg_text(width / 2, 42, "Figure 2: Stage-A Paired Primary-Gold Chunk-Recall Differences", 22, weight="bold"))
    svg.append(svg_text(width / 2, 72, "Western Formal Study v0.1.5; Comparison minus R0; n = 42 paired cases; 95% bootstrap CIs", 15, color=COLORS["muted"]))

    # Grid ticks
    for val in [-0.05, 0.0, 0.1, 0.2, 0.3, 0.4]:
        x = sx(val)
        svg.append(svg_line(x, top, x, top + plot_h, stroke=COLORS["grid"], stroke_width=1))
        svg.append(svg_text(x, top + plot_h + 28, f"{val:+.2f}" if val != 0 else "0.00", 14, color=COLORS["muted"]))

    # Zero reference line
    zero_x = sx(0.0)
    svg.append(svg_line(zero_x, top, zero_x, top + plot_h, stroke=COLORS["ink"], stroke_width=2))

    # Data rows
    row_gap = plot_h / len(rows)
    for i, r in enumerate(rows):
        y = top + row_gap * (i + 0.5)
        comp = r["comparison"]
        mean = float(r["mean_chunk_recall_difference"])
        low = float(r["bootstrap_ci_lower_95"])
        high = float(r["bootstrap_ci_upper_95"])

        # Label left
        svg.append(svg_text(left - 24, y + 6, comp, 17, anchor="end", weight="bold"))

        # CI line and end caps
        svg.append(svg_line(sx(low), y, sx(high), y, stroke=COLORS["accent_point"], stroke_width=4))
        svg.append(svg_line(sx(low), y - 10, sx(low), y + 10, stroke=COLORS["accent_point"], stroke_width=3))
        svg.append(svg_line(sx(high), y - 10, sx(high), y + 10, stroke=COLORS["accent_point"], stroke_width=3))

        # Point estimate
        svg.append(f'<circle cx="{sx(mean):.2f}" cy="{y:.2f}" r="8" fill="{COLORS["accent_point"]}" stroke="#FFFFFF" stroke-width="2"/>')

        # Numeric text right
        stat_text = f"{mean:+.3f}  [95% CI: {low:+.3f}, {high:+.3f}]"
        svg.append(svg_text(left + plot_w + 24, y + 6, stat_text, 15, anchor="start", weight="bold", color=COLORS["ink"]))

    # Axis label
    svg.append(svg_text(left + plot_w / 2, height - 25, "Paired difference in primary-gold chunk recall (vs R0)", 15, weight="bold"))
    svg.append("</svg>")
    out_svg.write_text("\n".join(svg) + "\n", encoding="utf-8")

    # PNG (High-res 2400x1120)
    scale = 2
    img = Image.new("RGB", (width * scale, height * scale), COLORS["background"])
    draw = ImageDraw.Draw(img)

    def p_line(x1, y1, x2, y2, color, width=1):
        draw.line((x1 * scale, y1 * scale, x2 * scale, y2 * scale), fill=color, width=width * scale)

    def p_text(x, y, text, size, bold=False, color=COLORS["ink"], anchor="mm"):
        draw.text((x * scale, y * scale), text, font=get_font(size * scale, bold=bold), fill=color, anchor=anchor)

    p_text(width / 2, 42, "Figure 2: Stage-A Paired Primary-Gold Chunk-Recall Differences", 22, bold=True)
    p_text(width / 2, 72, "Western Formal Study v0.1.5; Comparison minus R0; n = 42 paired cases; 95% bootstrap CIs", 15, color=COLORS["muted"])

    for val in [-0.05, 0.0, 0.1, 0.2, 0.3, 0.4]:
        x = sx(val)
        p_line(x, top, x, top + plot_h, COLORS["grid"], width=1)
        p_text(x, top + plot_h + 28, f"{val:+.2f}" if val != 0 else "0.00", 14, color=COLORS["muted"])

    p_line(zero_x, top, zero_x, top + plot_h, COLORS["ink"], width=2)

    for i, r in enumerate(rows):
        y = top + row_gap * (i + 0.5)
        comp = r["comparison"]
        mean = float(r["mean_chunk_recall_difference"])
        low = float(r["bootstrap_ci_lower_95"])
        high = float(r["bootstrap_ci_upper_95"])

        p_text(left - 24, y, comp, 17, bold=True, anchor="rm")
        p_line(sx(low), y, sx(high), y, COLORS["accent_point"], width=4)
        p_line(sx(low), y - 10, sx(low), y + 10, COLORS["accent_point"], width=3)
        p_line(sx(high), y - 10, sx(high), y + 10, COLORS["accent_point"], width=3)

        # Marker circle
        r_px = 8 * scale
        cx = sx(mean) * scale
        cy = y * scale
        draw.ellipse((cx - r_px, cy - r_px, cx + r_px, cy + r_px), fill=COLORS["accent_point"], outline="#FFFFFF", width=2 * scale)

        stat_text = f"{mean:+.3f}  [95% CI: {low:+.3f}, {high:+.3f}]"
        p_text(left + plot_w + 24, y, stat_text, 15, bold=True, anchor="lm")

    p_text(left + plot_w / 2, height - 25, "Paired difference in primary-gold chunk recall (vs R0)", 15, bold=True)
    img.save(out_png, format="PNG", dpi=(300, 300), optimize=True)


# --- Figure 3: Follow-Up Forest Plot ---

def render_figure_3(rows: list[dict[str, str]], out_svg: Path, out_png: Path) -> None:
    width, height = 1200, 560
    left, right, top, bottom = 220, 320, 110, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    x_min, x_max = -0.05, 0.45

    def sx(val: float) -> float:
        return left + (val - x_min) / (x_max - x_min) * plot_w

    # SVG
    svg = svg_header(width, height)
    svg.append(svg_text(width / 2, 42, "Figure 3: Semantic Follow-Up Paired Full-Coverage Differences", 22, weight="bold"))
    svg.append(svg_text(width / 2, 72, "Separate Western Semantic Follow-up v0.2; Comparison minus R0; n = 42 answerable cases; 95% bootstrap CIs", 15, color=COLORS["muted"]))

    # Grid ticks
    for val in [-0.05, 0.0, 0.1, 0.2, 0.3, 0.4]:
        x = sx(val)
        svg.append(svg_line(x, top, x, top + plot_h, stroke=COLORS["grid"], stroke_width=1))
        svg.append(svg_text(x, top + plot_h + 28, f"{val:+.2f}" if val != 0 else "0.00", 14, color=COLORS["muted"]))

    # Zero reference line
    zero_x = sx(0.0)
    svg.append(svg_line(zero_x, top, zero_x, top + plot_h, stroke=COLORS["ink"], stroke_width=2))

    # Data rows
    row_gap = plot_h / len(rows)
    for i, r in enumerate(rows):
        y = top + row_gap * (i + 0.5)
        comp = r["comparison"]
        mean = float(r["mean_difference"])
        low = float(r["bootstrap_ci_95_low"])
        high = float(r["bootstrap_ci_95_high"])

        # Label left
        svg.append(svg_text(left - 24, y + 6, comp, 17, anchor="end", weight="bold"))

        # CI line and end caps
        svg.append(svg_line(sx(low), y, sx(high), y, stroke=COLORS["accent_point"], stroke_width=4))
        svg.append(svg_line(sx(low), y - 10, sx(low), y + 10, stroke=COLORS["accent_point"], stroke_width=3))
        svg.append(svg_line(sx(high), y - 10, sx(high), y + 10, stroke=COLORS["accent_point"], stroke_width=3))

        # Point estimate
        svg.append(f'<circle cx="{sx(mean):.2f}" cy="{y:.2f}" r="8" fill="{COLORS["accent_point"]}" stroke="#FFFFFF" stroke-width="2"/>')

        # Numeric text right
        stat_text = f"{mean:+.3f}  [95% CI: {low:+.3f}, {high:+.3f}]"
        svg.append(svg_text(left + plot_w + 24, y + 6, stat_text, 15, anchor="start", weight="bold", color=COLORS["ink"]))

    # Axis label
    svg.append(svg_text(left + plot_w / 2, height - 25, "Paired difference in full-coverage score (vs R0)", 15, weight="bold"))
    svg.append("</svg>")
    out_svg.write_text("\n".join(svg) + "\n", encoding="utf-8")

    # PNG (High-res 2400x1120)
    scale = 2
    img = Image.new("RGB", (width * scale, height * scale), COLORS["background"])
    draw = ImageDraw.Draw(img)

    def p_line(x1, y1, x2, y2, color, width=1):
        draw.line((x1 * scale, y1 * scale, x2 * scale, y2 * scale), fill=color, width=width * scale)

    def p_text(x, y, text, size, bold=False, color=COLORS["ink"], anchor="mm"):
        draw.text((x * scale, y * scale), text, font=get_font(size * scale, bold=bold), fill=color, anchor=anchor)

    p_text(width / 2, 42, "Figure 3: Semantic Follow-Up Paired Full-Coverage Differences", 22, bold=True)
    p_text(width / 2, 72, "Separate Western Semantic Follow-up v0.2; Comparison minus R0; n = 42 answerable cases; 95% bootstrap CIs", 15, color=COLORS["muted"])

    for val in [-0.05, 0.0, 0.1, 0.2, 0.3, 0.4]:
        x = sx(val)
        p_line(x, top, x, top + plot_h, COLORS["grid"], width=1)
        p_text(x, top + plot_h + 28, f"{val:+.2f}" if val != 0 else "0.00", 14, color=COLORS["muted"])

    p_line(zero_x, top, zero_x, top + plot_h, COLORS["ink"], width=2)

    for i, r in enumerate(rows):
        y = top + row_gap * (i + 0.5)
        comp = r["comparison"]
        mean = float(r["mean_difference"])
        low = float(r["bootstrap_ci_95_low"])
        high = float(r["bootstrap_ci_95_high"])

        p_text(left - 24, y, comp, 17, bold=True, anchor="rm")
        p_line(sx(low), y, sx(high), y, COLORS["accent_point"], width=4)
        p_line(sx(low), y - 10, sx(low), y + 10, COLORS["accent_point"], width=3)
        p_line(sx(high), y - 10, sx(high), y + 10, COLORS["accent_point"], width=3)

        r_px = 8 * scale
        cx = sx(mean) * scale
        cy = y * scale
        draw.ellipse((cx - r_px, cy - r_px, cx + r_px, cy + r_px), fill=COLORS["accent_point"], outline="#FFFFFF", width=2 * scale)

        stat_text = f"{mean:+.3f}  [95% CI: {low:+.3f}, {high:+.3f}]"
        p_text(left + plot_w + 24, y, stat_text, 15, bold=True, anchor="lm")

    p_text(left + plot_w / 2, height - 25, "Paired difference in full-coverage score (vs R0)", 15, bold=True)
    img.save(out_png, format="PNG", dpi=(300, 300), optimize=True)


# --- Table Generators ---

def render_table_1(rows: list[dict[str, str]], out_md: Path, out_csv: Path) -> None:
    # CSV
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Condition", "n", "Primary Gold Chunk Recall@4", "Primary Source Recall@4", "Hit@4", "MRR"])
        for r in rows:
            writer.writerow([
                r["condition"],
                r["n_cases"],
                f"{float(r['primary_gold_chunk_recall_at_4']):.6f}",
                f"{float(r['primary_source_recall_at_4']):.6f}",
                f"{float(r['hit_at_4']):.6f}",
                f"{float(r['mrr']):.6f}",
            ])

    # Markdown
    md = [
        "# Table 1: Stage-A Headline Retrieval Metrics",
        "",
        "| Condition | n | Chunk Recall@4 | Source Recall@4 | Hit@4 | MRR |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        md.append(
            f"| {r['condition']} | {r['n_cases']} | "
            f"{float(r['primary_gold_chunk_recall_at_4']):.6f} | "
            f"{float(r['primary_source_recall_at_4']):.6f} | "
            f"{float(r['hit_at_4']):.6f} | "
            f"{float(r['mrr']):.6f} |"
        )
    md.extend([
        "",
        "**Note:** Frozen Western Formal Study v0.1.5. Headline retrieval denominator is 42 supported or partially supported cases with non-empty primary gold evidence. Six insufficient-evidence cases were excluded from the headline retrieval denominator and not imputed as failures. All conditions evaluated at top-4 retrieval depth. Recalls represent micro-aggregates across primary-gold items.",
    ])
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")


def render_table_2(rows: list[dict[str, str]], out_md: Path, out_csv: Path) -> None:
    # CSV
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Condition", "n", "Mean Full-Coverage Score", "SD", "Median", "Min", "Max"])
        for r in rows:
            writer.writerow([
                r["retrieval_condition"],
                r["n"],
                f"{float(r['mean']):.6f}",
                f"{float(r['sd']):.6f}",
                f"{float(r['median']):.3f}",
                f"{float(r['min']):.1f}",
                f"{float(r['max']):.1f}",
            ])

    # Markdown
    md = [
        "# Table 2: Semantic Evidence Full Coverage by Retrieval Condition",
        "",
        "| Condition | n | Mean Full-Coverage Score | SD | Median | Min | Max |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md.append(
            f"| {r['retrieval_condition']} | {r['n']} | "
            f"{float(r['mean']):.6f} | "
            f"{float(r['sd']):.6f} | "
            f"{float(r['median']):.3f} | "
            f"{float(r['min']):.1f} | "
            f"{float(r['max']):.1f} |"
        )
    md.extend([
        "",
        "**Note:** Separate Western Semantic Follow-up v0.2. Evaluates 42 answerable benchmark cases per retrieval condition using fixed Qwen/Qwen3-8B answers. Full-coverage score is the primary semantic endpoint (macro mean of `n_fully_covered / n_expected_points` judged against frozen expected points). Evaluated by a single GPT-5.6 Sol evidence-grounded evaluator with condition identity concealed. Does not represent clinical validation or patient safety.",
    ])
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")


def render_table_3(presence: list[dict[str, str]], contradictions: list[dict[str, str]], mcnemar: list[dict[str, str]], out_md: Path, out_csv: Path) -> None:
    contra_map = {r["retrieval_condition"]: r for r in contradictions}

    # CSV
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Panel A: Condition-Level Rates"])
        writer.writerow(["Condition", "n", "Unsupported-Claim Present", "Unsupported Rate", "Contradiction Present", "Contradiction Rate", "Contradicted Points Total"])
        for p in presence:
            cond = p["retrieval_condition"]
            c = contra_map[cond]
            writer.writerow([
                cond,
                p["n"],
                f"{p['true_count']}/42",
                f"{float(p['rate']):.6f}",
                f"{c['true_count']}/42",
                f"{float(c['rate']):.6f}",
                c["total_n_contradicted"],
            ])
        writer.writerow([])
        writer.writerow(["Panel B: Paired McNemar Tests for Unsupported-Claim Presence vs R0"])
        writer.writerow(["Comparison", "R0 Presence / Comparison Absence", "R0 Absence / Comparison Presence", "Discordant Pairs", "Exact Two-Sided McNemar p", "Holm-Adjusted p", "Holm Family Size"])
        for m in mcnemar:
            writer.writerow([
                m["comparison"],
                m["r0_true_comparison_false"],
                m["r0_false_comparison_true"],
                m["discordant_total"],
                f"{float(m['exact_two_sided_mcnemar_p_raw']):.6f}",
                f"{float(m['holm_adjusted_p']):.6f}",
                m["holm_family_size"],
            ])

    # Markdown
    md = [
        "# Table 3: Unsupported-Claim Presence and Contradiction Behavior",
        "",
        "### Panel A: Condition-Level Rates (n = 42 cases per condition)",
        "",
        "| Condition | Unsupported-Claim Present | Rate | Contradiction Present | Rate | Contradicted Points Total |",
        "|---|---|---|---|---|---|",
    ]
    for p in presence:
        cond = p["retrieval_condition"]
        c = contra_map[cond]
        md.append(
            f"| {cond} | {p['true_count']}/42 | {float(p['rate']):.4f} | "
            f"{c['true_count']}/42 | {float(c['rate']):.4f} | {c['total_n_contradicted']} |"
        )
    md.extend([
        "",
        "### Panel B: Paired Comparisons for Unsupported-Claim Presence versus R0",
        "",
        "| Comparison | R0 Present / Comp Absent | R0 Absent / Comp Present | Discordant Pairs | Exact McNemar p | Holm-Adjusted p |",
        "|---|---|---|---|---|---|",
    ])
    for m in mcnemar:
        md.append(
            f"| {m['comparison']} | {m['r0_true_comparison_false']} | {m['r0_false_comparison_true']} | "
            f"{m['discordant_total']} | {float(m['exact_two_sided_mcnemar_p_raw']):.6f} | {float(m['holm_adjusted_p']):.6f} |"
        )
    md.extend([
        "",
        "**Note:** Secondary outcomes in Western Semantic Follow-up v0.2 across 42 answerable cases. Panel A reports case-level indicator presence (at least one unsupported claim or contradiction in the generated answer). Panel B reports exact two-sided binomial tests on paired discordant presence indicators across the three prespecified R0 comparisons (family size = 3, Holm-Bonferroni adjustment). Unsupported-claim and contradiction annotations are rubric-grounded evaluations against supplied evidence excerpts and do not constitute validated clinical safety or factuality metrics.",
    ])
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")


def render_table_s1(stage_a_pairwise: list[dict[str, str]], out_md: Path, out_csv: Path) -> None:
    # CSV (copy direct contents with standard format)
    shutil.copy2(STAGE_A_TABLES / "stage_a_pairwise_vs_r0.csv", out_csv)

    # Markdown
    md = [
        "# Table S1: Complete Stage-A Paired Retrieval Statistics",
        "",
        "| Comparison | Paired n | Mean Recall Diff | 95% Bootstrap CI | R0 Hit / Comp Miss | R0 Miss / Comp Hit | Discordant Pairs | Exact McNemar p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in stage_a_pairwise:
        md.append(
            f"| {r['comparison']} | {r['n_paired_cases']} | {float(r['mean_chunk_recall_difference']):.6f} | "
            f"[{float(r['bootstrap_ci_lower_95']):.6f}, {float(r['bootstrap_ci_upper_95']):.6f}] | "
            f"{r['r0_hit_comparison_miss']} | {r['r0_miss_comparison_hit']} | {r['discordant_pairs']} | "
            f"{float(r['mcnemar_p_exact_two_sided']):.6f} |"
        )
    md.extend([
        "",
        "**Note:** Western Formal Study v0.1.5. Headline retrieval paired comparisons across 42 answerable cases. Chunk recall differences evaluate micro-aggregated primary gold items. Confidence intervals are 95% percentile intervals from 10,000 paired case bootstrap resamples (seed 20260815). McNemar p-values evaluate paired Hit@4 discordance using an exact two-sided binomial test. No multiplicity adjustment was prespecified in Stage A.",
    ])
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")


def render_table_s2(out_md: Path, out_csv: Path) -> None:
    part_desc = read_csv(STAGE_C2_TABLES / "w_rq2_partial_credit_by_condition.csv")
    part_pair = read_csv(STAGE_C2_TABLES / "w_rq2_partial_credit_pairwise_vs_r0.csv")
    unsupp_desc = read_csv(STAGE_C2_TABLES / "w_rq2_unsupported_count_by_condition.csv")
    unsupp_pair = read_csv(STAGE_C2_TABLES / "w_rq2_unsupported_count_pairwise_vs_r0.csv")
    points = read_csv(STAGE_C2_TABLES / "w_rq2_expected_point_labels_by_condition.csv")

    # CSV
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Panel A1: Partial-Credit Coverage by Condition"])
        writer.writerow(["Condition", "n", "Mean", "SD", "Median", "Min", "Max"])
        for r in part_desc:
            writer.writerow([r["retrieval_condition"], r["n"], f"{float(r['mean']):.6f}", f"{float(r['sd']):.6f}", r["median"], r["min"], r["max"]])
        writer.writerow([])
        writer.writerow(["Panel A2: Paired Partial-Credit Differences vs R0"])
        writer.writerow(["Comparison", "n", "Mean Difference", "Median Difference", "95% Bootstrap CI Lower", "95% Bootstrap CI Upper"])
        for r in part_pair:
            writer.writerow([r["comparison"], r["n"], f"{float(r['mean_difference']):.6f}", r["median_difference"], f"{float(r['bootstrap_ci_95_low']):.6f}", f"{float(r['bootstrap_ci_95_high']):.6f}"])
        writer.writerow([])
        writer.writerow(["Panel B1: Unsupported-Claim Counts by Condition"])
        writer.writerow(["Condition", "n", "Mean", "SD", "Median", "Min", "Max"])
        for r in unsupp_desc:
            writer.writerow([r["retrieval_condition"], r["n"], f"{float(r['mean']):.6f}", f"{float(r['sd']):.6f}", r["median"], r["min"], r["max"]])
        writer.writerow([])
        writer.writerow(["Panel B2: Paired Unsupported-Count Differences vs R0"])
        writer.writerow(["Comparison", "n", "Mean Difference", "95% Bootstrap CI Lower", "95% Bootstrap CI Upper"])
        for r in unsupp_pair:
            writer.writerow([r["comparison"], r["n"], f"{float(r['mean_difference']):.6f}", f"{float(r['bootstrap_ci_95_low']):.6f}", f"{float(r['bootstrap_ci_95_high']):.6f}"])
        writer.writerow([])
        writer.writerow(["Panel C: Expected Evidence-Point Label Totals"])
        writer.writerow(["Condition", "Covered", "Partially Covered", "Not Covered", "Contradicted", "Total Expected Points", "n Cases"])
        for r in points:
            writer.writerow([r["retrieval_condition"], r["covered"], r["partially_covered"], r["not_covered"], r["contradicted"], r["total_expected_points"], r["n_cases"]])

    # Markdown
    md = [
        "# Table S2: Detailed W-RQ2 Secondary Semantic Outcomes",
        "",
        "### Panel A: Partial-Credit Coverage",
        "",
        "| Condition | n | Mean | SD | Median | Min | Max |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in part_desc:
        md.append(f"| {r['retrieval_condition']} | {r['n']} | {float(r['mean']):.6f} | {float(r['sd']):.6f} | {r['median']} | {r['min']} | {r['max']} |")
    md.extend([
        "",
        "| Paired Comparison | n | Mean Diff | 95% Bootstrap CI |",
        "|---|---|---|---|",
    ])
    for r in part_pair:
        md.append(f"| {r['comparison']} | {r['n']} | {float(r['mean_difference']):.6f} | [{float(r['bootstrap_ci_95_low']):.6f}, {float(r['bootstrap_ci_95_high']):.6f}] |")

    md.extend([
        "",
        "### Panel B: Unsupported-Claim Counts",
        "",
        "| Condition | n | Mean Count | SD | Median | Min | Max |",
        "|---|---|---|---|---|---|---|",
    ])
    for r in unsupp_desc:
        md.append(f"| {r['retrieval_condition']} | {r['n']} | {float(r['mean']):.6f} | {float(r['sd']):.6f} | {r['median']} | {r['min']} | {r['max']} |")
    md.extend([
        "",
        "| Paired Comparison | n | Mean Diff | 95% Bootstrap CI |",
        "|---|---|---|---|",
    ])
    for r in unsupp_pair:
        md.append(f"| {r['comparison']} | {r['n']} | {float(r['mean_difference']):.6f} | [{float(r['bootstrap_ci_95_low']):.6f}, {float(r['bootstrap_ci_95_high']):.6f}] |")

    md.extend([
        "",
        "### Panel C: Expected Evidence-Point Label Totals",
        "",
        "| Condition | Covered | Partially Covered | Not Covered | Contradicted | Total Points | n Cases |",
        "|---|---|---|---|---|---|---|",
    ])
    for r in points:
        md.append(f"| {r['retrieval_condition']} | {r['covered']} | {r['partially_covered']} | {r['not_covered']} | {r['contradicted']} | {r['total_expected_points']} | {r['n_cases']} |")

    md.extend([
        "",
        "**Note:** Western Semantic Follow-up v0.2 secondary outcomes. 42 answerable cases per condition. Bootstrap resamples = 10,000, seed = 20260815. In Panel C, individual expected points are nested within benchmark cases and do not represent independent inferential units.",
    ])
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")


def render_table_s3(dist: list[dict[str, str]], cases: list[dict[str, str]], out_md: Path, out_csv: Path) -> None:
    # CSV
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Panel A: Categorical Distribution by Retrieval Condition (n = 6 cases per condition)"])
        writer.writerow(["Condition", "n", "Appropriate Abstention", "Appropriate Bounded Insufficiency", "Substantive w/o Acknowledgment", "Overclaim Beyond Pilot"])
        for r in dist:
            writer.writerow([
                r["retrieval_condition"],
                r["n"],
                f"{r['appropriate_abstention']} ({float(r['appropriate_abstention_proportion'])*100:.1f}%)",
                f"{r['appropriate_bounded_insufficiency']} ({float(r['appropriate_bounded_insufficiency_proportion'])*100:.1f}%)",
                f"{r['substantive_answer_without_insufficiency_acknowledgement']} ({float(r['substantive_answer_without_insufficiency_acknowledgement_proportion'])*100:.1f}%)",
                f"{r['overclaim_beyond_pilot_evidence']} ({float(r['overclaim_beyond_pilot_evidence_proportion'])*100:.1f}%)",
            ])
        writer.writerow([])
        writer.writerow(["Panel B: Case-Level Audit Labels (all 24 condition-case pairs)"])
        writer.writerow(["Case ID", "Condition", "Insufficient Handling Label"])
        for c in cases:
            writer.writerow([c["case_id"], c["retrieval_condition"], c["insufficient_handling"]])

    # Markdown
    md = [
        "# Table S3: W-RQ3 Insufficient-Evidence Handling",
        "",
        "### Panel A: Condition-Level Categorical Handling Distribution (n = 6 cases per condition)",
        "",
        "| Condition | n | Appropriate Abstention | Bounded Insufficiency | Substantive w/o Ack | Overclaim Beyond Pilot |",
        "|---|---|---|---|---|---|",
    ]
    for r in dist:
        md.append(
            f"| {r['retrieval_condition']} | {r['n']} | "
            f"{r['appropriate_abstention']} ({float(r['appropriate_abstention_proportion'])*100:.1f}%) | "
            f"{r['appropriate_bounded_insufficiency']} ({float(r['appropriate_bounded_insufficiency_proportion'])*100:.1f}%) | "
            f"{r['substantive_answer_without_insufficiency_acknowledgement']} ({float(r['substantive_answer_without_insufficiency_acknowledgement_proportion'])*100:.1f}%) | "
            f"{r['overclaim_beyond_pilot_evidence']} ({float(r['overclaim_beyond_pilot_evidence_proportion'])*100:.1f}%) |"
        )
    md.extend([
        "",
        "### Panel B: Complete Case-Level Audit Labels (all 24 condition-case cells)",
        "",
        "| Case ID | Condition | Insufficient Handling Label |",
        "|---|---|---|",
    ])
    for c in cases:
        md.append(f"| `{c['case_id']}` | {c['retrieval_condition']} | `{c['insufficient_handling']}` |")

    md.extend([
        "",
        "**Note:** W-RQ3 descriptive evaluation in Western Semantic Follow-up v0.2. Total denominator is 6 insufficient-evidence cases across 4 conditions (24 cells total). Due to small sample size, results are reported purely descriptively with no inferential tests performed. Evaluated by single GPT-5.6 Sol evaluator against frozen pilot evidence.",
    ])
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")


# --- Captions File ---

def render_captions(out_file: Path) -> None:
    captions = """# Captions for Phase II Western Manuscript v0.2.1

## Main Figures

### Figure 1. Study architecture and frozen-data reuse across study versions.
Flow diagram showing the two distinct scientific components of MediRAG Phase II. The left container represents the historically closed **Western Formal Study v0.1.5**, comprising the bounded Western pilot corpus (16 systematic reviews, 271 chunks), the 48-case benchmark, Stage A retrieval (192 cells across R0–R3, completed), Stage B primary answer generation with a fixed Qwen/Qwen3-8B generator (192 answers, completed), and automated Stage C (reached prospective stopping rule without qualifying a Primary Judge; prospectively terminated without formal semantic estimates). The right container represents the **Separate Western Semantic Follow-up v0.2**, an independent post-study evaluation reusing the 192 unchanged frozen Stage-B answers under a single blinded GPT-5.6 Sol evidence-grounded evaluator. The follow-up evaluates W-RQ2 across 42 answerable cases (168 cells) and W-RQ3 across 6 insufficient-evidence cases (24 cells). The follow-up reuses frozen outputs but does not reopen or retroactively complete automated Stage C in v0.1.5.

### Figure 2. Stage-A paired primary-gold chunk-recall differences versus lexical baseline (R0).
Horizontal forest plot displaying paired differences in primary-gold chunk recall@4 for dense retrieval (R1), reciprocal-rank fusion (R2), and fusion with reranking (R3) relative to the lexical baseline (R0) within Western Formal Study v0.1.5. Contrast direction is comparison condition minus R0. Points indicate case-level mean paired differences across the 42 headline answerable cases with non-empty primary gold evidence; error bars indicate 95% percentile confidence intervals derived from 10,000 paired case bootstrap resamples (seed 20260815). The vertical solid line at zero indicates parity with R0. Point estimates and intervals are descriptive and are not interpreted as binary significance verdicts or general condition superiority outside this bounded pilot.

### Figure 3. Follow-up paired full-coverage differences versus lexical baseline (R0).
Horizontal forest plot displaying paired differences in the primary semantic endpoint (case-level macro full evidence-point coverage) for R1, R2, and R3 relative to R0 within the separate Western Semantic Follow-up v0.2. Contrast direction is comparison condition minus R0. Points represent macro mean paired differences across 42 answerable benchmark cases evaluated with the generator held fixed to Qwen/Qwen3-8B; error bars indicate 95% percentile confidence intervals from 10,000 paired case bootstrap resamples (seed 20260815). The vertical line indicates parity with R0. Semantic judgments were produced by a single blinded GPT-5.6 Sol evaluator. Results are pilot-specific descriptive observations and do not establish clinical validity, clinical correctness, or a causal relationship between retrieval performance and generated-answer quality.

---

## Main Tables

### Table 1. Stage-A headline retrieval metrics across frozen retrieval conditions.
Exact condition-level retrieval performance within Western Formal Study v0.1.5. Headline denominator is 42 supported or partially supported cases with non-empty primary gold evidence; six insufficient-evidence cases were excluded from headline retrieval denominators and not imputed as failures. Retrieval depth was fixed to top 4 for all conditions. Primary-gold chunk recall and source recall are micro-aggregates over gold items; Hit@4 and MRR evaluate case-level first-hit occurrence. Condition definitions: R0 = lexical BM25-like; R1 = dense BAAI/bge-m3; R2 = lexical–dense reciprocal-rank fusion (k=60); R3 = R2 candidate generation (depth 12) followed by BAAI/bge-reranker-v2-m3 reranking to top 4.

### Table 2. Semantic evidence full coverage by retrieval condition in Follow-up v0.2.
Exact condition-level descriptive summaries for the primary semantic endpoint (`full_coverage_score`) within Western Semantic Follow-up v0.2. Evaluates fixed Qwen/Qwen3-8B generated answers across 42 answerable benchmark cases (168 cells total). For each answer, full coverage is the proportion of frozen expected evidence points judged fully supported by supplied top-4 retrieved excerpts. Judgments were generated by a single blinded GPT-5.6 Sol evaluator without human or clinician adjudication. Macro mean, standard deviation (SD), median, minimum, and maximum are shown. Findings measure textual evidence grounding and do not establish clinical correctness or safety.

### Table 3. Unsupported-claim presence and contradiction behavior by retrieval condition.
Secondary evidence-grounded outcomes in Western Semantic Follow-up v0.2 across 42 answerable cases per condition. Panel A reports condition-level presence counts and rates for generated answers containing at least one unsupported claim or at least one contradiction against supplied evidence, alongside total contradicted expected evidence points. Panel B reports exact two-sided McNemar binomial tests on paired discordant presence indicators for unsupported claims versus R0, with family-wise error rate controlled via the Holm-Bonferroni method across the three prespecified comparisons (family size = 3). Unsupported-claim annotations are rubric-grounded textual assessments and do not constitute validated general hallucination or clinical-safety metrics.

---

## Supplementary Tables

### Table S1. Complete Stage-A paired retrieval statistics.
Comprehensive paired comparison statistics for Stage-A primary-gold chunk recall@4 and Hit@4 discordance against R0 within Western Formal Study v0.1.5. Includes paired sample sizes (n = 42), technical missingness (0), mean paired recall differences, 95% bootstrap confidence intervals (10,000 resamples, seed 20260815), discordant Hit@4 pair counts, and exact two-sided McNemar p-values. No multiplicity adjustment was prespecified for Stage A.

### Table S2. Detailed secondary semantic outcomes in Follow-up v0.2.
Comprehensive condition-level and paired statistics for secondary semantic endpoints in Western Semantic Follow-up v0.2 across 42 answerable cases. Panel A reports descriptive summaries and paired differences versus R0 for partial-credit coverage. Panel B reports descriptive summaries and paired differences versus R0 for unsupported-claim counts. Confidence intervals represent 95% percentile intervals from 10,000 paired case bootstrap resamples (seed 20260815). Panel C reports condition-level distributions across the 58 total expected evidence points (covered, partially covered, not covered, contradicted). Expected evidence points are nested within cases and are not independent inferential units.

### Table S3. W-RQ3 descriptive evaluation of insufficient-evidence cases.
Evaluation of system behavior when the pilot corpus provides insufficient evidence to answer the benchmark query (W-RQ3) in Western Semantic Follow-up v0.2. Denominator is 6 insufficient-evidence cases per condition (24 cells total). Panel A reports categorical distribution across four frozen rubric labels: appropriate abstention, appropriate bounded insufficiency, substantive answer without insufficiency acknowledgement, and overclaim beyond pilot evidence. Panel B lists complete case-level annotations across all 24 cells for full traceability. Due to the small sample size (n = 6), analyses are descriptive only with no hypothesis tests performed.
"""
    out_file.write_text(captions.strip() + "\n", encoding="utf-8")


# --- Source Data Package ---

def export_source_data(pkg_source_data: Path) -> None:
    pkg_source_data.mkdir(parents=True, exist_ok=True)

    sources_to_copy = [
        (STAGE_A_TABLES / "stage_a_headline_metrics.csv", pkg_source_data / "stage_a_headline_metrics.csv"),
        (STAGE_A_TABLES / "stage_a_pairwise_vs_r0.csv", pkg_source_data / "stage_a_pairwise_vs_r0.csv"),
        (STAGE_C2_TABLES / "w_rq2_primary_coverage_by_condition.csv", pkg_source_data / "w_rq2_primary_coverage_by_condition.csv"),
        (STAGE_C2_TABLES / "w_rq2_primary_pairwise_vs_r0.csv", pkg_source_data / "w_rq2_primary_pairwise_vs_r0.csv"),
        (STAGE_C2_TABLES / "w_rq2_unsupported_presence_by_condition.csv", pkg_source_data / "w_rq2_unsupported_presence_by_condition.csv"),
        (STAGE_C2_TABLES / "w_rq2_unsupported_mcnemar_vs_r0.csv", pkg_source_data / "w_rq2_unsupported_mcnemar_vs_r0.csv"),
        (STAGE_C2_TABLES / "w_rq2_contradictions_by_condition.csv", pkg_source_data / "w_rq2_contradictions_by_condition.csv"),
        (STAGE_C2_TABLES / "w_rq2_partial_credit_by_condition.csv", pkg_source_data / "w_rq2_partial_credit_by_condition.csv"),
        (STAGE_C2_TABLES / "w_rq2_partial_credit_pairwise_vs_r0.csv", pkg_source_data / "w_rq2_partial_credit_pairwise_vs_r0.csv"),
        (STAGE_C2_TABLES / "w_rq2_unsupported_count_by_condition.csv", pkg_source_data / "w_rq2_unsupported_count_by_condition.csv"),
        (STAGE_C2_TABLES / "w_rq2_unsupported_count_pairwise_vs_r0.csv", pkg_source_data / "w_rq2_unsupported_count_pairwise_vs_r0.csv"),
        (STAGE_C2_TABLES / "w_rq2_expected_point_labels_by_condition.csv", pkg_source_data / "w_rq2_expected_point_labels_by_condition.csv"),
        (STAGE_C2_TABLES / "w_rq3_insufficient_label_distribution.csv", pkg_source_data / "w_rq3_insufficient_label_distribution.csv"),
        (STAGE_C2_TABLES / "w_rq3_case_by_condition.csv", pkg_source_data / "w_rq3_case_by_condition.csv"),
    ]

    for src, dst in sources_to_copy:
        shutil.copy2(src, dst)

    readme = """# Source Data Package for Phase II Western Manuscript v0.2.1 Figures and Tables

This directory contains the exact, compact derived CSV tables required to reproduce all figures and tables in the publication package.

## Authoritative Provenance Crosswalk

| Source Data CSV | Authoritative Repository Source Path | Used By |
|---|---|---|
| `stage_a_headline_metrics.csv` | `research/experiments/western_formal_v0_1/stage_a_publication_v0_1_5/tables/stage_a_headline_metrics.csv` | Table 1 |
| `stage_a_pairwise_vs_r0.csv` | `research/experiments/western_formal_v0_1/stage_a_publication_v0_1_5/tables/stage_a_pairwise_vs_r0.csv` | Figure 2, Table S1 |
| `w_rq2_primary_coverage_by_condition.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_primary_coverage_by_condition.csv` | Table 2 |
| `w_rq2_primary_pairwise_vs_r0.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_primary_pairwise_vs_r0.csv` | Figure 3 |
| `w_rq2_unsupported_presence_by_condition.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_unsupported_presence_by_condition.csv` | Table 3 Panel A |
| `w_rq2_unsupported_mcnemar_vs_r0.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_unsupported_mcnemar_vs_r0.csv` | Table 3 Panel B |
| `w_rq2_contradictions_by_condition.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_contradictions_by_condition.csv` | Table 3 Panel A |
| `w_rq2_partial_credit_by_condition.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_partial_credit_by_condition.csv` | Table S2 Panel A |
| `w_rq2_partial_credit_pairwise_vs_r0.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_partial_credit_pairwise_vs_r0.csv` | Table S2 Panel A |
| `w_rq2_unsupported_count_by_condition.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_unsupported_count_by_condition.csv` | Table S2 Panel B |
| `w_rq2_unsupported_count_pairwise_vs_r0.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_unsupported_count_pairwise_vs_r0.csv` | Table S2 Panel B |
| `w_rq2_expected_point_labels_by_condition.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_expected_point_labels_by_condition.csv` | Table S2 Panel C |
| `w_rq3_insufficient_label_distribution.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq3_insufficient_label_distribution.csv` | Table S3 Panel A |
| `w_rq3_case_by_condition.csv` | `research/experiments/western_semantic_followup_v0_2/tables/w_rq3_case_by_condition.csv` | Table S3 Panel B |

## Privacy and Data Safeguards
- No full Western corpus source text is included.
- No generated answer prose is included.
- No blind key mapping (`stage_c2_blind_key.csv`) is included.
- No protected Excel evaluation workbook (`stage_c2_blinded_eval_input.xlsx`) is included.
"""
    (pkg_source_data / "README.md").write_text(readme.strip() + "\n", encoding="utf-8")


# --- Main Rendering Orchestration ---

def render_package(output_dir: Path) -> dict[str, str]:
    fig_dir = output_dir / "figures"
    tab_dir = output_dir / "tables"
    sup_dir = output_dir / "supplement"
    src_dir = output_dir / "source_data"

    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)
    sup_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(parents=True, exist_ok=True)

    data = verify_source_data()

    # Render figures
    f1_svg = fig_dir / "Figure_1_study_flow.svg"
    f1_png = fig_dir / "Figure_1_study_flow.png"
    render_figure_1(f1_svg, f1_png)

    f2_svg = fig_dir / "Figure_2_stage_a_paired_recall.svg"
    f2_png = fig_dir / "Figure_2_stage_a_paired_recall.png"
    render_figure_2(data["stage_a_pairwise"], f2_svg, f2_png)

    f3_svg = fig_dir / "Figure_3_semantic_full_coverage.svg"
    f3_png = fig_dir / "Figure_3_semantic_full_coverage.png"
    render_figure_3(data["w_rq2_pairwise"], f3_svg, f3_png)

    # Render main tables
    render_table_1(data["stage_a_headline"], tab_dir / "Table_1_stage_a_headline_metrics.md", tab_dir / "Table_1_stage_a_headline_metrics.csv")
    render_table_2(data["w_rq2_coverage"], tab_dir / "Table_2_semantic_full_coverage.md", tab_dir / "Table_2_semantic_full_coverage.csv")
    render_table_3(data["w_rq2_presence"], data["w_rq2_contradictions"], data["w_rq2_mcnemar"], tab_dir / "Table_3_unsupported_and_contradictions.md", tab_dir / "Table_3_unsupported_and_contradictions.csv")

    # Render supplementary tables
    render_table_s1(data["stage_a_pairwise"], sup_dir / "Table_S1_stage_a_complete_pairwise.md", sup_dir / "Table_S1_stage_a_complete_pairwise.csv")
    render_table_s2(sup_dir / "Table_S2_semantic_secondary_outcomes.md", sup_dir / "Table_S2_semantic_secondary_outcomes.csv")
    render_table_s3(data["w_rq3_dist"], data["w_rq3_cases"], sup_dir / "Table_S3_insufficient_evidence.md", sup_dir / "Table_S3_insufficient_evidence.csv")

    # Captions
    render_captions(output_dir / "CAPTIONS_v0.2.1.md")

    # Source data
    export_source_data(src_dir)

    # Return SHA256 of all generated files
    hashes = {}
    for p in sorted(output_dir.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(output_dir)).replace("\\", "/")
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Phase II Western Manuscript v0.2.1 Publication Package")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Destination directory for publication package")
    args = parser.parse_args()

    print(f"Rendering publication package to: {args.output_dir}")
    hashes = render_package(args.output_dir)
    print(f"Rendered {len(hashes)} publication artifacts successfully.")
    for path, h in sorted(hashes.items()):
        print(f"  {path}: {h}")


if __name__ == "__main__":
    main()
