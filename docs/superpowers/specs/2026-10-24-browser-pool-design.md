# Persistent browser pool design

## Intent

Firefox Reader launches a Camoufox browser for every request. Concurrent launches have caused browser-driver failures, while the service receives repeated full-text requests from rss-reader. Reuse a small number of browsers to reduce launch churn and make `/ping` validate the real fetch path through the same pool.

## Goals

- Keep three browser workers by default, each with one Camoufox browser owned by one OS thread.
- Reuse a worker's browser between requests; create and close a fresh page for every request.
- Keep a bounded queue of three waiting requests and a 30-second queue timeout. Preserve HTTP 503 and `Retry-After: 30` when saturated.
- Retry operational Playwright failures up to three times, discarding a failed browser before retrying.
- Keep current error behavior: operational Playwright failures are not sent to Sentry; unexpected exceptions are captured once and return `None`.
- Recycle a browser after 200 handled requests to limit long-lived browser state.
- Allow `BROWSER_POOL_SIZE` to override the default; reject non-positive values.
- Start and stop the pool through FastAPI lifespan. `/ping` continues to navigate to `https://example.com` through the pool.
- Preserve endpoint response shapes and existing proxy configuration.

## Non-goals

- Increasing the default concurrency beyond three.
- Rewriting the service around async Playwright or changing rss-reader retry behavior.
- Adding runtime metrics, browser pooling dependencies, or production-network tests.

## Design decisions

- A bounded `queue.Queue` feeds dedicated worker threads. This preserves Playwright thread affinity and bounds waiting work.
- A worker keeps its Camoufox context manager open and calls `browser.new_page()` for each request. It closes the page after use; this keeps request page state isolated.
- Queue timeout only applies until a worker starts a job. Once started, existing navigation/readability timeouts govern the request.
- A browser's proxy is selected at launch and stays fixed until that browser is recycled. The default Tor proxy is unchanged. When fallback proxy rotation is configured, rotation therefore happens per browser launch/recycle rather than per request.
- Shutdown stops accepting work, drains already queued jobs, closes each browser in its owner thread, and joins workers.

## Constraints and risks

- The current Compose file declares 1 GiB and 1 CPU, while the running Dokploy container reports 4 GiB and 8 CPUs. Keep pool size at three for this change, but reconcile those deployment limits before changing concurrency.
- Camoufox is synchronous. No test may launch a real browser or make a real network request; use fakes for the pool and endpoint tests.
- If browser proxy rotation must occur on every request, browsers need a different proxy-switching design; this pool intentionally keeps each browser's proxy for up to 200 requests.

## Acceptance

All existing route contracts remain unchanged. Mock-based tests prove browser reuse, per-request page closure, operational retry/replacement, unexpected-error reporting, recycling, bounded queue behavior, timeout/cancellation behavior, and lifespan shutdown.
