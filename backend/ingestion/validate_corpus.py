from __future__ import annotations

from corpus import corpus_version, validate_corpus


def main() -> int:
    issues = validate_corpus()
    if issues:
        print("\n".join(issues))
        return 1
    print(f"Corpus valid: {corpus_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
