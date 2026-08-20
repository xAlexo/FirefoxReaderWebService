# CHANGELOG


## v0.11.0 (2026-08-20)

### Documentation

- Add README with Tor configuration and deployment guide
  ([`656751d`](https://github.com/xAlexo/FirefoxReaderWebService/commit/656751d10a42ede8874c4af08060ce42e9439e20))

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-openagent)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

### Features

- Add .env.example with Tor proxy configuration template
  ([`3c0e268`](https://github.com/xAlexo/FirefoxReaderWebService/commit/3c0e2685fbef72e77228501d95c116120d001d6c))

Deployment template covering TOR_PROXY, PROXIES, PROXY_WHITELIST_HOSTS, REQUIRE_PROXY, USE_BRIDGES,
  TOR_BRIDGE_1..10, BOOTSTRAP_TIMEOUT_SECONDS.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-openagent)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>


## v0.10.1 (2026-08-20)

### Bug Fixes

- Copy README.md to builder stage for hatchling build
  ([`2842242`](https://github.com/xAlexo/FirefoxReaderWebService/commit/284224227c2c8b9945ee0a341b9ed7d95e0733f4))

pyproject.toml declares readme = README.md; hatchling fails with OSError if the file is missing
  during uv sync --frozen --no-dev.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-openagent)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>


## v0.10.0 (2026-08-20)

### Features

- Add compose.yaml with Tor proxy environment
  ([`5426161`](https://github.com/xAlexo/FirefoxReaderWebService/commit/542616100b453e1a5f63928e799825defc322c51))

Service with TOR_PROXY (default socks5h://127.0.0.1:9050), PROXIES for Tor bootstrap,
  REQUIRE_PROXY=1 by default, USE_BRIDGES, TOR_BRIDGE_1..10, BOOTSTRAP_TIMEOUT_SECONDS. Port 8095,
  1G RAM limit, logging rotation.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-openagent)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Add host-aware proxy router with config and tests
  ([`1417ad6`](https://github.com/xAlexo/FirefoxReaderWebService/commit/1417ad656808f306eda7e5efae07812c354e3ab6))

Ported from TGRSSReaderBot's contrib.proxy_router. Lazy config import allows test-time env
  overrides. REQUIRE_PROXY=1 by default — Firefox always routes through Tor, no direct connections.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-openagent)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Add Tor bootstrap entrypoint and torrc
  ([`02bcafd`](https://github.com/xAlexo/FirefoxReaderWebService/commit/02bcafdcbb148f2692a05575b5243d859dd3fb60))

Entrypoint starts Tor in background, blocks until Bootstrapped 100% + nc -z 9050, then launches the
  app. Supports obfs4 bridges via TOR_BRIDGE_1..10 (case-by-index, no eval) and Socks5Proxy from
  first PROXIES entry with self-loop guard. set +e around wait prevents Tor orphan on non-zero app
  exit.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-openagent)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Multi-stage Dockerfile with Tor, obfs4proxy, tini
  ([`ed7e4e8`](https://github.com/xAlexo/FirefoxReaderWebService/commit/ed7e4e82eb6edc792eecaa1b4c4e425d6cf00ce4))

Builder stage uses uv sync; runtime stage is python:3.13-slim with
  Firefox+geckodriver+tor+obfs4proxy+tini+netcat-openbsd. ENTRYPOINT is tini+entrypoint.sh, CMD runs
  uvicorn directly from venv (on PATH). .dockerignore excludes tests and caches.

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-openagent)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>

- Route Firefox through Tor SOCKS5 proxy
  ([`c8512ec`](https://github.com/xAlexo/FirefoxReaderWebService/commit/c8512ecbc941fad690474d7cb7788113a719a75e))

Replace module-level firefox_options with _build_options() that configures Firefox SOCKS5 proxy
  prefs from TOR_PROXY (network.proxy.socks + socks_remote_dns=true for socks5h equivalent). Firefox
  always routes through local Tor (127.0.0.1:9050 by default).

Ultraworked with [Sisyphus](https://github.com/code-yeongyu/oh-my-openagent)

Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>


## v0.9.0 (2026-08-20)

### Features

- Retry operational Selenium failures with fresh browser
  ([`84bdf13`](https://github.com/xAlexo/FirefoxReaderWebService/commit/84bdf13ffc6416bf30f9e10b67ba6673f4432927))

TimeoutException and NoSuchWindowException are transient — a fresh Firefox instance often succeeds.
  read_by_firefox now retries up to MAX_ATTEMPTS=3 times on operational failures, spinning up a new
  browser each attempt. Unexpected exceptions still hit Sentry once and return immediately (no
  retry).

- added MAX_ATTEMPTS constant - wrapped browser lifecycle in for attempt loop - operational except:
  log and continue to next attempt - unexpected except: sentry + return None (no retry) - 2 new
  tests: S4 timeout-then-success, S5 no-such-window-then-success - updated S1/S2: assert retries
  exhausted (quit called per attempt)


## v0.8.5 (2026-08-19)

### Bug Fixes

- Handle Selenium operational failures without Sentry noise
  ([`6f0c4fa`](https://github.com/xAlexo/FirefoxReaderWebService/commit/6f0c4fa8ee0001c6f237b465b3b70760466e5441))

Both Bugsink issues FIREFOX_READER_WEB_SERVICE-1 (ReadTimeoutError from browser.get hanging 120s)
  and -2 (NoSuchWindowException from discarded browsing context) shared one root cause:
  read_by_firefox treated every Selenium failure as a bug via a broad 'except Exception' that
  captured to Sentry, and never set an explicit page-load timeout.

- set_page_load_timeout(30) so slow pages fail fast instead of hanging for the geckodriver
  transport's 120s read timeout - catch TimeoutException + NoSuchWindowException explicitly:
  log+return None without Sentry capture (operational, not a bug) - keep the broad except for
  genuinely unexpected errors (Sentry capture) - pin the new behavior with 3 tests (RED->GREEN),
  regression guard for the unexpected-error path


## v0.8.4 (2026-08-16)

### Bug Fixes

- Trigger release after package deletion
  ([`f3e2cc0`](https://github.com/xAlexo/FirefoxReaderWebService/commit/f3e2cc0d600bca78106f97669c1698a650cb03ba))


## v0.8.3 (2026-08-16)

### Bug Fixes

- Use explicit lowercase image name for ghcr.io push
  ([`e34e374`](https://github.com/xAlexo/FirefoxReaderWebService/commit/e34e374e86cda9b61f5e6cc01f332c82360e7f7c))

github.repository (xAlexo/FirefoxReaderWebService) resolves to mixed-case which ghcr.io normalizes,
  but the existing package was created by a PAT and is not linked to this repo. Explicit lowercase
  matches the existing package name exactly.

### Chores

- Add __pycache__, *.pyc, .omo to .gitignore
  ([`c9a98c4`](https://github.com/xAlexo/FirefoxReaderWebService/commit/c9a98c481bd8d7cc445cbea9620034d786185246))


## v0.8.2 (2026-08-16)

### Bug Fixes

- Make pyroscope optional (Linux-only) and add dev dependencies
  ([`5579f1a`](https://github.com/xAlexo/FirefoxReaderWebService/commit/5579f1a50b6877a55554b788557ba1723687c372))

- pyroscope-io: add sys_platform=='linux' marker (no Windows wheels) - __main__.py: guard pyroscope
  import with try/except ImportError - add pytest + httpx to [dependency-groups] dev - enables local
  development and testing on Windows/macOS

- Reader mode via injected Readability.js instead of about:reader
  ([`a60ee6f`](https://github.com/xAlexo/FirefoxReaderWebService/commit/a60ee6fb521f07fea7f9a3971b9d60422c0b3364))

Firefox 153+ blocks WebDriver navigation to about:reader URLs (UnsupportedOperationError from
  Marionette driver.sys.mjs). Replace direct about:reader?url= navigation with: 1. Navigate to URL
  normally (browser.get) 2. Inject @mozilla/readability.js from CDN 3. Parse DOM with Readability
  (same lib Firefox uses internally)

Same result: {title, content} with <div class='page'> HTML. JS-rendered pages still work — Firefox
  executes JS in step 1.

### Testing

- Add unit tests for all FastAPI endpoints
  ([`17c5207`](https://github.com/xAlexo/FirefoxReaderWebService/commit/17c52075e30cb4567b601de9c9cbfbeeb72d6980))

6 tests covering /, /html, /ping — success and failure paths. Mocks read_by_firefox so no
  Firefox/Selenium needed to run tests. All 6 pass: uv run pytest tests/ -v


## v0.8.1 (2026-08-16)

### Bug Fixes

- Upgrade fastapi 0.111->0.141.1 to fix 7 starlette CVEs
  ([`a8ebd37`](https://github.com/xAlexo/FirefoxReaderWebService/commit/a8ebd37a4c6979fc6b1c7b263d2f21dc189e6255))

Dependabot alerts (all in starlette <1.3.1): - high: DoS via form() limits ignored (CVE in starlette
  >=0.4.1,<1.3.1) - high: SSRF/NTLM credential theft via UNC paths on Windows (<1.1.0) - high: DoS
  via multipart/form-data (<0.40.0) - medium: Host header poisoning -> request.url.path bypass
  (<=1.0.0) - medium: Arbitrary HTTP method dispatch via getattr (<1.1.0) - medium: DoS parsing
  large multipart files (<0.47.2) - low: Unvalidated request path -> hostname poisoning (<1.3.0)

starlette 0.37.2 -> 1.6.0, fastapi 0.111.1 -> 0.141.1

### Refactoring

- Merge ci.yml into release.yml as single workflow
  ([`cffa34e`](https://github.com/xAlexo/FirefoxReaderWebService/commit/cffa34e7ee245b40ce35bb28c3cf0d1414f87eb8))

- Semantic Release runs first, creates tag + release - Docker build+push runs only if release
  happened (released==true) - Docker uses GITHUB_TOKEN for ghcr.io (GH_TOKEN expired) - ci.yml
  deleted, no separate tag-triggered workflow needed


## v0.8.0 (2026-08-16)

### Bug Fixes

- Add trailing newline to Dockerfile
  ([`6b83d5f`](https://github.com/xAlexo/FirefoxReaderWebService/commit/6b83d5fd81d67a708eb572e757ffe7b6208c6929))

- Update Firefox deps for Debian Trixie and tar.xz download
  ([`7b313fd`](https://github.com/xAlexo/FirefoxReaderWebService/commit/7b313fdcc2cd52de464fd226d7701fbba3e516bb))

- apt: libasound2->libasound2t64, libatk-bridge2.0-0->libatk-bridge2.0-0t64 - apt:
  libappindicator3-1->libayatana-appindicator3-1 - apt: add libatk1.0-0t64, libgtk-3-0t64 (modern
  Firefox deps) - apt: drop redundant python3/python3-pip/python3-dev/python3-setuptools - Firefox
  download: tar.bz2->tar.xz (Mozilla switched format)

- Update release workflow for Node 24 compatibility
  ([`d88ad31`](https://github.com/xAlexo/FirefoxReaderWebService/commit/d88ad3132da847bb7dbbb20e509fe10ed2d0629b))

- actions/checkout@v3 -> @v4 (v3 deprecated, breaks auth on Node 24) -
  python-semantic-release@master -> @v9 (stable tag) - use GH_TOKEN consistently (was mixing
  GH_TOKEN and GITHUB_TOKEN)

- Use default GITHUB_TOKEN instead of expired GH_TOKEN secret
  ([`fdd3e79`](https://github.com/xAlexo/FirefoxReaderWebService/commit/fdd3e792c158620dde95a6c73aad7f74f8e35925))

### Chores

- Add pre-commit hooks and ruff linter
  ([`f46eb61`](https://github.com/xAlexo/FirefoxReaderWebService/commit/f46eb611d684f0b3fed1d853168e2102bef95434))

- .pre-commit-config.yaml: trailing-whitespace, end-of-file-fixer, check-merge-conflict, check-yaml,
  check-toml, check-added-large-files, debug-statements, check-docstring-first, ruff (--fix, no
  formatter), codespell - pyproject.toml: [tool.ruff] line-length=120, target py311, select
  E/F/I/W/UP, ignore BLE001 (sentry blind-except pattern)

- Migrate from Poetry to uv
  ([`a2b1aa3`](https://github.com/xAlexo/FirefoxReaderWebService/commit/a2b1aa367abf3b9d23bf41f10d3b3229f497a712))

- pyproject.toml: [tool.poetry] -> PEP 621 [project], hatchling backend - poetry.lock removed,
  uv.lock generated (66 packages) - Dockerfile: uv from ghcr.io/astral-sh/uv, two-stage sync
  --frozen --no-dev - .dockerignore: exclude .git/.github/.idea/.omo - copilot-instructions.md: uv
  sync --no-dev / uv run uvicorn

- Migrate to Python 3.13
  ([`b24ff76`](https://github.com/xAlexo/FirefoxReaderWebService/commit/b24ff7612dfb6aeddb79346dc2a2d1a0b5132346))

- pyproject.toml: requires-python >=3.13,<4.0, ruff target py313 - Dockerfile: FROM python:3.13 -
  uv.lock: regenerated (66 packages, old 3.11/3.12 markers removed)

### Features

- Add /ping health check endpoint
  ([`075eda4`](https://github.com/xAlexo/FirefoxReaderWebService/commit/075eda4d2ccde22633c57b9b0c7eed3e776a34f0))

Opens https://example.com via headless Firefox to verify the full
  Selenium+geckodriver+Firefox+network stack. Returns 200 {status:ok} on success, 500 {status:error}
  on failure.


## v0.7.6 (2025-01-01)

### Bug Fixes

- Открытие по ip
  ([`67e0ca9`](https://github.com/xAlexo/FirefoxReaderWebService/commit/67e0ca9f65fe4d70ad9496cd1f0dd745da798dd1))


## v0.7.5 (2025-01-01)

### Bug Fixes

- Больше логов
  ([`50c3628`](https://github.com/xAlexo/FirefoxReaderWebService/commit/50c3628a7c1180789b26d894b096d581ba6c2b56))


## v0.7.4 (2025-01-01)

### Bug Fixes

- Проверка DNS
  ([`a5402ad`](https://github.com/xAlexo/FirefoxReaderWebService/commit/a5402ad732e5d744ed4d19066f64eb02b56be1e9))


## v0.7.3 (2025-01-01)

### Bug Fixes

- Проверка DNS
  ([`e42cdc5`](https://github.com/xAlexo/FirefoxReaderWebService/commit/e42cdc5223113050071c3de4a5e38fd9791578ef))


## v0.7.2 (2025-01-01)

### Bug Fixes

- Попробовал убрать display
  ([`ef23e9d`](https://github.com/xAlexo/FirefoxReaderWebService/commit/ef23e9d582ec9cdcbd0d4fd9d7f2a15aeeb48837))


## v0.7.1 (2025-01-01)

### Bug Fixes

- Добавлен забытый пакет
  ([`8f8a1a7`](https://github.com/xAlexo/FirefoxReaderWebService/commit/8f8a1a787698ebcfd31e6874c847e195d117acb9))


## v0.7.0 (2025-01-01)

### Features

- Интегрирован sentry
  ([`19d15e1`](https://github.com/xAlexo/FirefoxReaderWebService/commit/19d15e1c0faab766ebd732771a2834cbfbb3abe5))


## v0.6.1 (2024-07-05)

### Bug Fixes

- Use email_from from secrets
  ([`4760887`](https://github.com/xAlexo/FirefoxReaderWebService/commit/4760887d635e403ff17894014cf4431de9c7293f))


## v0.6.0 (2024-07-05)

### Features

- Improve
  ([`5107bb6`](https://github.com/xAlexo/FirefoxReaderWebService/commit/5107bb6204ffe576853a027aa145de65a67244de))


## v0.5.0 (2024-02-23)

### Features

- Add pyroscope
  ([`d5ef397`](https://github.com/xAlexo/FirefoxReaderWebService/commit/d5ef397877e0edfd79f9e8103ab2747b9d398d4c))


## v0.4.5 (2024-02-12)

### Bug Fixes

- One timeout
  ([`7d49018`](https://github.com/xAlexo/FirefoxReaderWebService/commit/7d490187d15cd0084b851254478ded5f29c9d6a8))


## v0.4.4 (2024-02-12)

### Bug Fixes

- If render
  ([`ccf79a3`](https://github.com/xAlexo/FirefoxReaderWebService/commit/ccf79a324132fe42cce4de5b2ae64c3a0dc379ca))


## v0.4.3 (2024-02-12)

### Bug Fixes

- Find reader page content
  ([`be95cf8`](https://github.com/xAlexo/FirefoxReaderWebService/commit/be95cf8b80c21f9f74938950b107810d9f5e672b))


## v0.4.2 (2024-02-12)

### Bug Fixes

- Change wait time
  ([`7070c82`](https://github.com/xAlexo/FirefoxReaderWebService/commit/7070c820a40e9fb3f394643cf8ad702458cb7fc2))


## v0.4.1 (2024-02-12)

### Bug Fixes

- Not installed async-timeout
  ([`bcde65c`](https://github.com/xAlexo/FirefoxReaderWebService/commit/bcde65ca6ec53b39ca61062168399efc35665b8e))


## v0.4.0 (2024-02-12)

### Features

- Add async-timeout
  ([`64beb4a`](https://github.com/xAlexo/FirefoxReaderWebService/commit/64beb4ad33f58de8f1210af34659a2d0b8620f75))


## v0.3.3 (2024-02-12)

### Bug Fixes

- Return 400 if error
  ([`154a576`](https://github.com/xAlexo/FirefoxReaderWebService/commit/154a576e420aef90743723b9ab8bf2ca6f2273ab))


## v0.3.2 (2024-02-11)

### Bug Fixes

- Catch content not found
  ([`38f212d`](https://github.com/xAlexo/FirefoxReaderWebService/commit/38f212d7ecb2a552e0f88e021918528dd0c9a6f1))


## v0.3.1 (2024-02-08)

### Bug Fixes

- Get content from firefox
  ([`02297ad`](https://github.com/xAlexo/FirefoxReaderWebService/commit/02297ad2bcdfff1802cdd89b99a32a8fa454de5a))


## v0.3.0 (2024-01-05)

### Features

- Getting html without reading mode
  ([`fef5f7c`](https://github.com/xAlexo/FirefoxReaderWebService/commit/fef5f7c6c149643e9bad8d403d7cb588498f5157))


## v0.2.3 (2024-01-04)

### Bug Fixes

- Getting content
  ([`fa251d4`](https://github.com/xAlexo/FirefoxReaderWebService/commit/fa251d4f407ea2e493c9888b4b30341f756c35ef))


## v0.2.2 (2024-01-04)

### Bug Fixes

- Dockerfile
  ([`7505161`](https://github.com/xAlexo/FirefoxReaderWebService/commit/75051613f36bd2ec2458d0dd28e98c20a583378d))


## v0.2.1 (2024-01-04)

### Bug Fixes

- Add requirement
  ([`1cf5662`](https://github.com/xAlexo/FirefoxReaderWebService/commit/1cf5662981e914a7278b94a30e62a23e94b66f02))


## v0.2.0 (2024-01-04)

### Bug Fixes

- Update getting data from page
  ([`8109c9f`](https://github.com/xAlexo/FirefoxReaderWebService/commit/8109c9f373b4608d6f4569951a80409c93fa04f6))

### Features

- Update docker
  ([`edb722a`](https://github.com/xAlexo/FirefoxReaderWebService/commit/edb722ab800b7da564702c65ca88c22466d07c61))


## v0.1.0 (2024-01-04)

### Features

- Update geckodriver
  ([`a522f7e`](https://github.com/xAlexo/FirefoxReaderWebService/commit/a522f7e84b9eb94d1bd6ddfee52984db3b3bcf9e))


## v0.0.0 (2023-09-16)
