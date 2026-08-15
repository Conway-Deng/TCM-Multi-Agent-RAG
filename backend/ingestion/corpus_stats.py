from __future__ import annotations

import json

from corpus import corpus_stats


if __name__ == "__main__":
    print(json.dumps(corpus_stats(), ensure_ascii=False, indent=2))
