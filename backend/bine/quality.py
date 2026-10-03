"""Data-quality filter and dual-issuer universe builder for BINE.

Rules:
1. Never rank tokens by raw `(tokenPrice - referencePrice) / referencePrice`,
   because `referencePrice == tokenPrice / tokenToShareRatio` (shares per token).
2. Mark outliers (such as `ENLVon` with tokenPrice=$0.0023, referencePrice=$0.0344,
   tokenToShareRatio=0.066667, volume24H=$501k) as `quality_status="unreliable"`
   and exclude them from default views.
3. Default universe is the set of underlying tickers that exist on BOTH Ondo
   and bStocks on BSC (`56`), enabling direct side-by-side comparison.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from bine.models import TokenSample

# Minimum thresholds for reliable tokenized stocks
MIN_TOKEN_PRICE_USD = 1.00
MIN_REFERENCE_PRICE_USD = 1.00
MIN_VOLUME_24H_USD = 1_000_000.0  # $1M 24h underlying/token volume
MIN_SHARE_RATIO = 0.25
MAX_SHARE_RATIO = 5.0

# Canonical 40 tickers confirmed on both Ondo and bStocks on BSC (chainId=56)
DUAL_ISSUER_TICKERS: tuple[str, ...] = (
    "AAOI", "AMD", "ARM", "AVGO", "AXTI", "BABA", "CBRS", "COIN", "CRCL", "CRWV",
    "DRAM", "EWY", "GLW", "GOOGL", "HOOD", "IBM", "INTC", "LITE", "META", "MRVL",
    "MSFT", "MSTR", "MU", "NBIS", "NOK", "NVDA", "ORCL", "PLTR", "QCOM", "QQQ",
    "RKLB", "SKHY", "SNDK", "SOXL", "SPCX", "SPY", "TQQQ", "TSLA", "TSM", "WDC",
)


@dataclass(frozen=True)
class QualityCheck:
    reliable: bool
    status: str  # "ok" | "unreliable"
    reason: str | None = None


def assess_token_quality(
    *,
    token_price: float | None,
    reference_price: float | None,
    token_to_share_ratio: float | None,
    volume_24h: float | None,
) -> QualityCheck:
    """Evaluate a token snapshot against deterministic data-quality rules."""
    if token_price is None or reference_price is None or token_price <= 0 or reference_price <= 0:
        return QualityCheck(False, "unreliable", "Missing or non-positive price")

    if token_price < MIN_TOKEN_PRICE_USD or reference_price < MIN_REFERENCE_PRICE_USD:
        return QualityCheck(
            False,
            "unreliable",
            f"Sub-${MIN_TOKEN_PRICE_USD:.2f} price (token=${token_price:.4f}, ref=${reference_price:.4f})",
        )

    if token_to_share_ratio is None or token_to_share_ratio <= 0:
        return QualityCheck(False, "unreliable", "Missing or non-positive tokenToShareRatio")

    if token_to_share_ratio < MIN_SHARE_RATIO or token_to_share_ratio > MAX_SHARE_RATIO:
        return QualityCheck(
            False,
            "unreliable",
            f"Extreme tokenToShareRatio ({token_to_share_ratio:.6f}x outside [{MIN_SHARE_RATIO}, {MAX_SHARE_RATIO}])",
        )

    expected_ref = token_price / token_to_share_ratio
    if abs(expected_ref - reference_price) / reference_price > 0.01:
        return QualityCheck(
            False,
            "unreliable",
            "tokenPrice / tokenToShareRatio diverges >1% from referencePrice",
        )

    if volume_24h is None or volume_24h < MIN_VOLUME_24H_USD:
        vol_str = f"${volume_24h:,.0f}" if volume_24h is not None else "null"
        return QualityCheck(
            False,
            "unreliable",
            f"Low 24h volume ({vol_str} < ${MIN_VOLUME_24H_USD:,.0f})",
        )

    return QualityCheck(True, "ok", None)


def assess_sample_row(row: TokenSample) -> QualityCheck:
    """Assess a SQLAlchemy TokenSample row."""
    if not row.ok:
        return QualityCheck(False, "unreliable", row.error_msg or "Sample failed")
    return assess_token_quality(
        token_price=row.token_price,
        reference_price=row.reference_price,
        token_to_share_ratio=row.token_to_share_ratio,
        volume_24h=row.volume_24h,
    )


def find_dual_issuer_tickers(rows: Iterable[TokenSample]) -> set[str]:
    """Return tickers that have a reliable snapshot on BOTH ondo and bstock."""
    by_platform: dict[str, set[str]] = {"ondo": set(), "bstock": set()}
    for r in rows:
        if r.platform_id in by_platform and assess_sample_row(r).reliable:
            by_platform[r.platform_id].add(r.underlying_ticker.upper())
    common = by_platform["ondo"] & by_platform["bstock"]
    return common if common else set(DUAL_ISSUER_TICKERS)
