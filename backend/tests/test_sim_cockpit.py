from app.sim_cockpit.service import SimCockpitService
from app.sim_cockpit.desktop_adapter import TonghuashunDesktopAdapter
from app.learning.dataset2_stage import Dataset2StageService


def _reset_sim_cockpit(store) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM sim_cockpit_readbacks")
        conn.execute("DELETE FROM sim_cockpit_actions")
        conn.execute("DELETE FROM sim_cockpit_window_verifications")
        conn.execute("DELETE FROM events WHERE event_type LIKE 'sim_cockpit_%'")
        conn.execute("DELETE FROM events WHERE event_type LIKE 'dataset2_%'")


def _verify_simulation_window(service: SimCockpitService) -> dict:
    return service.verify_window(
        window_title="Tonghuashun hexin mncg simulation window",
        visible_text="mncg simulation \u6a21\u62df\u7092\u80a1 \u6a21\u62df\u4e70\u5165 \u6a21\u62df\u5356\u51fa",
        raw_payload={"process_name": "hexin.exe", "window_class": "Tonghuashun"},
        detected_items=[{"type": "mode", "value": "mncg"}],
        verified_by="pytest",
        confidence=0.95,
    )


def test_sim_cockpit_blocks_unverified_actions(test_db):
    _reset_sim_cockpit(test_db)
    service = SimCockpitService()

    action = service.buy(
        symbol="SZ002081",
        price=10.0,
        quantity=100,
        signal_source="pytest",
        risk_result={"simulation_allowed": True, "all_gates_passed": True},
    )

    assert action["status"] == "blocked"
    assert "blocked_needs_verified_simulation_window" in action["blocked_reasons"]
    assert action["execution"]["real_screen_click_executed"] is False
    assert action["simulation_only"] is True
    assert action["live_trading_enabled"] is False


def test_verify_window_accepts_mncg_simulation_and_blocks_real_terms(test_db):
    _reset_sim_cockpit(test_db)
    service = SimCockpitService()

    verified = _verify_simulation_window(service)
    assert verified["status"] == "verified"
    assert verified["simulation_mode_detected"] is True
    assert verified["real_trading_blocked"] is True

    menu_risk = service.verify_window(
        window_title="Tonghuashun hexin mncg simulation window",
        visible_text="mncg \u6a21\u62df\u7092\u80a1 menu \u94f6\u8bc1\u8f6c\u8d26 \u5238\u5546",
        raw_payload={"process_name": "hexin.exe"},
        verified_by="pytest",
        confidence=0.9,
    )
    assert menu_risk["status"] == "verified"
    assert menu_risk["dangerous_terms"] == []
    assert "\u94f6\u8bc1\u8f6c\u8d26" in menu_risk["raw_payload"]["non_blocking_risk_terms"]

    blocked = service.verify_window(
        window_title="\u540c\u82b1\u987a \u771f\u5b9e\u59d4\u6258 \u5238\u5546\u767b\u5f55",
        visible_text="\u8d44\u91d1\u8d26\u53f7 \u94f6\u8bc1\u8f6c\u8d26 \u5b9e\u76d8\u4e70\u5165",
        raw_payload={"process_name": "hexin.exe"},
        verified_by="pytest",
        confidence=0.8,
    )
    assert blocked["status"] == "blocked"
    assert "dangerous_real_trading_terms_detected" in blocked["blocked_reasons"]

    status = service.status()
    assert status["status"] == "blocked"
    assert status["simulation_actions_allowed"] is False


