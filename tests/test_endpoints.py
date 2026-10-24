"""Endpoint tests — lifespan builds a FakePool, so no Firefox or network is used."""

import os
from unittest.mock import patch

# Set env vars before importing the app (sentry/pyroscope init on import)
os.environ.setdefault('SENTRY_DSN', 'http://fake@localhost/1')

import pytest
from fastapi.testclient import TestClient

from reader_web_service.browser_pool import BrowserBusy


class FakePool:
    """Scripted BrowserPool stand-in: records run() calls, launches nothing."""

    def __init__(self, *args):
        self.calls = []
        self.result = None
        self.busy = False
        self.start_count = 0
        self.shutdown_count = 0

    async def start(self):
        self.start_count += 1

    async def run(self, url, reader=True):
        self.calls.append((url, reader))
        if self.busy:
            raise BrowserBusy
        return self.result

    async def shutdown(self):
        self.shutdown_count += 1


@pytest.fixture
def pool_and_client():
    """Swap BrowserPool for FakePool; the app lifespan builds the fake pool."""
    from reader_web_service.__main__ import app

    with patch('reader_web_service.__main__.BrowserPool', FakePool):
        with TestClient(app) as client:
            yield app.state.browser_pool, client


def test_root_reader_mode_success(pool_and_client):
    """GET / with valid URL returns 200 + title + html from reader mode."""
    pool, client = pool_and_client
    pool.result = {
        'title': 'Test Article',
        'content': '<p>Hello world</p>',
    }
    resp = client.get('/', params={'url': 'https://example.com'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['title'] == 'Test Article'
    assert body['html'] == '<p>Hello world</p>'
    assert pool.calls == [('https://example.com', True)]


def test_root_reader_mode_not_found(pool_and_client):
    """GET / when the pool returns None → 400 + error."""
    pool, client = pool_and_client
    resp = client.get('/', params={'url': 'https://example.com'})
    assert resp.status_code == 400
    assert resp.json() == {'error': 'reader not found'}


def test_html_endpoint_success(pool_and_client):
    """GET /html with valid URL returns 200 + title + html (reader disabled)."""
    pool, client = pool_and_client
    pool.result = {
        'title': 'Raw Page',
        'content': '<div>raw content</div>',
    }
    resp = client.get('/html', params={'url': 'https://example.com'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['title'] == 'Raw Page'
    assert body['html'] == '<div>raw content</div>'
    assert pool.calls == [('https://example.com', False)]


def test_html_endpoint_not_found(pool_and_client):
    """GET /html when the pool returns None → 400 + error."""
    pool, client = pool_and_client
    resp = client.get('/html', params={'url': 'https://example.com'})
    assert resp.status_code == 400
    assert resp.json() == {'error': 'reader not found'}


def test_ping_success(pool_and_client):
    """GET /ping when a worker opens example.com → 200 + status ok."""
    pool, client = pool_and_client
    pool.result = {
        'title': 'Example Domain',
        'content': '<div>example</div>',
    }
    resp = client.get('/ping')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}
    assert pool.calls == [('https://example.com', False)]


def test_ping_failure(pool_and_client):
    """GET /ping when the pool returns None → 500 + status error."""
    pool, client = pool_and_client
    resp = client.get('/ping')
    assert resp.status_code == 500
    assert resp.json() == {'status': 'error'}


def test_ip_success(pool_and_client):
    """GET /ip returns the exit IP parsed from the ip.me page."""
    pool, client = pool_and_client
    pool.result = {
        'title': 'What is my IP address?',
        'content': '<input type="text" name="ip" value="203.0.113.42" class="form-control" id="ip-lookup">',
    }
    resp = client.get('/ip')
    assert resp.status_code == 200
    assert resp.json() == {'ip': '203.0.113.42'}
    assert pool.calls == [('https://ip.me', False)]


def test_ip_failure(pool_and_client):
    """GET /ip when the pool returns None → 500 + error."""
    pool, client = pool_and_client
    resp = client.get('/ip')
    assert resp.status_code == 500
    assert resp.json() == {'error': 'failed to get IP'}


def test_ip_parse_failure(pool_and_client):
    """GET /ip when the page loaded but no IP found → 500 + error."""
    pool, client = pool_and_client
    pool.result = {'title': 'Error', 'content': '<html>no IP here</html>'}
    resp = client.get('/ip')
    assert resp.status_code == 500
    assert resp.json() == {'error': 'could not parse IP'}


def test_pool_busy_returns_503(pool_and_client):
    """GET /ping while the pool is saturated → 503 + Retry-After: 30."""
    pool, client = pool_and_client
    pool.busy = True
    resp = client.get('/ping')
    assert resp.status_code == 503
    assert resp.json()['detail'] == 'Browser capacity is busy; retry later.'
    assert resp.headers['retry-after'] == '30'
    assert pool.calls == [('https://example.com', False)]


def test_lifespan_starts_and_shuts_down_the_pool_once():
    """Lifespan awaits start() once and, on exit, exactly one shutdown()."""
    from reader_web_service.__main__ import app

    with patch('reader_web_service.__main__.BrowserPool', FakePool):
        with TestClient(app):
            pool = app.state.browser_pool
            assert pool.start_count == 1
        assert pool.shutdown_count == 1
