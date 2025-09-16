from __future__ import annotations

import hashlib
from typing import Iterable


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def chunk_text(text: str, min_tokens: int = 80, max_tokens: int = 600) -> list[str]:
    # Упрощённый чанкер по абзацам; токены ~ слова
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    count = 0
    for p in paragraphs:
        tokens = p.split()
        if count + len(tokens) <= max_tokens:
            cur.append(p)
            count += len(tokens)
        else:
            if count >= min_tokens:
                chunks.append("\n\n".join(cur))
            cur = [p]
            count = len(tokens)
    if cur and count >= min_tokens:
        chunks.append("\n\n".join(cur))

    # Quality gates: no-empty, dedup
    seen = set()
    uniq: list[str] = []
    for c in chunks:
        h = text_hash(c)
        if h in seen:
            continue
        seen.add(h)
        uniq.append(c)
    if uniq:
        return uniq

    # Fallback: если не удалось набрать достаточные чанки, создаём один усечённый чанк
    words = text.split()
    if len(words) >= max(min_tokens // 2, 40):
        return [" ".join(words[:max_tokens])]
    return []


