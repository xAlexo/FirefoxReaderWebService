"""Tests for reader_web_service.proxy_router — host-aware dual-proxy selection.

TDD: written BEFORE implementation. MUST fail on import (RED) until
reader_web_service/proxy_router.py is created, then pass (GREEN).
"""
import importlib

import pytest


def _reload_config(monkeypatch, proxies='', tor_proxy='', whitelist='', require_proxy='0'):
    """Reload reader_web_service.config with given env values."""
    monkeypatch.setenv('PROXIES', proxies)
    monkeypatch.setenv('TOR_PROXY', tor_proxy)
    monkeypatch.setenv('PROXY_WHITELIST_HOSTS', whitelist)
    monkeypatch.setenv('REQUIRE_PROXY', require_proxy)
    import reader_web_service.config
    importlib.reload(reader_web_service.config)
    import reader_web_service.proxy_router
    importlib.reload(reader_web_service.proxy_router)
    return reader_web_service.proxy_router


def test_r1_no_proxy_returns_none_when_not_required(monkeypatch):
    """R1: PROXIES='', TOR_PROXY='', REQUIRE_PROXY=0 → returns None (direct allowed)."""
    pr = _reload_config(monkeypatch)
    assert pr.get_proxy_for_url('https://example.com/path') is None


def test_r2_no_proxy_raises_when_required(monkeypatch):
    """R2: same but REQUIRE_PROXY=1 → raises NoProxyError."""
    pr = _reload_config(monkeypatch, require_proxy='1')
    with pytest.raises(pr.NoProxyError):
        pr.get_proxy_for_url('https://example.com/path')


def test_r3_tor_proxy_default_when_no_whitelist_no_proxies(monkeypatch):
    """R3: TOR_PROXY set, no whitelist, no PROXIES → returns Tor URL for any host."""
    pr = _reload_config(monkeypatch, tor_proxy='socks5h://127.0.0.1:9050')
    assert pr.get_proxy_for_url('https://example.com') == 'socks5h://127.0.0.1:9050'


def test_r4_whitelisted_host_uses_proxies(monkeypatch):
    """R4: whitelisted host → returns a PROXIES entry (cycle)."""
    pr = _reload_config(monkeypatch, proxies='socks5h://1.2.3.4:1080', whitelist='api.github.com')
    assert pr.get_proxy_for_url('https://api.github.com/repos') == 'socks5h://1.2.3.4:1080'


def test_r5_non_whitelisted_host_uses_tor_proxy(monkeypatch):
    """R5: non-whitelisted host → returns TOR_PROXY, not PROXIES."""
    pr = _reload_config(monkeypatch, proxies='socks5h://1.2.3.4:1080', tor_proxy='socks5h://127.0.0.1:9050')
    assert pr.get_proxy_for_url('https://example.com') == 'socks5h://127.0.0.1:9050'


def test_r6_case_insensitive_port_stripped(monkeypatch):
    """R6: uppercase host + port → matches lowercase whitelist entry."""
    pr = _reload_config(monkeypatch, proxies='socks5h://1.2.3.4:1080', whitelist='api.github.com')
    assert pr.get_proxy_for_url('https://API.GITHUB.COM:443/x') == 'socks5h://1.2.3.4:1080'


def test_r7_get_proxy_for_host_matches_url(monkeypatch):
    """R7: get_proxy_for_host returns same as get_proxy_for_url for same host."""
    pr = _reload_config(monkeypatch, proxies='socks5h://1.2.3.4:1080', whitelist='api.github.com')
    assert pr.get_proxy_for_host('api.github.com') == pr.get_proxy_for_url('https://api.github.com/')


def test_r8_exact_host_only_no_suffix_match(monkeypatch):
    """R8: whitelist='github.com' does NOT match 'api.github.com' (exact only)."""
    pr = _reload_config(
        monkeypatch,
        proxies='socks5h://1.2.3.4:1080',
        tor_proxy='socks5h://127.0.0.1:9050',
        whitelist='github.com',
    )
    assert pr.get_proxy_for_url('https://api.github.com/') == 'socks5h://127.0.0.1:9050'


def test_r9_proxies_cycle_advances(monkeypatch):
    """R9: multi-entry PROXIES cycle advances on consecutive whitelisted calls."""
    pr = _reload_config(
        monkeypatch,
        proxies='socks5h://1.2.3.4:1080,socks5h://5.6.7.8:1080',
        whitelist='api.github.com',
    )
    first = pr.get_proxy_for_url('https://api.github.com/')
    second = pr.get_proxy_for_url('https://api.github.com/')
    assert {first, second} == {'socks5h://1.2.3.4:1080', 'socks5h://5.6.7.8:1080'}


def test_r10_no_proxy_error_is_exception():
    """R10: NoProxyError is a subclass of Exception."""
    try:
        import reader_web_service.proxy_router
        assert issubclass(reader_web_service.proxy_router.NoProxyError, Exception)
    except ImportError:
        pytest.fail('NoProxyError not importable — module not created yet (RED)')


def test_r11_whitelist_whitespace_stripped(monkeypatch):
    """R11: whitespace around whitelist entries is stripped so matching works.
    Regression: ' api.github.com , example.com' (spaces after comma) must match both hosts."""
    pr = _reload_config(monkeypatch, proxies='socks5h://1.2.3.4:1080', whitelist=' api.github.com , example.com ')
    assert pr.get_proxy_for_url('https://api.github.com/x') == 'socks5h://1.2.3.4:1080'
    assert pr.get_proxy_for_url('https://example.com/y') == 'socks5h://1.2.3.4:1080'
