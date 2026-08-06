"""Generic document text extraction: .docx, .doc and .pdf -> plain text.

Mirrors the paragraph/table text extraction approach used to read the POC
scope deck (python-pptx) -- here for Word/PDF source documents instead of
slides. Used as the first step of both Case 1 and Case 2: extract text,
then compare.
"""
from __future__ import annotations

import sys
from pathlib import Path


def extract_docx_text(path: str) -> str:
    """Paragraphs in document order, then every table rendered as one row per line."""
    import docx

    doc = docx.Document(path)
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    for ti, table in enumerate(doc.tables):
        parts.append(f"\n[TABLE {ti}]")
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            parts.append(" | ".join(cells))
    return "\n".join(parts)


def extract_doc_text(path: str) -> str:
    """Legacy .doc via MS Word COM automation (requires Word installed, Windows only)."""
    import win32com.client

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        wdoc = word.Documents.Open(str(Path(path).resolve()), ReadOnly=True)
        try:
            return wdoc.Content.Text
        finally:
            wdoc.Close(False)
    finally:
        word.Quit()


def extract_pdf_text(path: str) -> str:
    """Text-layer extraction via pdfplumber. Returns '' for pages with no text layer
    (i.e. scanned/flattened images) -- those need OCR or vision-model parsing, not
    handled here."""
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            parts.append(f"--- page {i + 1} ---\n{text}")
    return "\n\n".join(parts)


def extract_text(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(path)
    if suffix == ".doc":
        return extract_doc_text(path)
    if suffix == ".pdf":
        return extract_pdf_text(path)
    raise ValueError(f"Unsupported file type: {suffix} ({path})")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python extract_text.py <file> [-o out.txt]", file=sys.stderr)
        raise SystemExit(2)
    src = sys.argv[1]
    text = extract_text(src)
    if "-o" in sys.argv:
        out_path = sys.argv[sys.argv.index("-o") + 1]
        Path(out_path).write_text(text, encoding="utf-8")
        print(f"wrote {len(text)} chars to {out_path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
