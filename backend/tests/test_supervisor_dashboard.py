import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "supervisor-dashboard.js").read_text(encoding="utf-8")
RESULTS = json.loads((ROOT / "frontend" / "data" / "research_results.json").read_text(encoding="utf-8"))


def test_supervisor_dashboard_has_required_sections_and_local_demo() -> None:
    for section in ("overview", "live-demo", "formal-results", "methodology"):
        assert f'id="{section}"' in HTML
    assert "START LIVE DEMO".casefold() in HTML.casefold()
    assert "DEMO RUN · NOT FORMAL BENCHMARK DATA".casefold() in HTML.casefold()
    assert "/api/research/run" in JS
    assert "['C1', 'C2']" in JS
    assert "['C2', 'C4']" in JS
    assert "value=\"3\" checked" in HTML


def test_presentation_results_match_frozen_display_values() -> None:
    assert RESULTS["rq1"]["full_recall_pct"] == {"C1": 90.76, "C2": 90.58}
    assert RESULTS["rq1"]["difference_c2_minus_c1_pp"] == -0.18
    assert RESULTS["rq1"]["bootstrap_95_ci_pp"] == [-1.81, 1.63]
    assert RESULTS["rq4"]["full_recall_pct"] == {"C2": 83.75, "C4": 81.25}
    assert RESULTS["rq4"]["bootstrap_95_ci_pp"] == [-8.12, 2.5]
    assert RESULTS["rq4"]["reliability_usable"] == {"C2": 88, "C4": 80}
    assert RESULTS["rq4"]["mean_latency_seconds"] == {"C2": 7.2785, "C4": 39.6598}


def test_frontend_bundle_is_public_safe() -> None:
    combined = HTML + JS + json.dumps(RESULTS)
    assert "sk-" not in combined
    assert "LLM_API_KEY" not in combined
    assert RESULTS["public_safety"] == {
        "aggregate_results_only": True,
        "contains_raw_corpus": False,
        "contains_raw_experiment_outputs": False,
        "contains_secrets": False,
    }
