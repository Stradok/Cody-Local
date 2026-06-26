import logging
import os
import uuid

logger = logging.getLogger(__name__)


def _extract_pdf(path: str) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(text)
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

    chapters = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            html = item.get_content().decode("utf-8", errors="replace")
            text = h2t.handle(html).strip()
            if len(text) > 100:
                chapters.append(text)
    return chapters


def _extract_plaintext(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return [s.strip() for s in content.split("\n\n") if s.strip()]


def extract_text(path: str) -> list[str]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".epub":
        return _extract_epub(path)
    return _extract_plaintext(path)


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
