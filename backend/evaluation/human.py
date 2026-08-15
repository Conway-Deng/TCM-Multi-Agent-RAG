from __future__ import annotations

import csv
from pathlib import Path

from pydantic import ValidationError

from schemas.research import HumanReview


FIELDS = list(HumanReview.model_fields)


def write_template(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def validate_import(path: Path) -> tuple[list[HumanReview], list[str]]:
    reviews: list[HumanReview] = []
    errors: list[str] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for line, row in enumerate(csv.DictReader(handle), 2):
            try:
                reviews.append(HumanReview.model_validate(row))
            except ValidationError as exc:
                errors.append(f"row {line}: {exc}")
    return reviews, errors


def cohens_kappa(left: list[int], right: list[int]) -> float | None:
    pairs = list(zip(left, right))
    if not pairs:
        return None
    observed = sum(a == b for a, b in pairs) / len(pairs)
    categories = sorted(set(left) | set(right))
    expected = sum((left.count(category) / len(left)) * (right.count(category) / len(right)) for category in categories)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def aggregate_reviews(reviews: list[HumanReview]) -> dict[str, object]:
    score_fields = [field for field in FIELDS if field.endswith("_score")]
    aggregates = {
        field: sum(getattr(review, field) for review in reviews) / len(reviews)
        for field in score_fields
    } if reviews else {}
    return {
        "review_count": len(reviews),
        "means": aggregates,
        "limitations": [
            "Likert values are ordinal; means are descriptive and should be interpreted cautiously.",
            "Inter-rater agreement requires multiple independent reviewers on overlapping items.",
            "Reviewer sampling, expertise, blinding, and order effects must be reported.",
        ],
    }
