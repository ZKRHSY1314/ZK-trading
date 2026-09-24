from __future__ import annotations

from dataclasses import dataclass
from math import floor

from app.config import settings

# daily_bar_cache stores volume in 手 (volume_unit="hand"); one 手 is 100 shares.
SHARES_PER_HAND = 100

LIQUIDITY_REPORTED = "reported_amount"
LIQUIDITY_PROXY = "volume_price_proxy"


@dataclass(frozen=True)
class ExecutionDecision:
    side: str
    fill_status: str
    requested_quantity: int
    filled_quantity: int
    price: float
    fee: float
    stamp_tax: float
    reject_reason: str | None = None
    liquidity_cap_amount: float | None = None
    liquidity_basis: str | None = None
    price_band_basis: str | None = None
    capacity_basis: str | None = None


class BacktestExecutionModel:
    def __init__(
        self,
        lot_size: int | None = None,
        max_participation_rate: float | None = None,
    ) -> None:
        self.lot_size = lot_size or settings.min_order_lot
        self.max_participation_rate = (
            max_participation_rate
            if max_participation_rate is not None
            else settings.backtest_max_participation_rate
        )
        self.fee_rate = settings.commission_rate
        self.stamp_tax_rate = settings.stamp_tax_rate

    def estimated_fee(self, notional: float) -> float:
        """Commission a fill of this notional would pay; 0 for an empty order."""

        return max(notional * self.fee_rate, 5.0) if notional > 0 else 0.0

    def decide(
        self,
        side: str,
        requested_quantity: int,
        price: float,
        bar: dict,
        previous_close: float,
        limit_pct: float,
        *,
        price_band_basis: str = "session_range",
        capacity_basis: str = "same_session_amount",
        capacity_bar: dict | None = None,
    ) -> ExecutionDecision:
        """Adjudicate one order against a daily bar.

        The defaults are the historical retrospective assumptions: the price band
        is judged from the whole session's range and capacity from the whole
        session's amount. ``price_band_basis="session_open"`` judges the band
        from the opening print only, and ``capacity_basis="prior_session_amount"``
        takes capacity from ``capacity_bar`` (the previous session) - both known
        at the open. A prior-session basis without a prior bar is refused as
        unproven capacity rather than silently falling back to today.
        """

        bases = {"price_band_basis": price_band_basis, "capacity_basis": capacity_basis}
        requested_quantity = max(0, int(requested_quantity))
        if requested_quantity < self.lot_size:
            return self._rejected(side, requested_quantity, price, "below_min_lot", **bases)

        limit_up_price = previous_close * (1 + limit_pct / 100)
        limit_down_price = previous_close * (1 - limit_pct / 100)
        if price_band_basis == "session_open":
            opening = float(bar["open"])
            if side == "buy" and opening >= limit_up_price * 0.99:
                return self._rejected(side, requested_quantity, price, "open_at_limit_up", **bases)
            if side == "sell" and opening <= limit_down_price * 1.01:
                return self._rejected(side, requested_quantity, price, "open_at_limit_down", **bases)
        elif price_band_basis == "session_range":
            low = float(bar["low"])
            high = float(bar["high"])
            if side == "buy" and low >= limit_up_price * 0.99:
                return self._rejected(side, requested_quantity, price, "one_word_limit_up", **bases)
            if side == "sell" and high <= limit_down_price * 1.01:
                return self._rejected(side, requested_quantity, price, "one_word_limit_down", **bases)
        else:
            raise ValueError(f"unknown price band basis: {price_band_basis!r}")

        if capacity_basis == "prior_session_amount":
            if capacity_bar is None:
                return self._rejected(side, requested_quantity, price, "capacity_unproven", **bases)
            liquidity_bar = capacity_bar
        elif capacity_basis == "same_session_amount":
            liquidity_bar = bar
        else:
            raise ValueError(f"unknown capacity basis: {capacity_basis!r}")

        amount = float(liquidity_bar.get("amount") or 0)
        liquidity_basis = LIQUIDITY_REPORTED
        if amount <= 0:
            # 97.6% of cached bars come from a source without 成交额. Refusing
            # every fill on them measures the data gap, not the strategy, so
            # fall back to volume x typical price (median ratio to reported
            # amount 1.007, and it under-estimates on wide-range days, which
            # is the conservative side for a participation cap). The basis is
            # carried on the decision so a run can report how much of its
            # liquidity was proxied.
            amount = self._proxy_amount(liquidity_bar)
            liquidity_basis = LIQUIDITY_PROXY if amount > 0 else None
        liquidity_cap_amount = amount * self.max_participation_rate
        if liquidity_cap_amount <= 0:
            return self._rejected(side, requested_quantity, price, "missing_liquidity_amount", **bases)

        liquidity_quantity = floor(liquidity_cap_amount / price / self.lot_size) * self.lot_size
        filled_quantity = min(requested_quantity, liquidity_quantity)
        if filled_quantity < self.lot_size:
            return self._rejected(
                side,
                requested_quantity,
                price,
                "liquidity_below_min_lot",
                liquidity_cap_amount=liquidity_cap_amount,
                **bases,
            )

        fill_status = "full" if filled_quantity == requested_quantity else "partial"
        filled_amount = filled_quantity * price
        fee = self.estimated_fee(filled_amount)
        stamp_tax = filled_amount * self.stamp_tax_rate if side == "sell" else 0.0
        return ExecutionDecision(
            side=side,
            fill_status=fill_status,
            requested_quantity=requested_quantity,
            filled_quantity=filled_quantity,
            price=price,
            fee=fee,
            stamp_tax=stamp_tax,
            liquidity_cap_amount=round(liquidity_cap_amount, 4),
            liquidity_basis=liquidity_basis,
            **bases,
        )

    @staticmethod
    def _proxy_amount(bar: dict) -> float:
        try:
            volume = float(bar.get("volume") or 0)
            typical = (
                float(bar.get("high") or 0) + float(bar.get("low") or 0) + float(bar.get("close") or 0)
            ) / 3
        except (TypeError, ValueError):
            return 0.0
        if volume <= 0 or typical <= 0:
            return 0.0
        return volume * SHARES_PER_HAND * typical

    def _rejected(
        self,
        side: str,
        requested_quantity: int,
        price: float,
        reason: str,
        liquidity_cap_amount: float | None = None,
        price_band_basis: str | None = None,
        capacity_basis: str | None = None,
    ) -> ExecutionDecision:
        return ExecutionDecision(
            side=side,
            fill_status="rejected",
            requested_quantity=requested_quantity,
            filled_quantity=0,
            price=price,
            fee=0.0,
            stamp_tax=0.0,
            reject_reason=reason,
            liquidity_cap_amount=liquidity_cap_amount,
            price_band_basis=price_band_basis,
            capacity_basis=capacity_basis,
        )