def test_buy_sell_cancel_payload_validation_and_audit(test_db):
    _reset_sim_cockpit(test_db)
    service = SimCockpitService()
    verification = _verify_simulation_window(service)

    buy = service.buy(
        symbol="SZ002081",
        price=10.0,
        quantity=100,
        signal_source="pytest_signal",
        risk_result={"simulation_allowed": True, "all_gates_passed": True},
        window_verification_id=verification["id"],
        requested_by="pytest",
    )
    assert buy["status"] == "executed"
    assert buy["execution"]["simulated_account_action"] is True
    assert buy["execution"]["real_screen_click_executed"] is False

    duplicate_buy = service.buy(
        symbol="SZ002081",
        price=10.0,
        quantity=100,
        signal_source="pytest_signal",
        risk_result={"simulation_allowed": True, "all_gates_passed": True},
        window_verification_id=verification["id"],
        requested_by="pytest",
    )
    assert duplicate_buy["status"] == "blocked"
    assert "symbol_daily_buy_limit_reached" in duplicate_buy["blocked_reasons"]

    sell = service.sell(
        symbol="SZ002081",
        price=10.5,
        quantity=100,
        signal_source="pytest_signal",
        risk_result={"simulation_allowed": True, "all_gates_passed": True},
        window_verification_id=verification["id"],
        requested_by="pytest",
    )
    assert sell["status"] == "executed"

    cancel = service.cancel(
        order_id="SIM-ORDER-1",
        signal_source="pytest_signal",
        window_verification_id=verification["id"],
        requested_by="pytest",
    )
    assert cancel["status"] == "executed"

    latest = service.latest_actions(limit=5)
    assert len(latest) == 4
    assert latest[0]["action_type"] == "cancel"
    assert latest[0]["execution"]["real_screen_click_executed"] is False

    event_count = test_db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM events WHERE event_type LIKE 'sim_cockpit_action_%'"
    )
    assert event_count["cnt"] == 4


