# RAG-система для edna Chat Center

Интеллектуальный помощник на базе RAG (Retrieval-Augmented Generation) для технической поддержки продукта edna Chat Center. Система использует векторный поиск по документации и генерацию ответов с помощью LLM.

## 🚀 Возможности

- **Многоканальность**: Поддержка Telegram и готовность к другим каналам
- **Гибридный поиск**: Комбинация dense и sparse эмбеддингов с RRF fusion
- **Умная маршрутизация**: Автоматический fallback между LLM провайдерами
- **Красивое форматирование**: MarkdownV2 с эмодзи и структурированными ответами
- **Production-ready**: Comprehensive error handling, кэширование, Circuit Breaker
- **Безопасность**: Валидация и санитизация входных данных
- **Мониторинг**: Prometheus метрики и детальное логирование
- **Надежность**: Graceful degradation и автоматическое восстановление

## 🏗️ Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │   Web Interface │    │   Other Channels│
│   (Long Polling)│    │   (Future)      │    │   (Future)      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      Channel Adapters     │
                    │   (Telegram, Web, etc.)   │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │        Core API           │
                    │    (Flask + RESTful)      │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     Query Processing      │
                    │ (Entity Extraction, etc.) │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      Embeddings          │
                    │  (Dense + Sparse BGE-M3) │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      Vector Search        │
                    │    (Qdrant + Hybrid)      │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │       Reranking          │
                    │   (BGE-reranker-v2-m3)   │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      LLM Router          │
                    │ (YandexGPT, GPT-5, etc.) │
                    └───────────────────────────┘
```

## 📋 Требования

### Системные требования
- Python 3.11+
- Docker (для Qdrant)
- 8GB+ RAM (рекомендуется)
- 2GB+ свободного места

### API ключи
- YandexGPT API ключ
- Deepseek API ключ (опционально)
- GPT-5 API ключ (опционально)
- Telegram Bot Token

## 🛠️ Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd RAG_2
```

### 2. Создание виртуального окружения
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка окружения
```bash
cp env.example .env
# Отредактируйте .env файл с вашими API ключами
```

### 5. Запуск сервисов

#### Qdrant (векторная база данных)
```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

#### Sparse Embeddings Service (опционально)
```bash
cd sparse_service
python app.py
```

### 6. Инициализация базы данных
```bash
python scripts/init_qdrant.py
```

### 7. Индексация документации
```bash
python -c "from ingestion.pipeline import crawl_and_index; crawl_and_index()"
```

### 8. Запуск системы

#### Flask API
```bash
python wsgi.py
```

#### Telegram Bot
```bash
python adapters/telegram_polling.py
```

## 🔧 Конфигурация

### Основные настройки (.env)

```env
# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_api_key

# LLM провайдеры
YANDEX_API_KEY=your_yandex_key
DEEPSEEK_API_KEY=your_deepseek_key
GPT5_API_KEY=your_gpt5_key

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# Эмбеддинги
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DIM=1024

# Поиск
HYBRID_DENSE_WEIGHT=0.7
HYBRID_SPARSE_WEIGHT=0.3
RERANK_TOP_N=10
```

### Настройка краулера

```env
CRAWL_START_URL=https://docs-chatcenter.edna.ru/
CRAWL_STRATEGY=jina  # jina, browser, http
CRAWL_TIMEOUT_S=30
CRAWL_MAX_PAGES=1000
```

## 📊 API Endpoints

### Chat API
- `POST /v1/chat/query` - Обработка запросов пользователей с валидацией

### Admin API
- `GET /v1/admin/health` - Проверка состояния системы с Circuit Breakers
- `POST /v1/admin/reindex` - Переиндексация документации

### Мониторинг
- `GET /v1/admin/metrics` - Метрики Prometheus в JSON
- `GET /v1/admin/metrics/raw` - Сырые метрики Prometheus
- `GET /v1/admin/circuit-breakers` - Состояние Circuit Breakers
- `GET /v1/admin/cache` - Статистика кэша

## 🧪 Тестирование

### Тест API
```bash
curl -X POST http://localhost:9000/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"message": "Как настроить маршрутизацию?"}'
```

### Тест Telegram бота
1. Найдите бота в Telegram: `@edna_cc_bot`
2. Отправьте сообщение: "Привет"
3. Проверьте ответ

## 📈 Мониторинг

### Логи
Система использует `loguru` для структурированного логирования:
- Время обработки каждого этапа
- Ошибки и предупреждения с контекстом
- Статистика запросов и производительности

### Prometheus метрики
- `rag_queries_total` - количество запросов по каналам и статусам
- `rag_query_duration_seconds` - длительность этапов обработки
- `rag_embedding_duration_seconds` - время создания эмбеддингов
- `rag_search_duration_seconds` - время поиска
- `rag_llm_duration_seconds` - время генерации LLM
- `rag_cache_hits_total` - попадания в кэш
- `rag_errors_total` - ошибки по типам и компонентам

### HTTP сервер метрик
- Порт: 8000
- Endpoint: `http://localhost:8000/metrics`
- Совместимость с Grafana и другими системами мониторинга

