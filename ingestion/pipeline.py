from __future__ import annotations

from typing import Any
from loguru import logger
from tqdm import tqdm
from ingestion.crawler import crawl, crawl_mkdocs_index, crawl_sitemap
from ingestion.parsers import parse_api_documentation, parse_release_notes, parse_faq_content, parse_guides
from ingestion.chunker import chunk_text, text_hash
from ingestion.indexer import upsert_chunks


def classify_page(url: str) -> str:
    low = url.lower()
    if "faq" in low:
        return "faq"
    if "api" in low:
        return "api"
    if "release" in low or "changelog" in low:
        return "release_notes"
    return "guide"


def crawl_and_index(incremental: bool = True) -> dict[str, Any]:
    """Полный цикл: краулинг → чанкинг → эмбеддинги → upsert в Qdrant.
    incremental: если True — в будущем можно сравнивать hash и пропускать неизменённые.
    Возвращает статистику по страницам и чанкам.
    """
    # 0) Если есть sitemap.xml — соберём список URL и скачаем обычным HTTP
    urls = crawl_sitemap()
    pages: list[dict] = []
    if urls:
        for u in urls:
            try:
                sub = crawl(start_url=u, strategy="jina")
                pages.extend(sub)
            except Exception:
                pass
    # 1) Фолбэк: если sitemap пуст, возьмём корень через Jina
    if not pages:
        pages = crawl(strategy="jina")
    if not pages:
        # 2) MkDocs index
        pages = crawl_mkdocs_index()
    if not pages:
        # 3) Фолбэк: браузерный обход
        pages = crawl(strategy="browser")
    total_chunks = 0
    with tqdm(total=len(pages), desc="Indexing") as pbar:
        for p in pages:
            url = p["url"]
            html = p.get("html") or ""
            raw_text = p.get("text")
            page_type = classify_page(url)

            # Извлечение основного текста (упрощённо для старта)
            if raw_text:
                text = raw_text
                title = p.get("title")
            else:
                parsed = parse_guides(html)
                text = parsed.get("text") or html
                title = parsed.get("title")
            chunks_text = chunk_text(text)
            chunks = []
            for ct in chunks_text:
                chunks.append({
                    "text": ct,
                    "payload": {
                        "url": url,
                        "page_type": page_type,
                        "source": "docs-site",
                        "language": "ru",
                        "title": title,
                        "text": ct,
                    },
                })
            total_chunks += upsert_chunks(chunks)
            pbar.update(1)
    return {"pages": len(pages), "chunks": total_chunks}


