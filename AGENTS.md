# Project guidance

This is a Python 3.13+ FastAPI service that uses Camoufox/Playwright and Tor to fetch pages, returning reader-parsed content or raw HTML. The ASGI application is `reader_web_service:app`; the package code is under `reader_web_service/` and tests are under `tests/`.

The README documents development with `uv sync --no-dev` followed by `uv run uvicorn reader_web_service:app --host 0.0.0.0 --port 8095`; fetching the Camoufox browser with `uv run python -m camoufox fetch` is also documented. Docker is the deployment path and includes Tor setup. Pytest discovers tests in `tests/` (`pytest.ini`).

Requests can cause real browser traffic through Tor or configured proxies; do not launch the service or exercise network-facing endpoints as a routine check. Configuration such as `SENTRY_DSN`, proxy settings, and Tor bridge lines belongs in environment/local deployment configuration, never committed values. Keep proxy-routing behavior and the `/`, `/html`, `/ip`, and `/ping` endpoint contracts covered when changing the service.

## Dokploy deployment

- The production Compose app is `firefox_reader_web_service` in Dokploy. Treat its Dokploy configuration as the live deployment.
- Keep proxy settings, Tor bridge lines, and monitoring credentials in the deployment environment. Never commit their values or Dokploy identifiers.
- Preserve the existing service configuration when changing the Compose deployment. Do not run a second production copy from a local checkout.
