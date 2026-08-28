from __future__ import annotations

from pathlib import Path

from citebase.extractors import PYPDF_AVAILABLE, PlainTextExtractor, default_extractors


def test_plain_normalizes_newlines(tmp_path: Path) -> None:
    file = tmp_path / "notes.txt"
    file.write_bytes("第一行\r\n第二行\r尾行".encode())
    extractor = PlainTextExtractor()
    assert extractor.can_extract(file)
    result = extractor.extract(file)
    assert result.text == "第一行\n第二行\n尾行\n"
    assert result.confidence == 1.0


def test_plain_rejects_unknown_suffix(tmp_path: Path) -> None:
    assert not PlainTextExtractor().can_extract(tmp_path / "a.pdf")
    assert not PlainTextExtractor().can_extract(tmp_path / "a.bin")


def test_default_extractors_include_pdf_when_available() -> None:
    extractors = default_extractors()
    names = [e.name for e in extractors]
    assert names[0] == "plain@1"
    if PYPDF_AVAILABLE:
        from citebase.extractors import PypdfExtractor

        assert any(isinstance(e, PypdfExtractor) for e in extractors)
        pdf = next(e for e in extractors if isinstance(e, PypdfExtractor))
        assert pdf.name.startswith("pypdf@")
        assert pdf.can_extract(Path("paper.pdf"))
        assert not pdf.can_extract(Path("paper.md"))
