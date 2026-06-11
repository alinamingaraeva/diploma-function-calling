# Архитектурный паспорт проекта «Агент-консультант по сайту»

## 1. Диаграмма компонентов

flowchart LR
    USER["Клиент<br/>Telegram / Web"] --> GW["<b>API Gateway</b><br/>nginx / Telegram Bot API<br/>auth, rate limit (10 RPM)"]
    GW --> SVC["<b>Service</b><br/>FastAPI<br/>Bulkhead: asyncio.Semaphore(3)"]
    SVC --> CACHE["<b>Cache-Aside</b><br/>Redis, TTL 1h<br/>key: sha256(model + messages + temperature)"]
    CACHE -- "miss" --> LLM["<b>LLM слой</b><br/>Fallback chain:<br/>1. gpt-4o-mini (primary)<br/>2. deepseek<br/>3. gpt-4o<br/>4. Ollama (локально)<br/>Circuit Breaker (aiobreaker) на каждого провайдера"]
    CACHE -- "hit" --> SVC
    LLM --> EXT["<b>Провайдеры</b><br/>polza.ai (агрегатор)<br/>Ollama (локальный VPS)"]
    SVC --> DATA["<b>Data Layer</b><br/>Postgres: история диалогов,<br/>метрики, персональные данные (шифрование)<br/>Redis: кеш, сессии, rate limit counters"]

    style USER fill:#eef2ff,stroke:#6366f1,stroke-width:2px
    style GW fill:#ecfdf5,stroke:#10b981,stroke-width:2px
    style SVC fill:#eef2ff,stroke:#6366f1,stroke-width:2px
    style CACHE fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
    style LLM fill:#ecfdf5,stroke:#10b981,stroke-width:2px
    style DATA fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
    style EXT fill:#e5e7eb,stroke:#6b7280,stroke-width:2px
    
Условные обозначения

Точки отказоустойчивости: Circuit Breaker (на каждом провайдере), Fallback chain, Cache-Aside, Bulkhead.

Поток запроса: Клиент → Gateway → Service → Cache (если hit – сразу ответ) → при miss – LLM с fallback → сохранение в Postgres и Redis → ответ клиенту.

2. ADR (Architecture Decision Record)
ADR-001: Выбор паттерна взаимодействия
Status: Accepted (2026-06-11)

Context:
Проект – Telegram-бот для консультаций по сайту (поддержка, FAQ, ответы на вопросы клиентов). В 80% случаев ответ берётся из кеша (популярные вопросы), остальные требуют генерации LLM. Нагрузка: до 10 сообщений/мин в пик, средний ответ – 1–2 предложения (50–150 токенов, время генерации 1–3 секунды). Бюджет – низкий, но важен отзывчивый UX.

Decision:
Выбран Streaming с использованием Telegram editMessageText (паттерн «печатающий» бот). Каждый новый токен обновляет одно сообщение, создавая эффект реального времени.

Consequences:

Плюсы: первый токен появляется через 200–400 мс – пользователь видит, что бот «думает»; нет длительного молчания (плохо для чата); при ошибке генерации можно рано прервать и показать fallback.

Минусы: FastAPI держит соединение с LLM до окончания генерации (asyncio выдерживает сотни соединений); на уровне nginx нужно отключить proxy_buffering; требуется ограничить частоту editMessage (не более 1 раза в 0.2 с).

Alternatives considered:

Request-Response: отвергнут – задержка 1–3 секунд без обратной связи ухудшает UX, особенно при длинных ответах.

Queue-based: избыточен для интерактивного чата с низкой нагрузкой; добавляет сложность (polling) и задержку, не позволяет реализовать «печать» в реальном времени.

ADR-002: Стратегия fault tolerance (отказоустойчивость)
Status: Accepted (2026-06-11)

Context:
Бот использует polza.ai (агрегатор LLM) как основной шлюз, но возможны перегрузки, rate limits или ошибки отдельных моделей. Необходим fallback, чтобы сервис оставался доступен даже при частичных сбоях. Также есть локальная Ollama.

Decision:

Primary: gpt-4o-mini через polza.ai (дешёвый, быстрый, достаточен для FAQ).

Secondary: deepseek через polza.ai (тоже дешёвый, хорош для общих знаний).