## 🔄 Обновление данных

### Автоматическое обновление
```bash
# Переиндексация всей документации
curl -X POST http://localhost:9000/v1/admin/reindex
```

### Инкрементальное обновление
```python
from ingestion.pipeline import crawl_and_index
crawl_and_index(incremental=True)
```

## 🚀 Развертывание

### Docker (рекомендуется)
```bash
docker-compose up -d
```

### Production настройки
- Используйте Gunicorn вместо Flask dev server
- Настройте reverse proxy (Nginx)
- Включите HTTPS
- Настройте мониторинг (Prometheus + Grafana)

## 🔧 Критические исправления

Система прошла комплексную модернизацию для production-ready развертывания:

### ✅ Исправленные проблемы
- **Comprehensive Error Handling** - обработка ошибок на каждом этапе
- **Исправлен Hybrid Search** - корректная работа sparse векторов в Qdrant
- **Валидация и санитизация** - защита от XSS и инъекций
- **Кэширование** - Redis + in-memory fallback для производительности
- **Circuit Breaker** - защита от каскадных сбоев внешних сервисов
- **Prometheus метрики** - полный мониторинг системы

### 📊 Новые возможности
- Детальные метрики производительности
- Автоматическое восстановление при сбоях
- Graceful degradation при ошибках
- Полная валидация входных данных
- Кэширование для ускорения ответов

Подробнее: [docs/critical_fixes.md](docs/critical_fixes.md)

## 🛠️ Разработка

### Структура проекта
```
├── adapters/           # Адаптеры каналов (Telegram, Web)
├── app/               # Core API (Flask)
│   ├── routes/        # API endpoints
│   └── services/      # Бизнес-логика
├── ingestion/         # Парсинг и индексация
├── sparse_service/    # Сервис sparse эмбеддингов
├── scripts/           # Утилиты
└── docs/             # Документация
```

### Добавление нового канала
1. Создайте адаптер в `adapters/`
2. Реализуйте интерфейс `ChannelAdapter`
3. Добавьте конфигурацию

### Добавление нового LLM
1. Добавьте функцию в `app/services/llm_router.py`
2. Обновите fallback порядок
3. Добавьте конфигурацию

## 🐛 Устранение неполадок

### Частые проблемы

#### Timeout ошибки
- Увеличьте `CRAWL_TIMEOUT_S`
- Проверьте доступность API

#### Ошибки форматирования
- Проверьте MarkdownV2 синтаксис
- Используйте fallback режим

#### Проблемы с эмбеддингами
- Проверьте доступность Ollama
- Убедитесь в правильности модели

### Логи
```bash
# Просмотр логов Flask
tail -f logs/flask.log

# Просмотр логов Telegram бота
tail -f logs/telegram.log
```

## 📝 Лицензия

MIT License

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📞 Поддержка

- Документация: [docs/](docs/)
- Issues: [GitHub Issues](https://github.com/your-repo/issues)
- Email: support@example.com

## 🎯 Roadmap

- [ ] Web интерфейс
- [ ] Поддержка других мессенджеров
- [ ] A/B тестирование ответов
- [ ] Аналитика использования
- [ ] Многоязычность
- [ ] Voice интерфейс
