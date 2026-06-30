import logging
import os
import uuid

logger = logging.getLogger(__name__)

# ── Per-format extractors ─────────────────────────────────────────────────────

def _extract_pdf(path: str) -> list[str]:
    """
    Try text extraction first. If the PDF is scanned (< 50 avg chars/page),
    fall back to OCR via pytesseract + pdf2image.
    """
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages_text: list[str] = []
    for page in reader.pages:
        pages_text.append((page.extract_text() or "").strip())

    total_chars = sum(len(t) for t in pages_text)
    avg_chars = total_chars / max(len(pages_text), 1)

    if avg_chars >= 50:
        return [t for t in pages_text if t]

    # Scanned PDF — attempt OCR
    logger.info("[ingest] scanned PDF detected (avg %.1f chars/page) — running OCR", avg_chars)
    return _ocr_pdf(path)


def _ocr_pdf(path: str) -> list[str]:
    """OCR a scanned/image-only PDF using pdf2image + tesseract."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        raise ValueError(
            "This PDF has no text layer. OCR packages are missing. "
            "Run: pip install pytesseract pdf2image  "
            "and: apt install tesseract-ocr poppler-utils"
        )

    logger.info("[ingest] converting PDF pages to images for OCR…")
    try:
        images = convert_from_path(path, dpi=200, thread_count=4)
    except Exception as e:
        raise ValueError(f"pdf2image failed: {e}")

    pages: list[str] = []
    for i, img in enumerate(images):
        try:
            text = pytesseract.image_to_string(img, config="--psm 6").strip()
            if text:
                pages.append(text)
        except Exception as e:
            logger.warning("[ingest] OCR failed on page %d: %s", i + 1, e)

    if not pages:
        raise ValueError("OCR produced no text. The PDF may be a scanned document with very low quality.")
    logger.info("[ingest] OCR complete: %d pages with text", len(pages))
    return pages


def _extract_epub(path: str) -> list[str]:
    import ebooklib
    from ebooklib import epub
    import html2text

    book = epub.read_epub(path, options={"ignore_ncx": True})
    h2t = html2text.HTML2Text()
    h2t.ignore_links = True
    h2t.ignore_images = True
    h2t.body_width = 0

    chapters: list[str] = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            html = item.get_content().decode("utf-8", errors="replace")
            text = h2t.handle(html).strip()
            if len(text) > 100:
                chapters.append(text)
    return chapters


def _extract_docx(path: str) -> list[str]:
    from docx import Document
    doc = Document(path)
    sections: list[str] = []
    current: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            if current:
                sections.append("\n".join(current))
                current = []
        else:
            current.append(text)
    if current:
        sections.append("\n".join(current))
    return sections


def _extract_odt(path: str) -> list[str]:
    from odf import text as odf_text, teletype
    from odf.opendocument import load
    doc = load(path)
    sections: list[str] = []
    current: list[str] = []
    for elem in doc.getElementsByType(odf_text.P):
        t = teletype.extractText(elem).strip()
        if not t:
            if current:
                sections.append("\n".join(current))
                current = []
        else:
            current.append(t)
    if current:
        sections.append("\n".join(current))
    return sections


def _extract_html(path: str) -> list[str]:
    import html2text
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    h2t = html2text.HTML2Text()
    h2t.ignore_links = True
    h2t.ignore_images = True
    h2t.body_width = 0
    text = h2t.handle(content)
    return [s.strip() for s in text.split("\n\n") if s.strip()]


def _extract_plaintext(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return [s.strip() for s in content.split("\n\n") if s.strip()]


# ── Format dispatcher ─────────────────────────────────────────────────────────

def extract_text(path: str) -> list[str]:
    ext = os.path.splitext(path)[1].lower()
    dispatch = {
        ".pdf":      _extract_pdf,
        ".epub":     _extract_epub,
        ".docx":     _extract_docx,
        ".doc":      _extract_docx,
        ".odt":      _extract_odt,
        ".html":     _extract_html,
        ".htm":      _extract_html,
        ".txt":      _extract_plaintext,
        ".md":       _extract_plaintext,
        ".markdown": _extract_plaintext,
        ".rst":      _extract_plaintext,
        ".csv":      _extract_plaintext,
        ".json":     _extract_plaintext,
    }
    extractor = dispatch.get(ext, _extract_plaintext)
    logger.info("[ingest] using extractor for %s: %s", ext or "unknown", extractor.__name__)
    return extractor(path)


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_sections(sections: list[str], max_size: int = 800) -> list[str]:
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_size:
            if len(section) >= 40:
                chunks.append(section)
        else:
            paras = [p.strip() for p in section.split("\n") if p.strip()]
            current = ""
            for para in paras:
                if len(current) + len(para) + 1 <= max_size:
                    current = (current + "\n" + para).strip() if current else para
                else:
                    if current:
                        chunks.append(current)
                    if len(para) > max_size:
                        for i in range(0, len(para), max_size):
                            part = para[i : i + max_size].strip()
                            if len(part) >= 40:
                                chunks.append(part)
                        current = ""
                    else:
                        current = para
            if current:
                chunks.append(current)
    return [c for c in chunks if len(c.strip()) >= 40]


# ── Main entry point ──────────────────────────────────────────────────────────

async def ingest_file(
    path: str,
    title: str,
    category: str,
    embed_model: str,
) -> tuple[str, int]:
    """Extract, chunk, embed and store a document. Returns (book_id, chunk_count)."""
    from library.store import embed_texts, add_chunks

    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    book_id = str(uuid.uuid4())

    logger.info("[ingest] extracting %s", path)
    sections = extract_text(path)
    if not sections:
        raise ValueError("No text could be extracted from this file")

    chunks = chunk_sections(sections)
    if not chunks:
        raise ValueError("File produced no usable text chunks after processing")

    logger.info("[ingest] %d chunks → embedding with %s", len(chunks), embed_model)
    embeddings = await embed_texts(chunks, model=embed_model)

    add_chunks(
        book_id=book_id,
        chunks=chunks,
        embeddings=embeddings,
        title=title,
        category=category,
        source_path=path,
    )
    logger.info("[ingest] done: book_id=%s chunks=%d", book_id[:8], len(chunks))
    return book_id, len(chunks)
