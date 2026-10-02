"""Unit tests for HMAC-SHA256 request signing.

Uses the exact example from the Binance Web3 API Authentication docs as a
known-good vector. If these fail, every API call will return 40102.
"""

import base64
import hashlib
import hmac

from bine.client import make_timestamp, sign


# ---------- known-good vector from the docs ----------
# Docs say: preHash = timestamp + method + requestPath + body
# Example GET:
#   timestamp   = "2026-05-11T10:08:57.715Z"
#   method      = "GET"
#   requestPath = "/build/api/v1/dex/market/price?chainId=1&symbol=ETH%20USDT"
#   body        = ""

DOC_TIMESTAMP = "2026-05-11T10:08:57.715Z"
DOC_METHOD = "GET"
DOC_PATH = "/build/api/v1/dex/market/price?chainId=1&symbol=ETH%20USDT"
DOC_BODY = ""
TEST_SECRET = "test-secret-key-for-unit-tests"

# Compute expected signature independently
DOC_PREHASH = DOC_TIMESTAMP + DOC_METHOD + DOC_PATH + DOC_BODY
DOC_EXPECTED_SIG = base64.b64encode(
    hmac.new(
        TEST_SECRET.encode("utf-8"),
        DOC_PREHASH.encode("utf-8"),
        hashlib.sha256,
    ).digest()
).decode("utf-8")


def test_sign_matches_doc_example():
    """The sign() function must produce the exact same signature as the
    independently-computed HMAC over the doc's example pre-hash string."""
    result = sign(TEST_SECRET, DOC_TIMESTAMP, DOC_METHOD, DOC_PATH, DOC_BODY)
    assert result == DOC_EXPECTED_SIG


def test_sign_prehash_includes_build_prefix():
    """The pre-hash string MUST include /build. Omitting it is the #1 cause
    of 40102 per the docs."""
    # Sign with /build prefix
    sig_with = sign(TEST_SECRET, DOC_TIMESTAMP, "GET", "/build/api/v1/foo")
    # Sign without — must be different
    sig_without = sign(TEST_SECRET, DOC_TIMESTAMP, "GET", "/api/v1/foo")
    assert sig_with != sig_without


def test_sign_post_with_body():
    """POST requests include the raw JSON body in the pre-hash."""
    body = '{"chainId":56,"amount":"1000"}'
    path = "/build/api/v1/dex/swap"

    sig = sign(TEST_SECRET, DOC_TIMESTAMP, "POST", path, body)
    # Compute expected
    pre_hash = DOC_TIMESTAMP + "POST" + path + body
    expected = base64.b64encode(
        hmac.new(
            TEST_SECRET.encode("utf-8"),
            pre_hash.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    assert sig == expected


def test_sign_get_empty_body():
    """GET requests must use empty string for body, not None."""
    path = "/build/api/v1/dex/market/rwa/platforms"
    sig_empty = sign(TEST_SECRET, DOC_TIMESTAMP, "GET", path, "")
    sig_default = sign(TEST_SECRET, DOC_TIMESTAMP, "GET", path)
    assert sig_empty == sig_default


def test_sign_method_uppercase():
    """Method is uppercased in the pre-hash per spec."""
    path = "/build/api/v1/foo"
    sig_upper = sign(TEST_SECRET, DOC_TIMESTAMP, "GET", path)
    sig_lower = sign(TEST_SECRET, DOC_TIMESTAMP, "get", path)
    assert sig_upper == sig_lower


def test_sign_different_secrets_produce_different_sigs():
    """Sanity: different secrets → different signatures."""
    path = "/build/api/v1/foo"
    sig1 = sign("secret-a", DOC_TIMESTAMP, "GET", path)
    sig2 = sign("secret-b", DOC_TIMESTAMP, "GET", path)
    assert sig1 != sig2


def test_sign_query_string_preserved_exactly():
    """Query string must be signed in raw form — no re-ordering or decoding."""
    path_a = "/build/api/v1/foo?b=2&a=1"
    path_b = "/build/api/v1/foo?a=1&b=2"
    sig_a = sign(TEST_SECRET, DOC_TIMESTAMP, "GET", path_a)
    sig_b = sign(TEST_SECRET, DOC_TIMESTAMP, "GET", path_b)
    # Different order → different signature (the API checks exact wire form)
    assert sig_a != sig_b


def test_make_timestamp_format():
    """Timestamp must be ISO 8601 with exactly 3 decimal places and Z suffix."""
    ts = make_timestamp()
    assert ts.endswith("Z")
    # Format: YYYY-MM-DDTHH:MM:SS.mmmZ
    assert len(ts) == 24
    assert ts[10] == "T"
    assert ts[19] == "."
