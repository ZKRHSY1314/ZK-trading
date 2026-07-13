from pathlib import Path


def test_high_risk_frontend_labels_are_readable_chinese():
    frontend_root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    source = (frontend_root / "components" / "TradingDashboard.vue").read_text(encoding="utf-8")
    api_source = (frontend_root / "api" / "cockpit.ts").read_text(encoding="utf-8")

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
        "Market Pulse",
        "立即捕捉",
        "运行控制平面",
        'data-testid="public-opinion-capture-button"',
        'data-testid="control-plane-run-button"',
        'data-testid="control-plane-status"',
        "/api/public-opinion/context/latest?limit=8",
        "/api/public-opinion/runs/latest",
    ]:
        assert text in source

    assert 'fetchJson<ControlPlaneRunResult>("/api/control-plane/run-once"' in api_source
    assert 'method: "POST"' in api_source

    assert "资金流、板块热图和资讯源等待下一步接入" not in source

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


def test_browser_adapter_targets_the_mounted_trading_dashboard():
    project_root = Path(__file__).resolve().parents[2]
    adapter = (project_root / "frontend" / "scripts" / "browser_control_adapter.mjs").read_text(
        encoding="utf-8"
    )

    for selector in [
        "trading-dashboard",
        "live-trading-disabled-button",
        "public-opinion-capture-button",
        "control-plane-run-button",
        "control-plane-status",
        "public-opinion-news",
    ]:
        assert selector in adapter
    for legacy_selector in [
        "local-scan-button",
        "automation-run-button",
        "simulation-plan-button",
    ]:
        assert legacy_selector not in adapter
    assert "live_trading_enabled !== false" in adapter
