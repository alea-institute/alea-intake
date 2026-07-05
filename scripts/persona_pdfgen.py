#!/usr/bin/env python3
"""Render each persona's src/*.txt synthetic document into docs/*.pdf (monospace,
legal-doc look) via WeasyPrint, so the harness can upload them as application/pdf.

Usage: backend/.venv/bin/python scripts/persona_pdfgen.py [personas_root]
Default root: docs/evidence/persona-campaign/personas
"""
import html
import sys
from pathlib import Path

from weasyprint import HTML

CSS = """
@page { size: letter; margin: 0.9in; }
body { font-family: 'DejaVu Sans Mono', monospace; font-size: 10.5px; line-height: 1.35;
       white-space: pre-wrap; color: #111; }
"""


def render(src: Path, out: Path):
    text = src.read_text()
    doc = f"<html><head><style>{CSS}</style></head><body>{html.escape(text)}</body></html>"
    HTML(string=doc).write_pdf(str(out))
    return out.stat().st_size


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parents[1] / "docs/evidence/persona-campaign/personas"
    total = 0
    for persona in sorted(p for p in root.iterdir() if p.is_dir()):
        src_dir = persona / "src"
        out_dir = persona / "docs"
        if not src_dir.is_dir():
            continue
        out_dir.mkdir(exist_ok=True)
        for src in sorted(src_dir.glob("*.txt")):
            out = out_dir / (src.stem + ".pdf")
            size = render(src, out)
            total += 1
            print(f"  {persona.name}/{out.name}: {size} bytes")
    print(f"== rendered {total} PDFs ==")


if __name__ == "__main__":
    main()
