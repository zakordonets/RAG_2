from __future__ import annotations

from typing import Any
import requests
import telegramify_markdown
from app.config import CONFIG


DEFAULT_LLM = CONFIG.default_llm


def _yandex_complete(prompt: str, max_tokens: int = 800) -> str:
    url = f"{CONFIG.yandex_api_url}/text:generate"
    headers = {
        "Authorization": f"Api-Key {CONFIG.yandex_api_key}",
        "x-folder-id": CONFIG.yandex_catalog_id,
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gpt://{CONFIG.yandex_catalog_id}/{CONFIG.yandex_model}",
        "maxTokens": str(min(max_tokens, CONFIG.yandex_max_tokens)),
        "temperature": 0.2,
        "texts": [prompt],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # Ответ Yandex может отличаться; извлекаем текст первой альтернативы
    try:
        return data["result"]["alternatives"][0]["text"]
    except Exception:
        return str(data)


def _gpt5_complete(prompt: str, max_tokens: int = 800) -> str:
    if not CONFIG.gpt5_api_url or not CONFIG.gpt5_api_key:
        raise RuntimeError("GPT-5 creds are not set")
    headers = {"Authorization": f"Bearer {CONFIG.gpt5_api_key}", "Content-Type": "application/json"}
    payload = {"model": CONFIG.gpt5_model or "gpt5", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    resp = requests.post(CONFIG.gpt5_api_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return str(data)


def _deepseek_complete(prompt: str, max_tokens: int = 800) -> str:
    headers = {"Authorization": f"Bearer {CONFIG.deepseek_api_key}", "Content-Type": "application/json"}
    payload = {"model": CONFIG.deepseek_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    resp = requests.post(CONFIG.deepseek_api_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return str(data)


def _format_for_telegram(text: str) -> str:
    """Форматирует текст для красивого отображения в Telegram используя telegramify-markdown."""
    try:
        # Добавляем эмодзи для разделов перед конвертацией
        if "Быстрый старт" in text:
            text = text.replace("Быстрый старт", "🚀 Быстрый старт")
        if "Администрирование" in text:
            text = text.replace("Администрирование", "⚙️ Администрирование")
        if "Мониторинг" in text:
            text = text.replace("Мониторинг", "📊 Мониторинг")
        if "Настройка" in text:
            text = text.replace("Настройка", "🔧 Настройка")
        if "Создание" in text:
            text = text.replace("Создание", "➕ Создание")
        if "Интеграция" in text:
            text = text.replace("Интеграция", "🔗 Интеграция")
        if "Дополнительные" in text:
            text = text.replace("Дополнительные", "⚡ Дополнительные")
        
        # Конвертируем markdown в Telegram MarkdownV2
        formatted = telegramify_markdown.markdownify(text)
        return formatted
    except Exception as e:
        # Если конвертация не удалась, возвращаем исходный текст с базовым форматированием
        print(f"Telegram formatting error: {e}")
        # Простое форматирование без MarkdownV2
        text = text.replace("**", "*")  # Жирный текст
        text = text.replace("### ", "🔹 ")  # Заголовки
        text = text.replace("## ", "🔸 ")  # Заголовки
        text = text.replace("# ", "🔸 ")  # Заголовки
        return text


def generate_answer(query: str, context: list[dict], policy: dict[str, Any] | None = None) -> str:
    """
    Генерирует ответ, используя провайдер LLM согласно DEFAULT_LLM и fallback-порядку.
    - Формирует промпт с источниками (URL) и указанием добавлять "Подробнее".
    - Порядок: DEFAULT_LLM -> GPT5 -> DEEPSEEK.
    - Обрабатывает сетевые ошибки, возвращая следующее доступное решение.
    """
    policy = policy or {}
    # Формируем промпт с цитатами и ссылками «Подробнее»
    sources = []
    for c in context:
        url = (c.get("payload", {}) or {}).get("url")
        title = (c.get("payload", {}) or {}).get("title")
        if url:
            sources.append(f"- {title or 'Источник'}: {url}")
    sources_block = "\n".join(sources)
    prompt = (
        "Вы — ассистент по edna Chat Center. Используйте только предоставленный контекст.\n"
        "Отвечайте структурировано с заголовками, списками и ссылками.\n"
        "Используйте markdown форматирование: **жирный текст**, ### заголовки, * списки.\n"
        "В конце добавьте ссылку 'Подробнее' на основную страницу документации.\n"
        f"Вопрос: {query}\n\nКонтекст:\n{sources_block}\n"
    )

    order = [DEFAULT_LLM, "GPT5", "DEEPSEEK"]
    for provider in order:
        try:
            if provider == "YANDEX":
                answer = _yandex_complete(prompt)
                return _format_for_telegram(answer)
            if provider == "GPT5":
                answer = _gpt5_complete(prompt)
                return _format_for_telegram(answer)
            if provider == "DEEPSEEK":
                answer = _deepseek_complete(prompt)
                return _format_for_telegram(answer)
        except Exception:
            continue
    return "Извините, провайдеры LLM недоступны. Попробуйте позже."


