"""
pdf_tools.py — JARVIS v3 PDF Tools (PyMuPDF)
"""
from __future__ import annotations
import os
from pathlib import Path


def _open(path: str):
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF not installed: pip install pymupdf")
    path = os.path.expanduser(path)
    if not Path(path).exists():
        raise FileNotFoundError(f"Not found: {path}")
    return fitz.open(path)


def extract_text(path: str, max_pages: int = 50) -> str:
    try:
        doc = _open(path)
        pages = [page.get_text() for i, page in enumerate(doc) if i < max_pages]
        if len(doc) > max_pages:
            pages.append(f"\n[truncated at {max_pages} pages]")
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        return f"PDF error: {e}"


def summarize_pdf(router, path: str, max_chars: int = 6000) -> str:
    text = extract_text(path, max_pages=30)
    if text.startswith("PDF error"):
        return text
    text = text[:max_chars]
    if router is None:
        return text[:2000]
    prompt = (f"Summarize this document concisely. Key points, findings, conclusions.\n\n"
              f"Document ({Path(path).name}):\n{text}")
    return router.chat_sync([{"role": "user", "content": prompt}])


def extract_tables(path: str) -> str:
    try:
        doc = _open(path)
        tables = []
        for i, page in enumerate(doc):
            for block in page.get_text("blocks"):
                text = block[4] if len(block) > 4 else ""
                lines = text.strip().splitlines()
                if len(lines) >= 3:
                    tab_score = sum(1 for l in lines if l.count("  ") >= 2 or "\t" in l)
                    if tab_score >= len(lines) * 0.4:
                        tables.append(f"[Page {i+1}]\n{text.strip()}")
        doc.close()
        return "\n\n---\n\n".join(tables[:10]) if tables else "No tables detected."
    except Exception as e:
        return f"Table extract error: {e}"


def search_in_document(path: str, query: str, context_chars: int = 200) -> str:
    try:
        text = extract_text(path)
        q = query.lower()
        tl = text.lower()
        matches, start = [], 0
        while len(matches) < 10:
            pos = tl.find(q, start)
            if pos == -1:
                break
            s = max(0, pos - context_chars)
            e = min(len(text), pos + len(query) + context_chars)
            matches.append(f"…{text[s:e].replace(chr(10),' ').strip()}…")
            start = pos + 1
        if not matches:
            return f"'{query}' not found in {Path(path).name}"
        return f"{len(matches)} occurrence(s) of '{query}':\n\n" + \
               "\n\n".join(f"[{i+1}] {m}" for i, m in enumerate(matches))
    except Exception as e:
        return f"Search error: {e}"


# ── Mark-XL entry point ────────────────────────────────────────────────────

def run_pdf_tool(action: str, file_path: str, query: str = "", pages=None) -> str:
    """
    Unified entry point called by Mark-XL's _execute_tool dispatcher.
    action: summarize | extract_text | extract_tables | search | qa
    """
    try:
        if action == "extract_text":
            return extract_text(file_path)
        elif action == "summarize":
            # No router available here — return raw text summary
            text = extract_text(file_path, max_pages=20)
            if not text or text.startswith("PyMuPDF"):
                return text
            return text[:3000] + ("…" if len(text) > 3000 else "")
        elif action == "extract_tables":
            return extract_tables(file_path)
        elif action in ("search", "qa"):
            if not query:
                return "Please provide a query for search/qa."
            return search_in_document(file_path, query)
        else:
            return f"Unknown PDF action: {action}. Available: summarize, extract_text, extract_tables, search, qa"
    except Exception as e:
        return f"PDF tool error ({action}): {e}"
