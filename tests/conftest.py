"""Stub required environment variables before any project imports are collected,
so tests that don't need a live deployment can run without a .env file.
"""
import os

os.environ.setdefault('SENTRY_DSN', 'http://fake@localhost/1')
# proxy configuration defaults for tests
os.environ.setdefault('PROXIES', '')
os.environ.setdefault('TOR_PROXY', '')
os.environ.setdefault('PROXY_WHITELIST_HOSTS', '')
os.environ.setdefault('REQUIRE_PROXY', '0')
