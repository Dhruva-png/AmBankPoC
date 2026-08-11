from __future__ import annotations

from pathlib import Path

from extract_text import render_pdf_pages_to_images


def _docx_to_pdf(path: str, out_dir: str) -> str:
    import win32com.client

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    pdf_path = str(Path(out_dir) / (Path(path).stem + ".pdf"))
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        wdoc = word.Documents.Open(str(Path(path).resolve()), ReadOnly=True)
        try:
            wdoc.ExportAsFixedFormat(pdf_path, ExportFormat=17)  # wdExportFormatPDF
        finally:
            wdoc.Close(False)
    finally:
        word.Quit()
    return pdf_path


def render_document_pages(path: str, out_dir: str, scale: float = 1.5) -> list[str]:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return render_pdf_pages_to_images(path, out_dir, scale=scale)
    if suffix in (".doc", ".docx"):
        pdf_path = _docx_to_pdf(path, out_dir)
        return render_pdf_pages_to_images(pdf_path, out_dir, scale=scale)
    raise ValueError(f"Unsupported file type for preview: {suffix}")
