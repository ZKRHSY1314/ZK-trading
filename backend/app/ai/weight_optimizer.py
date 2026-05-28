REQUIRED_METRICS = ("total_return", "max_drawdown", "win_rate", "profit_loss_ratio")


class WeightOptimizer:
    def validate_candidate_update(
        self,
        metrics_before: dict[str, float],
        metrics_after: dict[str, float],
    ) -> dict:
        missing = [
            key
            for key in REQUIRED_METRICS
            if key not in metrics_before or key not in metrics_after
        ]
        if missing:
            return {
                "accepted": False,
                "reason": f"缺少验证指标: {', '.join(missing)}",
            }

        checks = {
            "total_return_improved": metrics_after["total_return"] > metrics_before["total_return"],
            "max_drawdown_not_worse": metrics_after["max_drawdown"] <= metrics_before["max_drawdown"],
            "win_rate_not_worse": metrics_after["win_rate"] >= metrics_before["win_rate"],
            "profit_loss_ratio_not_worse": (
                metrics_after["profit_loss_ratio"] >= metrics_before["profit_loss_ratio"]
            ),
        }

        accepted = all(checks.values())
        return {
            "accepted": accepted,
            "checks": checks,
            "reason": "全部验证指标通过" if accepted else "至少一个验证指标未通过，拒绝自动调权",
        }