Tertiary: gpt-4o через polza.ai (дорогой, высокое качество – используется редко).

Quaternary (last resort): локальная Ollama с моделью qwen3:32b (на VPS, на случай полного отказа облачных провайдеров).

Circuit Breaker:

По одному экземпляру aiobreaker на каждый провайдер.

Параметры: fail_max=3 ошибки подряд, timeout=30 секунд открытого состояния.

Отслеживаемые ошибки: RateLimitError, APIError, Timeout, 5xx.

Cache-Aside:

Redis, TTL = 1 час.

Ключ: sha256(model + messages + temperature).

В будущем планируется семантическое кеширование (по эмбеддингам), но в текущей версии – точное совпадение.

Bulkhead:

asyncio.Semaphore(3) на все LLM-вызовы (не более 3 одновременных генераций). Это защищает сервис от внутренней перегрузки.

Consequences:

Доступность: при отказе двух основных провайдеров включается локальная Ollama (медленнее, но сервис не падает).

Стоимость: дополнительные затраты на fallback-запросы незначительны (< $5/мес). Локальная Ollama бесплатна (расходы на VPS учтены).

Усложнение: необходимо поддерживать конфигурацию LiteLLM и скрипты запуска Ollama.

3. Потенциальные точки отказа и стратегии деградации
Слой	Что произойдёт при отказе	Паттерн смягчения	Как сервис деградирует (graceful degradation)
Gateway (Telegram API / nginx)	Telegram API недоступен или nginx не отвечает	Retry с backoff (tenacity)	Бот не отвечает. Пользователь видит таймаут. Через 5-10 минут retry восстанавливает.
Service (FastAPI)	Код упал (ошибка, OOM, нехватка памяти)	Рестарт оркестратором (docker / systemd), health checks	Пользователь получает 500, администратор – алерт.
LLM слой	Все провайдеры недоступны (маловероятно)	Fallback на шаблонный ответ: «Технические работы, попробуйте позже»	Сервис не генерирует новые ответы, но выдаёт предопределённую фразу. История не теряется.
Cache (Redis)	Redis недоступен	Кеширование отключается, запросы идут напрямую в LLM	Увеличение задержки и стоимости (но сервис жив).
Data Layer (Postgres)	Postgres не отвечает	История не сохраняется, но ответы возвращаются пользователю (логируем ошибку)	Клиент получает ответ, но диалог не сохранится (аналитика потеряется).
4. Ожидаемые нагрузки и метрики
RPM (пик): 10 запросов в минуту (из расчёта 50 новых клиентов в месяц, каждый задаёт 2–3 вопроса, плюс возвратные).

TPM (токенов в минуту): ~2000 (средний ответ 150 токенов, промпт 200 токенов).

Средний размер ответа: 1–2 предложения (50–150 токенов).

Бюджет: ~$5–10 в месяц (большинство запросов к gpt-4o-mini, кеш отсекает 50%).

Целевой cache hit rate: 50% (популярные вопросы).

Latency target: время до первого токена < 0.5 с, полный ответ < 3 с.

5. Использование LiteLLM как LLM Gateway
Для централизованного управления fallback, retry и Circuit Breaker выбран LiteLLM (open-source LLM Gateway).

Почему LiteLLM, а не самописный слой?

Готовые механизмы retry с экспоненциальным backoff, fallback-цепочек, circuit breaker.

Единый интерфейс OpenAI API для всех провайдеров – код не привязывается к конкретному вендору.

Легко менять веса и порядок провайдеров без переписывания кода (через config.yaml).

Встроенная поддержка кеширования (Redis) и балансировки нагрузки.

Конфигурация хранится в docs/liteLLM/config.yaml. В ней описаны 4 провайдера и fallback-цепочка gpt-4o-mini → deepseek → gpt-4o → ollama-qwen.

Локальный запуск прокси (для тестирования fallback):

bash
pip install 'litellm[proxy]'
export POLZA_API_KEY=sk-...   # или set POLZA_API_KEY=...
litellm --config ./docs/liteLLM/config.yaml --port 4000
Проверка переключения провайдера при ошибке primary (неверный API-ключ) подтверждает корректную работу fallback.
