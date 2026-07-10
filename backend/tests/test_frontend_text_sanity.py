from pathlib import Path


def test_high_risk_frontend_labels_are_readable_chinese():
    frontend_root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    source = (frontend_root / "components" / "TradingDashboard.vue").read_text(encoding="utf-8")

    for text in [
        "智投 A股",
        "AI 交易驾驶舱",
        "搜索股票 / 指数 / 资讯 / 策略",
        "模拟交易计划",
        "生成模拟买入计划",
        "真实下单入口：需人工确认 / 实盘未启用",
        "市场概览",
        "五档行情",
        "Release Gate",
    ]:
        assert text in source

    for mojibake in [
        "鐎圭偟娲忕粋浣烘暏",
        "鐎圭偟娲忛悩鑸?",
        "閸掔鏅㈤幒褍鍩?",
        "閺堫剙婀撮崐娆撯偓澶嬬潨",
        "娑撳秴鎯庨悽銊﹀焻閸ョ偓鍨ㄧ€圭偟娲?",
        "瀹炵洏绂佺敤",
        "鍒锋柊璇婃柇",
    ]:
        assert mojibake not in source
