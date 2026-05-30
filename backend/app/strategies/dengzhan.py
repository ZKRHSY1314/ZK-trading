from app.models import MarketSnapshot


class DengZhanSignals:
    def is_low_position(self, snapshot: MarketSnapshot, params: dict) -> tuple[bool, str]:
        high = (
            snapshot.metadata.get("rolling_high_250")
            or snapshot.metadata.get("high_250")
            or snapshot.historical_high
        )
        if not high or high <= 0:
            return False, "缺少历史最高价或250日高点，无法判断是否高位"

        ratio = snapshot.price / high
        limit = float(params.get("max_price_to_high_ratio", 0.5))
        if ratio <= limit:
            return True, f"当前价/高点={ratio:.2f}，符合低位要求"
        return False, f"当前价/高点={ratio:.2f}，触发高位红线"

    def is_low_position_limit_up(self, snapshot: MarketSnapshot, params: dict) -> tuple[bool, str]:
        low_position, low_reason = self.is_low_position(snapshot, params)
        if not low_position:
            return False, low_reason

        pct_change = snapshot.pct_change
        if pct_change is None:
            return False, "缺少涨跌幅，无法判断涨停"

        min_limit_up_pct = float(
            snapshot.metadata.get("limit_up_threshold") or params.get("min_limit_up_pct", 9.8)
        )
        if pct_change < min_limit_up_pct:
            return False, f"涨幅 {pct_change:.2f}% 未达到涨停候选阈值 {min_limit_up_pct:.2f}%"

        pb = snapshot.pb
        max_pb = params.get("max_pb")
        if pb is not None and max_pb is not None and pb > float(max_pb):
            return False, f"市净率 {pb:.2f} 高于阈值 {float(max_pb):.2f}"

        market_cap = snapshot.market_cap_billion
        min_cap = params.get("min_market_cap_billion")
        max_cap = params.get("max_market_cap_billion")

        if market_cap is not None:
            if min_cap is not None and market_cap < float(min_cap):
                return False, f"总市值 {market_cap:.2f} 亿低于下限 {float(min_cap):.2f} 亿"
            if max_cap is not None and market_cap > float(max_cap):
                return False, f"总市值 {market_cap:.2f} 亿高于上限 {float(max_cap):.2f} 亿"
        else:
            if min_cap is not None or max_cap is not None:
                return False, "缺少总市值数据，无法确认市值要求"

        return True, "低位、涨停、市净率、市值条件通过"

    def has_forced_divergence(self, snapshot: MarketSnapshot, params: dict) -> tuple[bool, str]:
        volume_ratio = snapshot.metadata.get("volume_ratio")
        if volume_ratio is None:
            return False, "缺少量比，无法判断强制分歧点"

        min_volume_ratio = float(params.get("min_volume_ratio", 1.5))
        if float(volume_ratio) >= min_volume_ratio:
            return True, f"量比 {float(volume_ratio):.2f} 达到强制分歧阈值"
        return False, f"量比 {float(volume_ratio):.2f} 未达到强制分歧阈值"

    def no_chasing_after_big_rise(self, snapshot: MarketSnapshot, params: dict) -> tuple[bool, str]:
        five_day_pct = snapshot.metadata.get("five_day_pct")
        if five_day_pct is None:
            return True, "缺少5日涨幅，暂不触发追高风控"

        big_rise_pct = float(params.get("big_rise_pct", 20))
        if float(five_day_pct) >= big_rise_pct:
            return False, f"5日涨幅 {float(five_day_pct):.2f}% 过高，需轻仓或回避"
        return True, "未触发大涨后追高风控"
