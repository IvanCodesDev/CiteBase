"""纯文本抽取器：文本类原件直接作为派生物（换行归一为 \\n）。"""

from __future__ import annotations

from pathlib import Path

from cardvault.ports import ExtractedText

_TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml"}


class PlainTextExtractor:
    name = "plain@1"

    def can_extract(self, original: Path) -> bool:
        return original.suffix.lower() in _TEXT_SUFFIXES

    def extract(self, original: Path) -> ExtractedText:
        raw = original.read_text(encoding="utf-8", errors="replace")
        text = raw.replace("\r\n", "\n").replace("\r", "\n")
        if not text.endswith("\n"):
            text += "\n"
        return ExtractedText(text=text, confidence=1.0)
