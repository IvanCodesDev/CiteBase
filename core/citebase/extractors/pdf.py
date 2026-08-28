"""PDF 抽取器（可选依赖 pypdf，安装：``pip install citebase[pdf]``）。

逐页抽取文本并以 ``<!-- page N -->`` 注释标记页界，便于 loc 行区间回溯到页。
纯文本抽取会丢失表格/公式结构，置信度按 0.8 入档（低于 0.6 才触发 L-PROV-4）。
"""

from __future__ import annotations

from importlib import metadata, util
from pathlib import Path

from citebase.ports import ExtractedText

PYPDF_AVAILABLE = util.find_spec("pypdf") is not None

PDF_CONFIDENCE = 0.8


def _pypdf_version() -> str:
    try:
        return metadata.version("pypdf")
    except metadata.PackageNotFoundError:
        return "unknown"


class PypdfExtractor:
    def __init__(self) -> None:
        if not PYPDF_AVAILABLE:
            raise RuntimeError("pypdf 未安装：pip install citebase[pdf]")
        self.name = f"pypdf@{_pypdf_version()}"

    def can_extract(self, original: Path) -> bool:
        return original.suffix.lower() == ".pdf"

    def extract(self, original: Path) -> ExtractedText:
        from pypdf import PdfReader

        reader = PdfReader(str(original))
        parts: list[str] = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            parts.append(f"<!-- page {page_no} -->")
            if text:
                parts.append(text)
        joined = "\n".join(parts)
        if not joined.endswith("\n"):
            joined += "\n"
        return ExtractedText(text=joined, confidence=PDF_CONFIDENCE)
