"""Unit tests for FastAPI endpoints — mocking read_by_firefox, no Firefox needed."""
import os
from unittest.mock import patch

# Set env vars before importing the app (sentry/pyroscope init on import)
os.environ.setdefault("SENTRY_DSN", "http://fake@localhost/1")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from reader_web_service.__main__ import app
    return TestClient(app)


@patch("reader_web_service.__main__.read_by_firefox")
def test_root_reader_mode_success(mock_read, client):
    """GET / with valid URL returns 200 + title + html from reader mode."""
    mock_read.return_value = {
        "title": "Test Article",
        "content": "<p>Hello world</p>",
    }
    resp = client.get("/", params={"url": "https://example.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Test Article"
    assert body["html"] == "<p>Hello world</p>"
    mock_read.assert_called_once_with("https://example.com")


@patch("reader_web_service.__main__.read_by_firefox")
def test_root_reader_mode_not_found(mock_read, client):
    """GET / when read_by_firefox returns None → 400 + error."""
    mock_read.return_value = None
    resp = client.get("/", params={"url": "https://example.com"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "reader not found"}


@patch("reader_web_service.__main__.read_by_firefox")
def test_html_endpoint_success(mock_read, client):
    """GET /html with valid URL returns 200 + title + html (reader=False)."""
    mock_read.return_value = {
        "title": "Raw Page",
        "content": "<div>raw content</div>",
    }
    resp = client.get("/html", params={"url": "https://example.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Raw Page"
    assert body["html"] == "<div>raw content</div>"
    mock_read.assert_called_once_with("https://example.com", False)


@patch("reader_web_service.__main__.read_by_firefox")
def test_html_endpoint_not_found(mock_read, client):
    """GET /html when read_by_firefox returns None → 400 + error."""
    mock_read.return_value = None
    resp = client.get("/html", params={"url": "https://example.com"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "reader not found"}


@patch("reader_web_service.__main__.read_by_firefox")
def test_ping_success(mock_read, client):
    """GET /ping when Firefox opens example.com → 200 + status ok."""
    mock_read.return_value = {
        "title": "Example Domain",
        "content": "<div>example</div>",
    }
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_read.assert_called_once_with("https://example.com", False)


@patch("reader_web_service.__main__.read_by_firefox")
def test_ping_failure(mock_read, client):
    """GET /ping when Firefox fails → 500 + status error."""
    mock_read.return_value = None
    resp = client.get("/ping")
    assert resp.status_code == 500
    assert resp.json() == {"status": "error"}


@patch("reader_web_service.__main__.read_by_firefox")
def test_ip_success(mock_read, client):
    """GET /ip returns the exit IP parsed from ip.me page."""
    mock_read.return_value = {
        "title": "What is my IP address?",
        "content": '<input type="text" name="ip" value="203.0.113.42" class="form-control" id="ip-lookup">',
    }
    resp = client.get("/ip")
    assert resp.status_code == 200
    assert resp.json() == {"ip": "203.0.113.42"}
    mock_read.assert_called_once_with("https://ip.me", False)


@patch("reader_web_service.__main__.read_by_firefox")
def test_ip_failure(mock_read, client):
    """GET /ip when Firefox fails → 500 + error."""
    mock_read.return_value = None
    resp = client.get("/ip")
    assert resp.status_code == 500
    assert resp.json() == {"error": "failed to get IP"}


@patch("reader_web_service.__main__.read_by_firefox")
def test_ip_parse_failure(mock_read, client):
    """GET /ip when page loaded but IP not found in HTML → 500 + error."""
    mock_read.return_value = {"title": "Error", "content": "<html>no IP here</html>"}
    resp = client.get("/ip")
    assert resp.status_code == 500
    assert resp.json() == {"error": "could not parse IP"}
