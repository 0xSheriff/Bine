"""SQLAlchemy models for the BINE Atlas.

Works with SQLite (local dev, driver=aiosqlite) and Postgres (production).
All schema changes are additive — no migrations needed for the hackathon.

Tables:
  token_sample   — one row per token per sampler tick (or a failure row)
  quote_probe    — slippage quotes at fixed USD sizes
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TokenSample(Base):
    """One row per token per sampler tick.

    If the API call failed, `ok=False` and only `error_msg` is populated —
    every other data field is NULL. The UI shows these gaps honestly.
    """

    __tablename__ = "token_sample"
    __table_args__ = (
        Index("ix_token_sample_address_sampled", "token_contract_address", "sampled_at"),
        Index("ix_token_sample_ticker_sampled", "underlying_ticker", "sampled_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Token identity (always populated, even on failure)
    binance_chain_id: Mapped[str] = mapped_column(String(16), nullable=False, default="56")
    token_contract_address: Mapped[str] = mapped_column(String(64), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(16), nullable=False)
    underlying_ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    token_symbol: Mapped[str] = mapped_column(String(32), nullable=False)

    # Whether this tick succeeded
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Prices — null on failure or when API returns null
    token_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    token_to_share_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Gap: (token_price - reference_price) / reference_price * 100
    # Stored as computed-at-sample-time to avoid float re-derivation.
    price_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Market status (null on bStocks, stored as received)
    open_state: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    market_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_open_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Volume / depth
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Quote probes (populated from separate quote calls if they ran)
    quotes: Mapped[list[QuoteProbe]] = relationship(
        "QuoteProbe", back_populates="sample", cascade="all, delete-orphan"
    )


class QuoteProbe(Base):
    """DEX `/quote` result for a fixed trade size at a given sample tick.

    Populated separately from the main token poll; may be absent if the quote
    call failed or was skipped (e.g. market closed, RFQ unavailable).
    """

    __tablename__ = "quote_probe"
    __table_args__ = (
        Index("ix_quote_probe_sample", "sample_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("token_sample.id", ondelete="CASCADE"), nullable=False
    )
    sample: Mapped[TokenSample] = relationship("TokenSample", back_populates="quotes")

    # Which probe
    probe_usd: Mapped[float] = mapped_column(Float, nullable=False)  # 10, 50, 250

    # Quote result — null if the quote call failed
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Slippage: (quoted_out - ideal_out) / ideal_out * 100 (negative = worse)
    slippage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Raw quote fields as returned
    from_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)


class DecisionLog(Base):
    """Audit log of every trade decision, refusal, Transaction API dry-run simulation,
    and Agentic Wallet live execution (`POST /api/execute`).
    """

    __tablename__ = "decision_log"
    __table_args__ = (
        Index("ix_decision_log_created_at", "created_at"),
        Index("ix_decision_log_ticker_created", "ticker", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Request inputs
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="dry_run")  # "dry_run" | "execute"

    # Deterministic Quote Engine Verdict
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)  # "BUY_ONDO" | "BUY_BSTOCK" | "REFUSE"
    recommended_platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    recommended_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recommended_contract_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    refusal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Economic summary of chosen route
    expected_shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_in_price_per_share_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_in_vs_reference_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_slippage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    quote_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Transaction API (/api/v1/dex/pre-transaction/simulate) dry-run results
    simulation_ran: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    simulation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "SUCCESS" | "REQUIRES_APPROVAL" | "FAILED" | "SKIPPED"
    simulation_fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_simulation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    spender_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estimated_gas_limit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Live execution via Binance Agentic Wallet (`baw`)
    live_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRY_RUN_ONLY"
    )  # "REFUSED" | "DRY_RUN_OK" | "DRY_RUN_FAILED" | "LIVE_SUBMITTED" | "LIVE_BLOCKED_CAP" | "LIVE_DISABLED" | "LIVE_ERROR"
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bsctrace_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    execution_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full JSON snapshot of quote + simulation + execution payload
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

