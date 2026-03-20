# ── Стадия 1: сборка зависимостей ─────────────────────────────────
FROM python:3.11-slim AS deps

WORKDIR /app

# gcc нужен для компиляции asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Отдельный слой для requirements — кэшируется пока файл не меняется
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Стадия 2: финальный образ (без build-tools) ────────────────────
FROM python:3.11-slim

WORKDIR /app

# libpq нужна для asyncpg в runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Копируем только установленные пакеты — без gcc и компиляторов
COPY --from=deps /usr/local/lib/python3.11/site-packages \
                 /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Исходный код
COPY src/ ./src/
COPY scripts/ ./scripts/

# Директория для логов (volume монтируется снаружи)
RUN mkdir -p /app/logs

# Не запускаем под root
RUN useradd -m -u 1000 teatr && chown -R teatr:teatr /app
USER teatr

CMD ["python", "-m", "src.main"]
