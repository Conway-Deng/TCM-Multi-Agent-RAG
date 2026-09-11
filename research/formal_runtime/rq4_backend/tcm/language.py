from __future__ import annotations

import re

from .schemas import ResponseLanguage


def detect_language(text: str) -> ResponseLanguage:
    chinese = len(re.findall(r"[\u3400-\u9fff]", text))
    korean = len(re.findall(r"[\uac00-\ud7af]", text))
    english = len(re.findall(r"[A-Za-z]", text))
    if chinese >= max(2, korean, english * 0.25):
        return "zh"
    if korean >= max(2, chinese, english * 0.25):
        return "ko"
    return "en"
