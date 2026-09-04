from dataclasses import dataclass, field
from typing import Iterator

from app.models import MarketSnapshot

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class SignalResult:
    """Three-state signal outcome.

    ``passed``/``reason`` keep the historical 2-tuple unpacking contract, while
    ``status`` separates "the input says no" (``fail``) from "we never had the
    input" (``unknown``). Both score zero, but only ``fail`` is evidence about
    the stock; ``unknown`` is evidence about our data coverage.

    ``missing`` is also populated on a pass, when a sub-gate was skipped for
    lack of data. Those skips were always permissive here; recording them makes
    "passed cleanly" and "passed because we could not check" distinguishable.
    """

    passed: bool
    reason: str
    status: str = PASS
    missing: tuple[str, ...] = field(default=())

    def __iter__(self) -> Iterator[object]:
        return iter((self.passed, self.reason))


def _passed(reason: str, *missing: str) -> SignalResult:
    return SignalResult(True, reason, PASS, tuple(missing))


def _failed(reason: str) -> SignalResult:
    return SignalResult(False, reason, FAIL)


def _unknown(reason: str, *missing: str) -> SignalResult:
    return SignalResult(False, reason, UNKNOWN, tuple(missing))


class DengZhanSignals:
    def is_low_position(self, snapshot: MarketSnapshot, params: dict) -> SignalResult:
        high = (
            snapshot.metadata.get("rolling_high_250")
            or snapshot.metadata.get("high_250")
            or snapshot.historical_high
        )
        if not high or high <= 0:
            return _unknown("缺少历史最高价或250日高点，无法判断是否高位", "high_250")

        ratio = snapshot.price / high
        limit = float(params.get("max_price_to_high_ratio", 0.5))
        if ratio <= limit:
            return _passed(f"当前价/高点={ratio:.2f}，符合低位要求")
        return _failed(f"当前价/高点={ratio:.2f}，触发高位红线")

    def is_low_position_limit_up(self, snapshot: MarketSnapshot, params: dict) -> SignalResult:
        """S0 on this bar, or still inside the ARMED window opened by an earlier S0.

        The written spec sequences the strategy as IDLE -> ARMED -> ENTRY: the
        low-position limit-up arms a symbol, and the divergence that authorizes
        an entry may land on any of the next few bars. Requiring both on the
        same bar is a different, stricter strategy - measured over the whole
        market across 20 months it admits 77 entries where the sequenced form
        admits 124.

        ``dengzhan_armed_age`` is supplied by the caller because rule
        evaluation is stateless: it is the number of trading bars since the arming
        S0, so 0 means "S0 is on this bar". Callers that do not track it (the
        live snapshot path) simply get the same-bar behaviour as before.
        """

        same_bar = self.same_bar_s0(snapshot, params)
        if same_bar.passed:
            return same_bar

        window = int(params.get("armed_window_days") or 0)
        if window <= 0:
            return same_bar
        armed_age = snapshot.metadata.get("dengzhan_armed_age")
        if armed_age is None:
            return same_bar
        try:
            age = int(armed_age)
        except (TypeError, ValueError):
            return same_bar
        if 1 <= age <= window:
            return _passed(
                f"S0 在 {age} 个交易日前成立，仍在 {window} 日 ARMED 窗口内，等待分歧确认"
            )
        return same_bar

    def same_bar_s0(self, snapshot: MarketSnapshot, params: dict) -> SignalResult:
        """The S0 gate on this bar alone: low position, limit up, PB and cap band."""

        low_position = self.is_low_position(snapshot, params)
        if not low_position.passed:
            return low_position

        pct_change = snapshot.pct_change
        if pct_change is None:
            return _unknown("缺少涨跌幅，无法判断涨停", "pct_change")

        min_limit_up_pct = float(
            snapshot.metadata.get("limit_up_threshold") or params.get("min_limit_up_pct", 9.8)
        )
        if pct_change < min_limit_up_pct:
            return _failed(
                f"涨幅 {pct_change:.2f}% 未达到涨停候选阈值 {min_limit_up_pct:.2f}%"
            )

        missing: list[str] = []
        pb = snapshot.pb
        max_pb = params.get("max_pb")
        if pb is None:
            if max_pb is not None:
                missing.append("pb")
        elif max_pb is not None and pb > float(max_pb):
            return _failed(f"市净率 {pb:.2f} 高于阈值 {float(max_pb):.2f}")

        market_cap = snapshot.market_cap_billion
        min_cap = params.get("min_market_cap_billion")
        max_cap = params.get("max_market_cap_billion")

        if market_cap is None:
            if min_cap is not None or max_cap is not None:
                missing.append("market_cap_billion")
        else:
            if min_cap is not None and market_cap < float(min_cap):
                return _failed(f"总市值 {market_cap:.2f} 亿低于下限 {float(min_cap):.2f} 亿")
            if max_cap is not None and market_cap > float(max_cap):
                return _failed(f"总市值 {market_cap:.2f} 亿高于上限 {float(max_cap):.2f} 亿")

        if missing:
            labels = {"pb": "市净率", "market_cap_billion": "总市值"}
            return _unknown(
                f"缺少{'、'.join(labels[item] for item in missing)}数据，无法确认估值要求",
                *missing,
            )

        return _passed("低位、涨停、市净率、市值条件通过")

    def has_forced_divergence(self, snapshot: MarketSnapshot, params: dict) -> SignalResult:
        volume_ratio = snapshot.metadata.get("volume_ratio")
        if volume_ratio is None:
            return _unknown("缺少量比，无法判断强制分歧点", "volume_ratio")

        min_volume_ratio = float(params.get("min_volume_ratio", 1.5))
        if float(volume_ratio) >= min_volume_ratio:
            return _passed(f"量比 {float(volume_ratio):.2f} 达到强制分歧阈值")
        return _failed(f"量比 {float(volume_ratio):.2f} 未达到强制分歧阈值")

    def no_chasing_after_big_rise(self, snapshot: MarketSnapshot, params: dict) -> SignalResult:
        five_day_pct = snapshot.metadata.get("five_day_pct")
        if five_day_pct is None:
            # Historically permissive for a risk rule; keep it, but flag it.
            return _passed("缺少5日涨幅，暂不触发追高风控", "five_day_pct")

        big_rise_pct = float(params.get("big_rise_pct", 20))
        if float(five_day_pct) >= big_rise_pct:
            return _failed(f"5日涨幅 {float(five_day_pct):.2f}% 过高，需轻仓或回避")
        return _passed("未触发大涨后追高风控")
