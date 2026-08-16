# Copilot Instructions

## Architecture

This is a FastAPI web service that uses headless Firefox (via Selenium) to scrape web pages — either through Firefox's built-in Reader Mode (`about:reader?url=...`) or as raw HTML. The service runs inside Docker with geckodriver and Firefox installed.

**Request flow:**
1. Client calls `GET /?url=<url>` (reader mode) or `GET /html?url=<url>` (raw HTML)
2. FastAPI offloads the blocking Selenium call to a thread executor (`loop.run_in_executor`)
3. `read_by_firefox()` in `reader_web_service/read_by_firefox.py` opens a headless Firefox instance, navigates to the URL, and extracts `title` + `content` HTML
4. Returns `{"title": "...", "html": "..."}` or `{"error": "reader not found"}` with HTTP 400

**Reader mode quirk:** Before opening the target URL, the browser first navigates to `http://<public-ip>/` (resolved via `ifconfig.me`). This appears to be a workaround for certain network routing issues.

**Key dependencies:** FastAPI + Uvicorn, Selenium (Firefox/geckodriver), Sentry SDK (exception tracking), Pyroscope (profiling).

## Environment Variables

| Variable | Description |
|---|---|
| `SENTRY_DSN` | **Required at startup** — Sentry DSN for error tracking |

Pyroscope is hardcoded to `http://my-pyroscope-server:4040`.

## Running Locally

Install dependencies with uv:
```bash
uv sync --no-dev
```

Run the service:
```bash
uv run uvicorn reader_web_service:app --host 0.0.0.0 --port 8095
```

Requires Firefox and geckodriver installed and on `PATH`. The Docker image handles this automatically.

## Docker

Build and run:
```bash
docker build -t firefox-reader-web-service .
docker run -e SENTRY_DSN=<dsn> -p 8095:8095 firefox-reader-web-service
```

Published to `ghcr.io/xalexo/firefox_reader_web_service:latest` on every push to `main`/`master` (via semantic release tagging).

## Release Process

Releases are automated via **Python Semantic Release** on push to `main`/`master`. Commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/) to trigger version bumps and CHANGELOG entries. The Docker image is built and pushed to GHCR only when a `v*.*.*` tag is created.

## Code Conventions

- Logging uses `loguru` imported as `_log` (not the standard `logging` module)
- Sentry exceptions are captured manually with `sentry_sdk.capture_exception(e)` in the `finally`/`except` blocks
- `read_by_firefox(url, reader=True)` — `reader=False` skips Firefox Reader Mode and returns raw page body
- Each HTTP request spawns a new Firefox instance; there is no browser pooling
