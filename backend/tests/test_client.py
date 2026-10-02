"""Tests for the BinanceClient: retry logic, error handling, header construction."""

import json

import httpx
import pytest
import respx

from bine.client import BinanceClient


API_KEY = "test-api-key"
SECRET_KEY = "test-secret-key"
PLATFORMS_PATH = "/api/v1/dex/market/rwa/platforms"


@pytest.fixture
def client():
    return BinanceClient(api_key=API_KEY, secret_key=SECRET_KEY, max_retries=2)


# -- Happy path --


@respx.mock
@pytest.mark.asyncio
async def test_get_success(client):
    """A successful GET returns parsed data."""
    payload = {
        "code": 0,
        "msg": "success",
        "data": [{"platformId": "ondo"}],
        "timestamp": 1748601600000,
        "success": True,
    }
    respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await client.get(PLATFORMS_PATH)
    assert result["code"] == 0
    assert result["data"][0]["platformId"] == "ondo"


@respx.mock
@pytest.mark.asyncio
async def test_post_success(client):
    """A successful POST returns parsed data."""
    payload = {"code": 0, "msg": "success", "data": {"simulated": True}}
    respx.post(
        "https://web3.binance.com/build/api/v1/dex/pre-transaction/simulate"
    ).mock(return_value=httpx.Response(200, json=payload))
    result = await client.post(
        "/api/v1/dex/pre-transaction/simulate",
        body={"binanceChainId": "56", "address": "0x123"},
    )
    assert result["data"]["simulated"] is True


# -- Auth headers --


@respx.mock
@pytest.mark.asyncio
async def test_headers_present(client):
    """Every request must include the three required auth headers."""
    route = respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}").mock(
        return_value=httpx.Response(
            200, json={"code": 0, "msg": "success", "data": []}
        )
    )
    await client.get(PLATFORMS_PATH)
    req = route.calls[0].request
    assert "X-OC-APIKEY" in req.headers
    assert "X-OC-TIMESTAMP" in req.headers
    assert "X-OC-SIGN" in req.headers
    assert req.headers["X-OC-APIKEY"] == API_KEY


# -- Error handling --


@respx.mock
@pytest.mark.asyncio
async def test_signature_error_raises(client):
    """A 40102 response raises SignatureError immediately (no retry)."""
    from bine.errors import SignatureError

    respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}").mock(
        return_value=httpx.Response(
            200, json={"code": 40102, "msg": "Invalid signature"}
        )
    )
    with pytest.raises(SignatureError) as exc_info:
        await client.get(PLATFORMS_PATH)
    assert exc_info.value.code == 40102


@respx.mock
@pytest.mark.asyncio
async def test_business_error_raises(client):
    """An unknown business error code raises BinanceAPIError."""
    from bine.errors import BinanceAPIError

    respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}").mock(
        return_value=httpx.Response(
            200, json={"code": 40001, "msg": "Parameter error"}
        )
    )
    with pytest.raises(BinanceAPIError) as exc_info:
        await client.get(PLATFORMS_PATH)
    assert exc_info.value.code == 40001


# -- Retry logic --


@respx.mock
@pytest.mark.asyncio
async def test_retry_on_http_429(client, monkeypatch):
    """Client retries on HTTP 429 with backoff."""
    # Patch sleep to avoid waiting
    monkeypatch.setattr(BinanceClient, "_sleep", staticmethod(lambda s: __import__("asyncio").sleep(0)))

    route = respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0.01"}),
        httpx.Response(200, json={"code": 0, "msg": "success", "data": []}),
    ]
    result = await client.get(PLATFORMS_PATH)
    assert result["code"] == 0
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_retry_on_500(client, monkeypatch):
    """Client retries on HTTP 500."""
    monkeypatch.setattr(BinanceClient, "_sleep", staticmethod(lambda s: __import__("asyncio").sleep(0)))

    route = respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json={"code": 0, "msg": "success", "data": []}),
    ]
    result = await client.get(PLATFORMS_PATH)
    assert result["code"] == 0


@respx.mock
@pytest.mark.asyncio
async def test_rate_limit_exhausts_retries(client, monkeypatch):
    """After max retries on 429, raises RateLimitError."""
    from bine.errors import RateLimitError

    monkeypatch.setattr(BinanceClient, "_sleep", staticmethod(lambda s: __import__("asyncio").sleep(0)))

    respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0.01"})
    )
    with pytest.raises(RateLimitError):
        await client.get(PLATFORMS_PATH)


# -- Recorded live response fixtures --


@respx.mock
@pytest.mark.asyncio
async def test_recorded_rwa_platforms_fixture(client):
    """Verify client parses the real recorded /rwa/platforms response."""
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "rwa_platforms.json"
    payload = json.loads(fixture.read_text())
    respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await client.get(PLATFORMS_PATH)
    assert result["code"] == 0
    platforms = {p["platformId"] for p in result["data"]}
    assert platforms == {"ondo", "bstock"}


@respx.mock
@pytest.mark.asyncio
async def test_recorded_rwa_tokens_fixtures(client):
    """Verify client parses the real recorded /rwa/tokens responses for ondo and bstock."""
    from pathlib import Path

    for name, expected_platform in [("rwa_tokens_ondo_bsc.json", "ondo"), ("rwa_tokens_bstock_bsc.json", "bstock")]:
        fixture = Path(__file__).parent / "fixtures" / name
        payload = json.loads(fixture.read_text())
        respx.get("https://web3.binance.com/build/api/v1/dex/market/rwa/tokens").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await client.get(
            "/api/v1/dex/market/rwa/tokens",
            params={"binanceChainId": "56", "platformId": expected_platform},
        )
        assert result["code"] == 0
        assert len(result["data"]) > 0
        first = result["data"][0]
        assert first["platformId"] == expected_platform
        assert first["binanceChainId"] == "56"
        assert "tokenPrice" in first
        assert "referencePrice" in first
        assert "statusInfo" in first


@respx.mock
@pytest.mark.asyncio
async def test_retry_resigns_headers_on_each_attempt(client, monkeypatch):
    """Every retry attempt generates a fresh X-OC-TIMESTAMP and X-OC-SIGN."""
    import bine.client as client_mod

    timestamps = iter(["2026-10-01T14:50:20.000Z", "2026-10-01T14:50:36.000Z"])
    monkeypatch.setattr(client_mod, "make_timestamp", lambda: next(timestamps))
    monkeypatch.setattr(BinanceClient, "_sleep", staticmethod(lambda s: __import__("asyncio").sleep(0)))

    route = respx.get(f"https://web3.binance.com/build{PLATFORMS_PATH}")
    route.side_effect = [
        httpx.ConnectTimeout("attempt 1 timed out after 15s"),
        httpx.Response(200, json={"code": 0, "msg": "success", "data": []}),
    ]

    result = await client.get(PLATFORMS_PATH)
    assert result["code"] == 0
    assert len(route.calls) == 2

    req1, req2 = route.calls[0].request, route.calls[1].request
    assert req1.headers["X-OC-TIMESTAMP"] == "2026-10-01T14:50:20.000Z"
    assert req2.headers["X-OC-TIMESTAMP"] == "2026-10-01T14:50:36.000Z"
    assert req1.headers["X-OC-SIGN"] != req2.headers["X-OC-SIGN"]