def test_sim_cockpit_api_smoke_and_dataset2_dry_run(client, test_db):
    _reset_sim_cockpit(test_db)

    status_resp = client.get("/api/sim-cockpit/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["live_trading_enabled"] is False

    verify_resp = client.post(
        "/api/sim-cockpit/verify-window",
        json={
            "window_title": "Tonghuashun hexin mncg simulation window",
            "visible_text": "mncg simulation \u6a21\u62df\u7092\u80a1",
            "raw_payload": {"process_name": "hexin.exe"},
            "verified_by": "pytest",
            "confidence": 0.95,
        },
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["status"] == "verified"

    buy_resp = client.post(
        "/api/sim-cockpit/actions/buy",
        json={
            "symbol": "SZ002081",
            "price": 10.0,
            "quantity": 100,
            "signal_source": "pytest_api",
            "risk_result": {"simulation_allowed": True, "all_gates_passed": True},
            "window_verification_id": verify_resp.json()["id"],
            "requested_by": "pytest",
        },
    )
    assert buy_resp.status_code == 200
    assert buy_resp.json()["status"] == "executed"

    latest_resp = client.get("/api/sim-cockpit/actions/latest?limit=5")
    assert latest_resp.status_code == 200
    assert latest_resp.json()[0]["action_type"] == "buy"

    cockpit_run_resp = client.post("/api/automation/cycles/simulation-cockpit-run?limit=2")
    assert cockpit_run_resp.status_code == 200
    assert cockpit_run_resp.json()["summary"]["simulation_only"] is True

    summary_resp = client.get("/api/learning/dataset2/stage-summary")
    assert summary_resp.status_code == 200
    assert summary_resp.json()["training_allowed"] is False

    dry_run_resp = client.post(
        "/api/learning/dataset2/training/dry-run",
        json={"limit": 20, "requested_by": "pytest"},
    )
    assert dry_run_resp.status_code == 200
    assert dry_run_resp.json()["training_executed"] is False
    assert dry_run_resp.json()["model_artifact_written"] is False


def test_dataset2_controlled_training_status_and_run_from_sim_cockpit_samples(client, test_db):
    _reset_sim_cockpit(test_db)

    empty_status = client.get("/api/learning/dataset2/training/status?limit=1&min_samples=4")
    assert empty_status.status_code == 200
    assert empty_status.json()["status"] == "blocked"
    assert "insufficient_samples" in empty_status.json()["blocked_reasons"]
    assert empty_status.json()["model_artifact_write_enabled"] is False

    service = SimCockpitService()
    verification = _verify_simulation_window(service)
    first = service.buy(
        symbol="SZ002081",
        price=10.0,
        quantity=100,
        signal_source="pytest_dataset2",
        risk_result={"simulation_allowed": True, "all_gates_passed": True},
        window_verification_id=verification["id"],
        requested_by="pytest",
    )
    second = service.buy(
        symbol="SZ002081",
        price=10.0,
        quantity=100,
        signal_source="pytest_dataset2",
        risk_result={"simulation_allowed": True, "all_gates_passed": True},
        window_verification_id=verification["id"],
        requested_by="pytest",
    )
    assert first["status"] == "executed"
    assert second["status"] == "blocked"

    status = client.get("/api/learning/dataset2/training/status?limit=20")
    assert status.status_code == 200
    status_json = status.json()
    assert status_json["training_allowed"] is True
    assert status_json["sample_candidate_count"] >= 4
    assert status_json["label_counts"]["action_feasible"] >= 1
    assert status_json["label_counts"]["blocked_or_rejected"] >= 1

    run = client.post(
        "/api/learning/dataset2/training/run",
        json={"limit": 20, "requested_by": "pytest"},
    )
    assert run.status_code == 200
    run_json = run.json()
    assert run_json["status"] == "completed"
    assert run_json["training_executed"] is True
    assert run_json["model_artifact_written"] is False
    assert run_json["writes_learning_samples"] is False
    assert run_json["live_trading_enabled"] is False
    assert run_json["metrics"]["validation_count"] >= 1

    latest = client.get("/api/learning/dataset2/training/runs/latest")
    assert latest.status_code == 200
    assert latest.json()["payload"]["event_id"] == run_json["event_id"]

    direct_latest = Dataset2StageService().latest_training_run()
    assert direct_latest["payload"]["model_artifact_written"] is False


class FakeDesktopAdapter:
    def build_coordinate_plan(self, *args, **kwargs):
        return {
            "status": "ready_for_click",
            "plan_ready_for_click": True,
            "steps": [{"name": "submit_button", "kind": "click", "x": 10, "y": 20}],
            "missing_controls": [],
            "confidence": 0.95,
        }

    def capture_window_screenshot(self, *args, **kwargs):
        return {
            "status": "captured",
            "artifact_ref": "artifact://pytest/sim-cockpit-screen",
            "artifact_hash": "hash",
            "ocr_executed": False,
        }

    def execute_coordinate_plan(self, *args, **kwargs):
        return {"status": "executed", "real_screen_click_executed": True}


class MissingMncgDesktopAdapter:
    def detect(self, *args, **kwargs):
        return {
            "schema_version": "sim_cockpit_desktop_detection.v1",
            "status": "blocked",
            "provider": "pytest_win32_adapter",
            "target_title": None,
            "best_window": {
                "hwnd": 114,
                "title": "\u7f51\u4e0a\u80a1\u7968\u4ea4\u6613\u7cfb\u7edf5.0",
                "process_name": "xiadan.exe",
                "rect": {"left": 100, "top": 60, "right": 1200, "bottom": 700},
                "child_texts": ["\u4e70\u5165", "\u5356\u51fa", "\u64a4\u5355"],
                "positive_terms": [],
                "process_terms": ["xiadan"],
                "dangerous_terms": [],
            },
            "windows": [],
            "blocked_reasons": ["missing_mncg_or_simulation_marker"],
            "simulation_only": True,
            "live_trading_enabled": False,
        }


def test_desktop_detection_does_not_verify_from_missing_marker_reason(test_db):
    _reset_sim_cockpit(test_db)
    service = SimCockpitService()
    service.desktop_adapter = MissingMncgDesktopAdapter()

    result = service.detect_desktop_window(record=True)

    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["missing_mncg_or_simulation_marker"]
    assert result["verification"]["status"] == "blocked"
    assert "missing_mncg_or_simulation_marker" in result["verification"]["blocked_reasons"]
    assert result["verification"]["simulation_mode_detected"] is False
    assert result["verification"]["raw_payload"]["blocked_reason_count"] == 1


def test_uia_coordinate_anchors_build_ready_buy_plan():
    adapter = TonghuashunDesktopAdapter()
    controls = [
        {
            "name": "买入[F1]",
            "control_type": "TreeItemControl",
            "automation_id": "",
            "rect": {"left": 188, "top": 214, "right": 261, "bottom": 256, "width": 73, "height": 42},
        },
        {
            "name": "",
            "control_type": "EditControl",
            "automation_id": "1032",
            "rect": {"left": 588, "top": 274, "right": 798, "bottom": 310, "width": 210, "height": 36},
        },
        {
            "name": "",
            "control_type": "EditControl",
            "automation_id": "1033",
            "rect": {"left": 588, "top": 358, "right": 740, "bottom": 394, "width": 152, "height": 36},
        },
        {
            "name": "",
            "control_type": "EditControl",
            "automation_id": "1034",
            "rect": {"left": 588, "top": 493, "right": 740, "bottom": 529, "width": 152, "height": 36},
        },
        {
            "name": "买入",
            "control_type": "ButtonControl",
            "automation_id": "1006",
            "rect": {"left": 588, "top": 538, "right": 761, "bottom": 580, "width": 173, "height": 42},
        },
    ]

    anchors = adapter._coordinate_anchors_from_uia_controls(controls)
    buy = anchors["buy"]
    assert buy["buy_tab"]["control_name"] == "买入[F1]"
    assert buy["submit_button"]["automation_id"] == "1006"
    assert buy["buy_tab"]["y"] != buy["submit_button"]["y"]

    plan = adapter.build_coordinate_plan(
        "buy",
        window={"coordinate_anchors": anchors},
        symbol="SZ002081",
        price=10.0,
        quantity=100,
    )
    assert plan["status"] == "ready_for_click"
    assert plan["plan_ready_for_click"] is True
    assert plan["missing_controls"] == []
    assert [step["name"] for step in plan["steps"]] == [
        "buy_tab",
        "symbol_input",
        "price_input",
        "quantity_input",
        "submit_button",
    ]
    assert plan["steps"][1]["automation_id"] == "1032"
    assert plan["steps"][1]["value"] == "002081"
    assert plan["steps"][2]["automation_id"] == "1033"
    assert plan["steps"][3]["automation_id"] == "1034"


def test_uia_coordinate_anchors_accept_normal_chinese_names():
    adapter = TonghuashunDesktopAdapter()
    controls = [
        {
            "name": "买入[F1]",
            "control_type": "TreeItemControl",
            "automation_id": "",
            "rect": {"left": 188, "top": 214, "right": 261, "bottom": 256, "width": 73, "height": 42},
        },
        {
            "name": "卖出[F2]",
            "control_type": "TreeItemControl",
            "automation_id": "",
            "rect": {"left": 188, "top": 256, "right": 261, "bottom": 298, "width": 73, "height": 42},
        },
        {
            "name": "撤单[F3]",
            "control_type": "TreeItemControl",
            "automation_id": "",
            "rect": {"left": 188, "top": 298, "right": 261, "bottom": 340, "width": 73, "height": 42},
        },
        {
            "name": "",
            "control_type": "EditControl",
            "automation_id": "1032",
            "rect": {"left": 588, "top": 274, "right": 798, "bottom": 310, "width": 210, "height": 36},
        },
        {
            "name": "",
            "control_type": "EditControl",
            "automation_id": "1033",
            "rect": {"left": 588, "top": 358, "right": 740, "bottom": 394, "width": 152, "height": 36},
        },
        {
            "name": "",
            "control_type": "EditControl",
            "automation_id": "1034",
            "rect": {"left": 588, "top": 493, "right": 740, "bottom": 529, "width": 152, "height": 36},
        },
        {
            "name": "买入",
            "control_type": "ButtonControl",
            "automation_id": "1006",
            "rect": {"left": 588, "top": 538, "right": 761, "bottom": 580, "width": 173, "height": 42},
        },
    ]

    anchors = adapter._coordinate_anchors_from_uia_controls(controls)

    assert anchors["buy"]["buy_tab"]["control_name"] == "买入[F1]"
    assert anchors["buy"]["submit_button"]["control_name"] == "买入"
    assert anchors["sell"]["sell_tab"]["control_name"] == "卖出[F2]"
    assert anchors["cancel"]["cancel_tab"]["control_name"] == "撤单[F3]"


def test_desktop_adapter_does_not_treat_page_text_as_process_marker():
    adapter = TonghuashunDesktopAdapter()

    codex_like = adapter._score_window(
        {
            "title": "Codex",
            "process_path": "C:\\Users\\lenovo\\AppData\\Local\\Programs\\Codex\\Codex.exe",
            "process_name": "Codex.exe",
            "child_texts": ["mncg114 \u540c\u82b1\u987a \u6a21\u62df\u7092\u80a1 xiadan.exe"],
            "uia": {"controls": []},
            "coordinate_anchors": {},
        },
        target_title=None,
    )
    assert codex_like["positive_terms"]
    assert codex_like["process_terms"] == []

    tonghuashun_like = adapter._score_window(
        {
            "title": "\u7f51\u4e0a\u80a1\u7968\u4ea4\u6613\u7cfb\u7edf5.0",
            "process_path": "D:\\\u540c\u82b1\u987a\u8f6f\u4ef6\\\u540c\u82b1\u987a\\xiadan.exe",
            "process_name": "xiadan.exe",
            "child_texts": ["mncg114 \u6a21\u62df\u7092\u80a1"],
            "uia": {"controls": []},
            "coordinate_anchors": {},
        },
        target_title=None,
    )
    assert "xiadan" in tonghuashun_like["process_terms"]
    assert tonghuashun_like["score"] > codex_like["score"]


def test_screen_click_requires_desktop_adapter_verification(test_db):
    _reset_sim_cockpit(test_db)
    service = SimCockpitService()
    verification = _verify_simulation_window(service)

    blocked = service.buy(
        symbol="SZ002081",
        price=10.0,
        quantity=100,
        signal_source="pytest_signal",
        risk_result={"simulation_allowed": True, "all_gates_passed": True},
        window_verification_id=verification["id"],
        requested_by="pytest",
        execution_mode="screen_click_simulation",
        screen_confirmation="SIMULATION_SCREEN_CLICK",
        screen_coordinates={
            "buy_tab": {"x": 1, "y": 1},
            "symbol_input": {"x": 2, "y": 2},
            "price_input": {"x": 3, "y": 3},
            "quantity_input": {"x": 4, "y": 4},
            "submit_button": {"x": 5, "y": 5},
        },
    )

    assert blocked["status"] == "blocked"
    assert "screen_click_requires_desktop_adapter_verification" in blocked["blocked_reasons"]
    assert blocked["execution"]["real_screen_click_executed"] is False


def test_screen_click_executes_only_with_desktop_verification_and_readback(test_db):
    _reset_sim_cockpit(test_db)
    service = SimCockpitService()
    verification = service.verify_window(
        window_title="Tonghuashun hexin mncg simulation window",
        visible_text="mncg simulation \u6a21\u62df\u7092\u80a1 \u6a21\u62df\u4e70\u5165",
        raw_payload={
            "source": "desktop_adapter",
            "process_name": "hexin.exe",
            "window": {"hwnd": 1, "rect": {"left": 0, "top": 0, "width": 800, "height": 600}},
        },
        detected_items=[{"type": "mode", "value": "mncg"}],
        verified_by="pytest_desktop",
        confidence=0.98,
    )
    service.desktop_adapter = FakeDesktopAdapter()

    executed = service.buy(
        symbol="SZ002081",
        price=10.0,
        quantity=100,
        signal_source="pytest_signal",
        risk_result={"simulation_allowed": True, "all_gates_passed": True},
        window_verification_id=verification["id"],
        requested_by="pytest",
        execution_mode="screen_click_simulation",
        screen_confirmation="SIMULATION_SCREEN_CLICK",
        screen_coordinates={
            "buy_tab": {"x": 1, "y": 1},
            "symbol_input": {"x": 2, "y": 2},
            "price_input": {"x": 3, "y": 3},
            "quantity_input": {"x": 4, "y": 4},
            "submit_button": {"x": 5, "y": 5},
        },
    )

    assert executed["status"] == "executed"
    assert executed["execution"]["real_screen_click_executed"] is True
    readbacks = service.latest_readbacks(limit=5)
    assert readbacks[0]["action_id"] == executed["id"]
    assert readbacks[0]["status"] == "executed"


def test_window_detection_api_is_safe_when_no_window_found(client, test_db):
    _reset_sim_cockpit(test_db)

    resp = client.get("/api/sim-cockpit/window-detection?record=false")
    assert resp.status_code == 200
    assert resp.json()["simulation_only"] is True
    assert resp.json()["live_trading_enabled"] is False
