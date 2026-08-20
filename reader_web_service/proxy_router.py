"""Host-aware dual-proxy selector used by HTTP helpers and Firefox configuration.

The module fetches proxy configuration lazily at call time so it can be
re-loaded during tests without importing side-effects.

Ported from TGRSSReaderBot's ``contrib.proxy_router`` — logic is identical,
only the config import path changes (``reader_web_service.config`` instead of
``contrib.config``).
"""
from urllib.parse import urlparse


class NoProxyError(RuntimeError):
    """Raised when a proxy is required but none is available."""


def _normalise_host(host: str) -> str:
    """Lower-case, strip ``user@``, strip ``:port``."""
    host = host.lower()
    if '@' in host:
        host = host.rsplit('@', 1)[-1]
    if ':' in host:
        host = host.split(':', 1)[0]
    return host


def get_proxy_for_host(host: str) -> str | None:
    """Return a proxy URL for *host*.

    Priority:
    1. If *host* is in ``PROXY_WHITELIST_HOSTS`` and ``PROXIES`` is defined —
       return the next value from the cycle.
    2. If ``TOR_PROXY`` is defined — return it.
    3. If ``PROXIES`` defined — return the next proxy from the cycle.
    4. If ``REQUIRE_PROXY`` — raise :class:`NoProxyError`.
    5. ``None`` — direct connection.
    """
    import reader_web_service.config as config

    host = _normalise_host(host)
    whitelist = {
        _normalise_host(h.strip())
        for h in (config.PROXY_WHITELIST_HOSTS or '').split(',')
        if h.strip()
    }

    if host in whitelist and config.PROXIES:
        return next(config.PROXIES)
    if config.TOR_PROXY:
        return config.TOR_PROXY
    if config.PROXIES:
        return next(config.PROXIES)
    if config.REQUIRE_PROXY:
        raise NoProxyError(f'Proxy required but none available for host {host}')
    return None


def get_proxy_for_url(url: str) -> str | None:
    """Parse *url* and delegate to :func:`get_proxy_for_host`."""
    return get_proxy_for_host(urlparse(url).hostname or '')
