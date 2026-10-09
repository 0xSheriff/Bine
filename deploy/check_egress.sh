#!/usr/bin/env bash
# ==============================================================================
# BINE VPS Egress Verification Script
# Verifies outbound HTTPS reachability to the Binance Web3 Wallet API.
# Expected status for unauthenticated probe: HTTP 401 (API reachable).
# ==============================================================================

set -euo pipefail

ENDPOINT="https://web3.binance.com/build/api/v1/dex/market/rwa/tokens?platform=ondo&chainId=56"
TIMEOUT_SEC=10

echo "Checking outbound egress to Binance Web3 API..."
echo "Target: ${ENDPOINT}"

# First attempt: standard system DNS and network path
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "${TIMEOUT_SEC}" --max-time "${TIMEOUT_SEC}" "${ENDPOINT}" || true)
HTTP_CODE=$(echo "${HTTP_CODE}" | tr -d '[:space:]')
if [[ -z "${HTTP_CODE}" ]]; then
  HTTP_CODE="000"
fi

# If connection failed (000), test if public DNS fallback can resolve it
if [[ "${HTTP_CODE}" == "000" ]] && command -v dig >/dev/null 2>&1; then
  echo "Notice: System DNS timed out or failed. Testing public DNS (8.8.8.8)..."
  FALLBACK_IP=$(dig @8.8.8.8 +short web3.binance.com 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true)
  if [[ -n "${FALLBACK_IP}" ]]; then
    echo "Resolved web3.binance.com to ${FALLBACK_IP} via 8.8.8.8. Testing with fallback IP..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --resolve "web3.binance.com:443:${FALLBACK_IP}" --connect-timeout "${TIMEOUT_SEC}" --max-time "${TIMEOUT_SEC}" "${ENDPOINT}" || true)
    HTTP_CODE=$(echo "${HTTP_CODE}" | tr -d '[:space:]')
    if [[ "${HTTP_CODE}" == "401" ]]; then
      echo "SUCCESS (with DNS note): Network reachability verified, but your local system DNS server cannot resolve web3.binance.com."
      echo "Recommended action on VPS: set upstream DNS resolver in /etc/resolv.conf to 8.8.8.8 or 1.1.1.1, or set DEV_DNS_FALLBACK=true in /etc/bine/bine.env."
      exit 0
    fi
  fi
fi

echo "Response status: HTTP ${HTTP_CODE}"

case "${HTTP_CODE}" in
  401)
    echo "SUCCESS: Binance Web3 API is reachable."
    echo "HTTP 401 is expected for unauthenticated probe (credentials required for data access)."
    exit 0
    ;;
  403|451)
    echo "FAILURE: Connection refused by upstream WAF or regional compliance (HTTP ${HTTP_CODE})."
    echo "Your server IP or datacenter region may be geoblocked by Binance."
    exit 1
    ;;
  000)
    echo "FAILURE: Connection timed out or DNS resolution failed."
    echo "Check server outbound firewall rules (port 443) and DNS configuration."
    exit 1
    ;;
  *)
    echo "UNEXPECTED: Upstream returned HTTP ${HTTP_CODE}."
    exit 1
    ;;
esac
