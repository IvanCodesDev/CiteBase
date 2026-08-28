"""Extractor 实现：plain（文本/Markdown）与 pypdf（PDF，可选依赖）。"""

from citebase.extractors.pdf import PYPDF_AVAILABLE, PypdfExtractor
from citebase.extractors.plain import PlainTextExtractor
from citebase.ports import Extractor


def default_extractors() -> list[Extractor]:
    """按优先级返回可用抽取器；pypdf 未安装时自动缺席。"""
    extractors: list[Extractor] = [PlainTextExtractor()]
    if PYPDF_AVAILABLE:
        extractors.append(PypdfExtractor())
    return extractors


__all__ = [
    "PYPDF_AVAILABLE",
    "PlainTextExtractor",
    "PypdfExtractor",
    "default_extractors",
]
