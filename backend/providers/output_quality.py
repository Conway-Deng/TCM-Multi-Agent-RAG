from __future__ import annotations

from collections import Counter
import re


_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)?|[\u3400-\u9fff]|[\uac00-\ud7af]")


def runaway_output_reason(text: str, *, max_words: int = 180) -> str | None:
    """Return a rejection reason without modifying generated medical content."""
    if not text.strip():
        return "empty output"
    stripped = text.strip()
    if "\ufffd" in text or any(ord(character) < 32 and character not in "\n\r\t" for character in text):
        return "invalid text character"
    if "\\" in text:
        return "unexpected escape formatting"
    if not stripped.endswith((".", "?", "!", "。", "？", "！")):
        return "incomplete paragraph"
    if re.search(r"(?:,,|;;|::|\.\.)", text):
        return "malformed repeated punctuation"
    if re.search(r"[a-z][A-Z]", text):
        return "malformed token spacing"
    words = [token.casefold() for token in _WORD_PATTERN.findall(text)]
    if len(words) < 8:
        return "insufficient complete content"
    if len(words) > max_words:
        return f"word limit exceeded ({len(words)} > {max_words})"
    if any(left == right for left, right in zip(words, words[1:])):
        return "consecutive repeated token"

    if len(words) >= 12:
        trigrams = Counter(tuple(words[index:index + 3]) for index in range(len(words) - 2))
        if max(trigrams.values(), default=0) >= 4:
            return "repeated phrase pattern"
    if len(words) >= 40 and len(set(words)) / len(words) < 0.35:
        return "low lexical diversity"
    return None
