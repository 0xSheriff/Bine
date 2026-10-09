import os
import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from bine.app import app, reset_rate_limits, _extract_client_ip
from bine.client import BinanceClient
from bine.config import Settings, get_settings


def test_client_ip_extraction_trusted_vs_untrusted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1,::1")

    # 1. Trusted proxy with X-Forwarded-For (multiple hops)
    scope_trusted_xff = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 10.0.0.1")],
    }
    req = Request(scope_trusted_xff)
    assert _extract_client_ip(req) == "203.0.113.195"

    # 2. Trusted proxy with X-Real-IP
    scope_trusted_xreal = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-real-ip", b"198.51.100.7")],
    }
    req = Request(scope_trusted_xreal)
    assert _extract_client_ip(req) == "198.51.100.7"

    # 3. Untrusted proxy/client trying to spoof X-Forwarded-For
    scope_untrusted = {
        "type": "http",
        "client": ("192.0.2.1", 54321),
        "headers": [(b"x-forwarded-for", b"1.1.1.1")],
    }
    req = Request(scope_untrusted)
    assert _extract_client_ip(req) == "192.0.2.1"


def test_rate_limit_distinct_clients_behind_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1,testclient")
    reset_rate_limits()
    client = TestClient(app)

    # Exhaust rate limit for client A
    for _ in range(20):
        resp = client.get("/api/health", headers={"X-Forwarded-For": "203.0.113.10"})
        assert resp.status_code == 200

    # 21st request for client A should be allowed on /api/health (rate limit is on /api/quote & /api/execute)
    # Let's test directly on _check_rate_limit or /api/quote rate limiting
    from bine.app import _check_rate_limit
    from fastapi import HTTPException

    req_a = Request({
        "type": "http",
        "client": ("127.0.0.1", 1234),
        "headers": [(b"x-forwarded-for", b"203.0.113.10")],
    })
    req_b = Request({
        "type": "http",
        "client": ("127.0.0.1", 1234),
        "headers": [(b"x-forwarded-for", b"203.0.113.20")],
    })

    reset_rate_limits()
    for _ in range(20):
        _check_rate_limit(req_a, "quote", 20)

    # req_a reaches limit
    with pytest.raises(HTTPException) as exc_info:
        _check_rate_limit(req_a, "quote", 20)
    assert exc_info.value.status_code == 429

    # req_b has its own bucket and is not blocked
    _check_rate_limit(req_b, "quote", 20)


def test_public_demo_lock_forces_live_mode_off_and_dry_run_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BINE_LIVE_MODE", "true")
    monkeypatch.setenv("BINE_PUBLIC_DEMO", "true")
    monkeypatch.delenv("VERCEL", raising=False)

    s = Settings()
    assert s.bine_live_mode is False

    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["live_mode"] is False
    assert "binance_credentials_present" in data


def test_binance_credentials_present_in_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BINANCE_API_KEY", "  valid_key  ")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "  valid_secret  ")
    s = Settings()
    assert s.binance_api_key == "valid_key"
    assert s.binance_secret_key == "valid_secret"

    b_client = BinanceClient(api_key=" test_k ", secret_key=" test_s ")
    assert b_client._api_key == "test_k"
    assert b_client._secret_key == "test_s"

    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["binance_credentials_present"] is True

    monkeypatch.setenv("BINANCE_API_KEY", "   ")
    client_empty = TestClient(app)
    resp_empty = client_empty.get("/api/health")
    assert resp_empty.json()["binance_credentials_present"] is False


def test_api_recent_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/api/recent?hours=24&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert data["hours"] == 24
    assert "checks" in data
    assert isinstance(data["checks"], list)


def test_cli_probe_command_parsing() -> None:
    from bine.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["probe", "--tickers", "NVDA,SPY", "5.50", "--scheduled"])
    assert args.command == "probe"
    assert args.scheduled is True
    assert args.tickers == "NVDA,SPY"
    assert args.amount_usd == 5.50
