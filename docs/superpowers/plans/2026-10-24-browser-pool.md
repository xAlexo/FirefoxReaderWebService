# Persistent Browser Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse three thread-owned Camoufox browsers across requests while preserving route behavior and bounded backpressure.

**Architecture:** Extract a single-request browser operation, then run it from dedicated worker threads that each own a persistent Camoufox context. FastAPI lifespan owns the pool; its bounded queue preserves the existing 503 contract.

**Tech Stack:** Python 3.13, FastAPI lifespan, Camoufox synchronous API, `queue.Queue`, `threading`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-24-browser-pool-design.md`

## Global Constraints

- Keep three browser workers by default; `BROWSER_POOL_SIZE` overrides the default and non-positive values are rejected.
- Keep a maximum of three queued requests and a 30-second queue timeout; overloaded requests return HTTP 503 with `Retry-After: 30`.
- Retry operational Playwright failures up to three times, replacing a failed browser before retrying.
- Do not send operational Playwright failures to Sentry; capture unexpected exceptions once and return `None`.
- Recycle a browser after 200 handled requests.
- Preserve `/`, `/html`, `/ip`, and `/ping` response contracts; `/ping` remains a real browser navigation through the pool.
- Give every request a fresh page and close that page after use.
- Use fake browsers and mock endpoints only; do not launch the service or contact external sites.
- Add no dependencies.

## Review Focus

- A failed navigation must close and replace its browser before retrying; test an operational failure followed by success.
- An unexpected browser exception must still be captured once, while an operational Playwright exception must not be captured; test both paths.
- A queued caller that times out or is cancelled must not run later; test a blocked worker, queued job, and timeout/cancellation.
- The queue must reject work beyond three waiters while keeping active workers unaffected; test queue overflow and `Retry-After`.
- Browser reuse must not leak page state; test a distinct page per request and closure on success and exception.
- Shutdown must close browsers in their owner threads and drain accepted work; test lifespan start/stop without real browsers.
- Invalid `BROWSER_POOL_SIZE` must fail clearly; test zero, negative, and non-integer values.

---

### Task 1: Extract a single browser request operation

**Files:**
- Modify: `reader_web_service/read_by_firefox.py`
- Test: `tests/test_read_by_firefox.py`

**Interfaces:**
- Produces: `read_with_browser(browser, url, reader=True)`, which reads one page using an already-open browser, closes its page, and does not launch or retry a browser.
- Preserves: `read_by_firefox(url, reader=True)` for the standalone call path and existing launch/retry behavior.

- [ ] **Step 1: Add tests for `read_with_browser`** covering URL normalization, reader and raw HTML results, and page closure on success and Playwright failure.
- [ ] **Step 2: Run `uv run pytest tests/test_read_by_firefox.py -q` and confirm the new helper tests fail because the helper is absent.**
- [ ] **Step 3: Extract the page operation into `read_with_browser`; keep launch, retry, and Sentry handling in `read_by_firefox`.**
- [ ] **Step 4: Run `uv run pytest tests/test_read_by_firefox.py -q`; all tests must pass without real browser launches.**
- [ ] **Step 5: Commit as `refactor: extract reusable browser page reader`.**

### Task 2: Implement the persistent worker pool

**Files:**
- Create: `reader_web_service/browser_pool.py`
- Create: `tests/test_browser_pool.py`
- Consumes: `read_with_browser(browser, url, reader=True)` from Task 1.
- Produces: `BrowserPool(size=None)`, async `start()`, async `run(url, reader=True)`, async `shutdown()`, and `BrowserBusy`.

- [ ] **Step 1: Add fake-Camoufox tests for one-browser reuse across requests, fresh closed pages, retry after operational failure with browser replacement, Sentry behavior for operational and unexpected exceptions, and recycling after 200 requests.**
- [ ] **Step 2: Add fake-worker tests for queue capacity, 30-second wait timeout, cancelled queued jobs, invalid pool sizes, and shutdown closing browsers on their owner threads.**
- [ ] **Step 3: Run `uv run pytest tests/test_browser_pool.py -q` and confirm the tests fail because `BrowserPool` is absent.**
- [ ] **Step 4: Implement a bounded queue and dedicated workers; retain each browser context on its worker thread and bridge job results back to the event loop.**
- [ ] **Step 5: Run `uv run pytest tests/test_browser_pool.py -q`; all tests must pass without real browsers or network.**
- [ ] **Step 6: Commit as `feat: reuse Camoufox browsers in bounded pool`.**

### Task 3: Integrate the pool with FastAPI and document configuration

**Files:**
- Modify: `reader_web_service/__main__.py`
- Delete: `reader_web_service/browser_capacity.py`
- Modify: `tests/test_endpoints.py`
- Delete: `tests/test_browser_capacity.py`
- Modify: `README.md`
- Modify: `.env.example`
- Consumes: `BrowserPool` and `BrowserBusy` from Task 2.

- [ ] **Step 1: Update endpoint tests to inject a fake pool and assert existing response shapes, `/ping` fetch arguments, and HTTP 503 with `Retry-After: 30`.**
- [ ] **Step 2: Run `uv run pytest tests/test_endpoints.py -q` and confirm the integration assertions fail against the current capacity implementation.**
- [ ] **Step 3: Create and shut down `BrowserPool` in FastAPI lifespan; route all four endpoints through it and remove the old capacity limiter.**
- [ ] **Step 4: Document `BROWSER_POOL_SIZE` — the runtime code default remains 3; `.env.example` shows `1` for the declared low-memory Compose profile (1 GiB / 1 CPU), noting that pool sizes above one require measuring browser RSS under load and higher-limit deployments can override to 3. Update the browser-capacity description to persistent browsers.**
- [ ] **Step 5: Run `uv run pytest -q`; all tests must pass, with no real browser/network activity.**
- [ ] **Step 6: Commit as `feat: serve endpoints through persistent browser pool`.**
