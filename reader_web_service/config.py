"""Proxy and application configuration — read lazily at import time from env vars.

Mirrors the proxy config pattern from TGRSSReaderBot's ``contrib.config``:
``PROXIES`` is a comma-separated list turned into an ``itertools.cycle`` for
round-robin selection; ``TOR_PROXY`` is the local Tor SOCKS5 default;
``PROXY_WHITELIST_HOSTS`` routes specific hosts through ``PROXIES`` instead of
Tor; ``REQUIRE_PROXY`` forces every request through a proxy.
"""
import os
from itertools import cycle

if PROXIES := os.getenv('PROXIES'):
    PROXIES = cycle(PROXIES.split(','))
TOR_PROXY = os.getenv('TOR_PROXY', 'socks5h://127.0.0.1:9050')
PROXY_WHITELIST_HOSTS = os.getenv('PROXY_WHITELIST_HOSTS', '')
REQUIRE_PROXY = os.getenv('REQUIRE_PROXY', '1') == '1'
