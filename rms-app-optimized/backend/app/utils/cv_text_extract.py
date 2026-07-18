"""Extract plain text from an uploaded CV (pdf via pypdf, docx via python-docx).

Best-effort: returns "" on any parse failure (cv_text is nullable; agents never block on it).
"""
from __future__ import annotations

import io

_MAX_CHARS = 200_000  # guard against pathological files; agents trim further at call time


def extract_text(filename: str, data: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    try:
        if ext == "pdf":
            text = _extract_pdf(data)
        elif ext == "docx":
            text = _extract_docx(data)
        else:
            return ""
    except Exception:  # noqa: BLE001 — extraction is best-effort
        return ""
    return text[:_MAX_CHARS].strip()


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)
