# Build stage
FROM python:3.13 AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY reader_web_service ./reader_web_service
COPY README.md ./
RUN uv sync --frozen --no-dev

# Runtime stage: camoufox browser + Tor
FROM python:3.13-slim AS runner

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation libayatana-appindicator3-1 libasound2t64 \
    libatk-bridge2.0-0t64 libatk1.0-0t64 libgtk-3-0t64 \
    libnspr4 libnss3 lsb-release xdg-utils libxss1 libdbus-glib-1-2 \
    libx11-xcb1 curl unzip wget xvfb xz-utils \
    tor obfs4proxy tini netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/tor /var/lib/tor /var/log/tor \
    && chown -R root:root /var/lib/tor /var/log/tor

WORKDIR /app
COPY --from=builder /app /app

# Fetch the camoufox browser binary into the image (~633MB layer, cached by buildx).
# Must run after the builder copy — the venv from the builder provides `camoufox`.
RUN python -m camoufox fetch

COPY torrc /etc/tor/torrc
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod 0644 /etc/tor/torrc \
    && chmod 0755 /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "reader_web_service:app", "--host", "0.0.0.0", "--port", "8095"]
