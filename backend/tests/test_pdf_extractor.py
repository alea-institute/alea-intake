"""PDF structure and provenance contracts, using dependency-free PDF fixtures."""

import ast
from pathlib import Path

import pytest

from app.services.document.extractors.pdf_extractor import _extract_sync


def _write_pdf(path, content):
    """Write a one-page PDF with Helvetica text or an image-only content stream."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> /XObject << /Im1 6 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
        b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\nstream\n\x80\nendstream",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += str(number).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    startxref = len(pdf)
    pdf += b"xref\n0 7\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode()
    path.write_bytes(pdf)


def test_title_body_and_provenance(tmp_path):
    path = tmp_path / "title-body.pdf"
    _write_pdf(path, b"BT /F1 18 Tf 72 720 Td (Legal Title) Tj "
               b"/F1 11 Tf 0 -40 Td (First body paragraph.) Tj "
               b"0 -20 Td (Second body paragraph.) Tj ET")
    text, elements = _extract_sync(path)
    assert "Legal Title" in text
    assert [(e["text"], e["element_type"], e["font_size"]) for e in elements] == [
        ("Legal Title", "heading", 18),
        ("First body paragraph.", "paragraph", 11),
        ("Second body paragraph.", "paragraph", 11),
    ]
    for element in elements:
        assert element["page"] == 1
        x0, y0, x1, y1 = element["bbox"]
        assert x0 == pytest.approx(72)
        assert 0 < y0 < y1 < 792
        assert 72 < x1 < 612


def test_image_only_pdf_has_no_embedded_text(tmp_path):
    path = tmp_path / "scan.pdf"
    _write_pdf(path, b"q 200 0 0 200 72 500 cm /Im1 Do Q")
    assert _extract_sync(path) == ("", [])


def test_source_does_not_import_removed_pdf_backend():
    app_dir = Path(__file__).parents[1] / "app"
    imports = set()
    for path in app_dir.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    assert not (imports & {"pymupdf", "fitz"})
