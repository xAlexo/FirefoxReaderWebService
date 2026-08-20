# FirefoxReaderWebService

FastAPI web service that uses headless Firefox (via Selenium) to scrape web pages through Firefox's built-in Reader Mode or as raw HTML. Runs inside Docker with Tor for anonymity.

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /?url=<url>` | Reader mode — returns `{title, html}` parsed via Readability.js |
| `GET /html?url=<url>` | Raw HTML — returns `{title, html}` without reader parsing |
| `GET /ping` | Health check — opens example.com via Firefox, returns `{status: ok/error}` |

## Docker

```bash
docker build -t firefox-reader-web-service .
docker run -e SENTRY_DSN=<dsn> -p 8095:8095 firefox-reader-web-service
```

Published to `ghcr.io/xalexo/firefoxreaderwebservice:latest` on every release tag.

## Tor Configuration

The service runs Tor inside the container (not a sidecar). Firefox always routes through the local Tor SOCKS5 proxy (`127.0.0.1:9050`). Tor's own OR-connections can optionally bootstrap through an external SOCKS5 proxy via `PROXIES`.

| Variable | Description | Default |
|---|---|---|
| `SENTRY_DSN` | Sentry DSN for error tracking | — |
| `TOR_PROXY` | Local Tor SOCKS5 — proxy for all Firefox requests | `socks5h://127.0.0.1:9050` |
| `PROXIES` | External SOCKS5 (comma-separated, round-robin). Used for Tor bootstrap (`Socks5Proxy` in torrc) | — |
| `PROXY_WHITELIST_HOSTS` | Hosts (comma-separated) routed through `PROXIES` instead of `TOR_PROXY` | — |
| `REQUIRE_PROXY` | `1` = every request must go through a proxy, else `NoProxyError` | `1` |
| `USE_BRIDGES` | `1` = enable obfs4 Tor bridges | `0` |
| `TOR_BRIDGE_1`..`TOR_BRIDGE_10` | obfs4 bridge lines: `obfs4 <ip>:<port> <fingerprint> cert=<cert> iat-mode=0` | — |
| `BOOTSTRAP_TIMEOUT_SECONDS` | Tor bootstrap timeout | `120` |

### Minimal deployment

```env
SENTRY_DSN=https://your-dsn@host/1
PROXIES=socks5h://external-proxy:1080
```

### With Tor bridges (censored networks)

```env
USE_BRIDGES=1
TOR_BRIDGE_1=obfs4 1.2.3.4:443 <fingerprint> cert=<cert> iat-mode=0
```

## Development

```bash
uv sync --no-dev
uv run uvicorn reader_web_service:app --host 0.0.0.0 --port 8095
```

Requires Firefox and geckodriver installed and on `PATH`. The Docker image handles this automatically.
