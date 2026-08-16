# CHANGELOG


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
