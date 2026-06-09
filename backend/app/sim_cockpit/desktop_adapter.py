from __future__ import annotations

import ctypes
import hashlib
import json
import re
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings


SIMULATION_POSITIVE_TERMS = (
    "mncg",
    "simulation",
    "simulated",
    "paper",
    "\u6a21\u62df",
    "\u6a21\u62df\u7092\u80a1",
    "\u6a21\u62df\u76d8",
    "\u6a21\u62df\u4e70\u5165",
    "\u6a21\u62df\u5356\u51fa",
    "\u6a21\u62df\u59d4\u6258",
)

TONGHUASHUN_PROCESS_TERMS = (
    "hexin",
    "xiadan",
    "tonghuashun",
    "ths",
    "\u540c\u82b1\u987a",
)

DANGEROUS_REAL_TRADING_TERMS = (
    "broker_login",
    "broker account",
    "credential",
    "password",
    "live_trading",
    "real_money",
    "real_order",
    "cash_transfer",
    "bank_transfer",
    "broker_submit",
    "\u5b9e\u76d8",
    "\u771f\u5b9e",
    "\u666e\u901a\u4ea4\u6613",
    "\u771f\u5b9e\u59d4\u6258",
    "\u59d4\u6258\u4ea4\u6613",
    "\u5238\u5546\u767b\u5f55",
    "\u5238\u5546",
    "\u8d44\u91d1\u8d26\u53f7",
    "\u94f6\u8bc1",
    "\u94f6\u8bc1\u8f6c\u8d26",
    "\u878d\u8d44\u878d\u5238",
)

SIMULATION_MENU_RISK_TERMS = (
    "\u5238\u5546",
    "\u59d4\u6258\u4ea4\u6613",
    "\u94f6\u8bc1",
    "\u94f6\u8bc1\u8f6c\u8d26",
)

EXECUTION_MODES = {
    "audit_fixture",
    "detect_only",
    "dry_run_screen",
    "screen_click_simulation",
}

SCREEN_CLICK_CONFIRMATION = "SIMULATION_SCREEN_CLICK"
MIN_CLICK_PLAN_CONFIDENCE = 0.8


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _terms_found(text: str, terms: tuple[str, ...]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def _hash_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _load_uiautomation() -> Any | None:
    try:
        import uiautomation as auto  # type: ignore[import-not-found]

        return auto
    except Exception:
        return None


class TonghuashunDesktopAdapter:
    """Small Win32 adapter for verified Tonghuashun simulated-account screens."""

    provider = "win32_desktop_adapter"

    def capabilities(self) -> dict[str, Any]:
        uia_available = _load_uiautomation() is not None if sys.platform.startswith("win") else False
        return {
            "provider": self.provider,
            "status": "available" if sys.platform.startswith("win") else "unsupported_platform",
            "platform": sys.platform,
            "detect_supported": sys.platform.startswith("win"),
            "uiautomation_supported": uia_available,
            "dry_run_supported": True,
            "screen_click_supported": sys.platform.startswith("win"),
            "screenshot_supported": sys.platform.startswith("win"),
            "ocr_supported": False,
            "requires_desktop_verified_window": True,
            "requires_coordinate_anchors_for_click": True,
            "allowed_execution_modes": sorted(EXECUTION_MODES),
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def detect(self, target_title: str | None = None, limit: int = 10) -> dict[str, Any]:
        if not sys.platform.startswith("win"):
            return {
                "schema_version": "sim_cockpit_desktop_detection.v1",
                "status": "blocked",
                "provider": self.provider,
                "reason": "windows_desktop_required",
                "windows": [],
                "best_window": None,
                "blocked_reasons": ["windows_desktop_required"],
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }

        self._ensure_dpi_awareness()
        windows = self._enumerate_windows()
        scored = [self._score_window(item, target_title=target_title) for item in windows]
        scored = sorted(scored, key=lambda item: item["score"], reverse=True)
        candidates = [item for item in scored if item["score"] > 0][: max(1, min(int(limit or 10), 50))]
        best = candidates[0] if candidates else None

        blocked_reasons: list[str] = []
        if settings.enable_live_trading:
            blocked_reasons.append("live_trading_enabled")
        if not best:
            blocked_reasons.append("tonghuashun_window_not_found")
        else:
            if best["dangerous_terms"]:
                blocked_reasons.append("dangerous_real_trading_terms_detected")
            if not best["process_terms"]:
                blocked_reasons.append("missing_tonghuashun_process_marker")
            if not best["positive_terms"]:
                blocked_reasons.append("missing_mncg_or_simulation_marker")

        status = "verified" if best and not blocked_reasons else "blocked"
        if not best and not settings.enable_live_trading:
            status = "needs_simulation_window"

        return {
            "schema_version": "sim_cockpit_desktop_detection.v1",
            "status": status,
            "provider": self.provider,
            "target_title": target_title,
            "best_window": best,
            "windows": candidates,
            "blocked_reasons": blocked_reasons,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def build_coordinate_plan(
        self,
        action_type: str,
        window: dict[str, Any] | None,
        symbol: str | None = None,
        price: float | None = None,
        quantity: int | None = None,
        order_id: str | None = None,
        coordinate_anchors: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action = action_type.strip().lower()
        raw_anchors = coordinate_anchors or (window or {}).get("coordinate_anchors") or {}
        anchors = raw_anchors.get(action, raw_anchors) if isinstance(raw_anchors, dict) else {}
        required = self._required_controls(action)
        missing = [name for name in required if name not in anchors]
        steps: list[dict[str, Any]] = []
        source = "coordinate_anchors"
        confidence = 0.95
        if missing:
            steps = self._estimated_steps(action, window, symbol=symbol, price=price, quantity=quantity, order_id=order_id)
            source = "estimated_from_window_rect"
            confidence = 0.35 if steps else 0.0
        else:
            steps = self._anchored_steps(
                action,
                anchors,
                symbol=symbol,
                price=price,
                quantity=quantity,
                order_id=order_id,
            )

        plan_ready_for_click = bool(steps) and not missing and confidence >= MIN_CLICK_PLAN_CONFIDENCE
        return {
            "schema_version": "sim_cockpit_coordinate_plan.v1",
            "status": "ready_for_click" if plan_ready_for_click else "needs_coordinate_anchors",
            "action_type": action,
            "source": source,
            "confidence": confidence,
            "required_controls": required,
            "missing_controls": missing,
            "steps": steps,
            "plan_ready_for_click": plan_ready_for_click,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def capture_window_screenshot(
        self,
        window: dict[str, Any] | None,
        phase: str,
        action_type: str,
    ) -> dict[str, Any]:
        if not sys.platform.startswith("win"):
            return {"status": "blocked", "reason": "windows_desktop_required", "artifact_ref": None}
        self._ensure_dpi_awareness()
        rect = (window or {}).get("rect") or {}
        uia_rect = ((window or {}).get("uia") or {}).get("root_rect") or {}
        if uia_rect:
            rect = uia_rect
        left = int(rect.get("left") or 0)
        top = int(rect.get("top") or 0)
        width = max(1, int(rect.get("width") or 0))
        height = max(1, int(rect.get("height") or 0))
        if width <= 1 or height <= 1:
            return {"status": "blocked", "reason": "window_rect_unavailable", "artifact_ref": None}

        out_dir = _project_root() / "backend" / "logs" / "sim_cockpit_screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_phase = "".join(ch for ch in phase if ch.isalnum() or ch in {"_", "-"})
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{action_type}_{safe_phase}.png"
        out_path = out_dir / filename
        safe_out_path = str(out_path).replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            f"$bmp=New-Object Drawing.Bitmap {width},{height}; "
            "$g=[Drawing.Graphics]::FromImage($bmp); "
            f"$g.CopyFromScreen({left},{top},0,0,$bmp.Size); "
            f"$bmp.Save('{safe_out_path}', [Drawing.Imaging.ImageFormat]::Png); "
            "$g.Dispose(); $bmp.Dispose();"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            return {"status": "failed", "reason": str(exc), "artifact_ref": None}
        if completed.returncode != 0 or not out_path.exists():
            return {
                "status": "failed",
                "reason": (completed.stderr or completed.stdout or "screenshot_failed").strip(),
                "artifact_ref": None,
            }
        return {
            "status": "captured",
            "artifact_ref": str(out_path),
            "artifact_hash": _hash_file(out_path),
            "pixel_data_stored": True,
            "ocr_executed": False,
        }

    def execute_coordinate_plan(self, window: dict[str, Any] | None, plan: dict[str, Any]) -> dict[str, Any]:
        if not sys.platform.startswith("win"):
            return {"status": "failed", "reason": "windows_desktop_required", "real_screen_click_executed": False}
        self._ensure_dpi_awareness()
        if not plan.get("plan_ready_for_click"):
            return {
                "status": "blocked",
                "reason": "coordinate_plan_not_ready_for_click",
                "real_screen_click_executed": False,
            }
        hwnd = int((window or {}).get("hwnd") or 0)
        if hwnd:
            try:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.2)
            except Exception:
                pass

        try:
            input_methods: list[dict[str, Any]] = []
            input_snapshot: dict[str, Any] | None = None
            for step in plan.get("steps") or []:
                if step.get("kind") == "click":
                    if step.get("name") == "submit_button" and input_methods and input_snapshot is None:
                        input_snapshot = self.capture_window_screenshot(
                            window,
                            phase="inputs",
                            action_type=str(plan.get("action_type") or "action"),
                        )
                    self._click(int(step["x"]), int(step["y"]))
                elif step.get("kind") == "input":
                    value = self._format_input_value(step.get("value"))
                    uia_set = False
                    if hwnd and step.get("automation_id"):
                        uia_set = self._set_uia_value(hwnd, str(step.get("automation_id")), value)
                    input_methods.append(
                        {
                            "name": step.get("name"),
                            "automation_id": step.get("automation_id"),
                            "method": "uia_value_pattern+sendinput" if uia_set else "sendinput_fallback",
                        }
                    )
                    self._click(int(step["x"]), int(step["y"]))
                    self._send_ctrl_a()
                    self._send_text(value)
                time.sleep(0.08)
        except Exception as exc:
            return {"status": "failed", "reason": str(exc), "real_screen_click_executed": True}
        return {
            "status": "executed",
            "reason": None,
            "real_screen_click_executed": True,
            "input_methods": input_methods,
            "input_snapshot": input_snapshot,
        }

    def _enumerate_windows(self) -> list[dict[str, Any]]:
        user32 = ctypes.windll.user32
        results: list[dict[str, Any]] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            title = self._window_text(hwnd)
            if not title:
                return True
            rect = self._window_rect(hwnd)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            process_path = self._process_path(int(pid.value))
            child_texts = self._child_texts(hwnd, limit=180)
            uia = self._uia_snapshot(int(hwnd))
            if uia.get("status") == "available":
                child_texts = [*child_texts, *uia.get("texts", [])[:80]]
            results.append(
                {
                    "hwnd": int(hwnd),
                    "pid": int(pid.value),
                    "title": title,
                    "process_path": process_path,
                    "process_name": Path(process_path).name if process_path else None,
                    "rect": rect,
                    "child_texts": child_texts,
                    "uia": uia,
                    "coordinate_anchors": uia.get("coordinate_anchors") or {},
                }
            )
            return True

        user32.EnumWindows(enum_proc, 0)
        return results

    def _score_window(self, window: dict[str, Any], target_title: str | None) -> dict[str, Any]:
        identity_text = " ".join(
            [
                str(window.get("title") or ""),
                str(window.get("process_path") or ""),
                str(window.get("process_name") or ""),
            ]
        )
        visible_text = " ".join(
            [
                " ".join(str(item) for item in window.get("child_texts") or []),
                " ".join(str(item.get("name") or "") for item in ((window.get("uia") or {}).get("controls") or [])),
            ]
        )
        text = " ".join([identity_text, visible_text])
        positive = _terms_found(text, SIMULATION_POSITIVE_TERMS)
        process = _terms_found(identity_text, TONGHUASHUN_PROCESS_TERMS)
        dangerous = _terms_found(text, DANGEROUS_REAL_TRADING_TERMS)
        non_blocking_risk_terms: list[str] = []
        if positive and ("mncg" in positive or "\u6a21\u62df\u7092\u80a1" in positive):
            non_blocking_risk_terms = [term for term in dangerous if term in SIMULATION_MENU_RISK_TERMS]
            dangerous = [term for term in dangerous if term not in SIMULATION_MENU_RISK_TERMS]
        score = len(positive) * 4 + len(process) * 3 - len(dangerous) * 20
        if (window.get("coordinate_anchors") or {}).get("buy"):
            score += 3
        if target_title and target_title.lower() in str(window.get("title") or "").lower():
            score += 5
        return {
            **window,
            "score": score,
            "positive_terms": positive,
            "process_terms": process,
            "dangerous_terms": dangerous,
            "non_blocking_risk_terms": non_blocking_risk_terms,
            "evidence_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }

    def _ensure_dpi_awareness(self) -> None:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    def _uia_snapshot(self, hwnd: int) -> dict[str, Any]:
        auto = _load_uiautomation()
        if auto is None:
            return {"status": "unavailable", "reason": "uiautomation_not_installed"}
        script = r"""
import json
import sys

def rect_payload(control):
    rect = getattr(control, "BoundingRectangle", None)
    if rect is None:
        return {}
    left = int(getattr(rect, "left", 0) or 0)
    top = int(getattr(rect, "top", 0) or 0)
    right = int(getattr(rect, "right", 0) or 0)
    bottom = int(getattr(rect, "bottom", 0) or 0)
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": max(0, right - left),
        "height": max(0, bottom - top),
    }

def walk(control, controls, depth=0, max_depth=8, max_items=220):
    if depth > max_depth or len(controls) >= max_items:
        return
    try:
        item = {
            "depth": depth,
            "name": str(getattr(control, "Name", "") or "")[:120],
            "control_type": str(getattr(control, "ControlTypeName", "") or ""),
            "automation_id": str(getattr(control, "AutomationId", "") or ""),
            "rect": rect_payload(control),
        }
    except Exception:
        item = {"depth": depth, "name": "", "control_type": "", "automation_id": "", "rect": {}}
    if item["name"] or item["automation_id"] or item["control_type"]:
        controls.append(item)
    try:
        children = control.GetChildren()
    except Exception:
        children = []
    for child in children:
        walk(child, controls, depth + 1, max_depth, max_items)

try:
    import uiautomation as auto
    try:
        auto.SetGlobalSearchTimeout(0.25)
    except Exception:
        pass
    hwnd = int(sys.argv[1])
    root = auto.ControlFromHandle(hwnd)
    controls = []
    walk(root, controls)
    print(json.dumps({
        "status": "available",
        "root_name": getattr(root, "Name", None),
        "root_type": getattr(root, "ControlTypeName", None),
        "root_rect": rect_payload(root),
        "texts": [item["name"] for item in controls if item.get("name")][:120],
        "controls": controls[:160],
    }, ensure_ascii=False, default=str))
except Exception as exc:
    print(json.dumps({"status": "failed", "reason": str(exc)}, ensure_ascii=False, default=str))
"""
        try:
            completed = subprocess.run(
                [sys.executable, "-c", script, str(hwnd)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode != 0:
                reason = (completed.stderr or completed.stdout or "uia_snapshot_failed").strip()
                return {"status": "failed", "reason": reason[:300]}
            payload = json.loads(completed.stdout or "{}")
            if payload.get("status") != "available":
                return payload
            controls = payload.get("controls") or []
            return {
                "status": "available",
                "root_name": payload.get("root_name"),
                "root_type": payload.get("root_type"),
                "root_rect": payload.get("root_rect") or {},
                "texts": (payload.get("texts") or [])[:120],
                "controls": controls[:160],
                "coordinate_anchors": self._coordinate_anchors_from_uia_controls(controls),
            }
        except subprocess.TimeoutExpired:
            return {"status": "failed", "reason": "uia_snapshot_timeout"}
        except Exception as exc:
            return {"status": "failed", "reason": str(exc)}

    def _walk_uia_controls(
        self,
        control: Any,
        controls: list[dict[str, Any]],
        depth: int,
        max_depth: int,
        max_items: int,
    ) -> None:
        if depth > max_depth or len(controls) >= max_items:
            return
        try:
            name = str(getattr(control, "Name", "") or "")
            control_type = str(getattr(control, "ControlTypeName", "") or "")
            automation_id = str(getattr(control, "AutomationId", "") or "")
            rect = self._uia_rect(control)
        except Exception:
            name = ""
            control_type = ""
            automation_id = ""
            rect = {}
        if name or automation_id or control_type:
            controls.append(
                {
                    "depth": depth,
                    "name": name[:120],
                    "control_type": control_type,
                    "automation_id": automation_id,
                    "rect": rect,
                }
            )
        try:
            children = control.GetChildren()
        except Exception:
            children = []
        for child in children:
            self._walk_uia_controls(
                child,
                controls=controls,
                depth=depth + 1,
                max_depth=max_depth,
                max_items=max_items,
            )

    def _uia_rect(self, control: Any) -> dict[str, int]:
        rect = getattr(control, "BoundingRectangle", None)
        if rect is None:
            return {}
        left = int(getattr(rect, "left", 0) or 0)
        top = int(getattr(rect, "top", 0) or 0)
        right = int(getattr(rect, "right", 0) or 0)
        bottom = int(getattr(rect, "bottom", 0) or 0)
        width = max(0, right - left)
        height = max(0, bottom - top)
        return {"left": left, "top": top, "right": right, "bottom": bottom, "width": width, "height": height}

    def _coordinate_anchors_from_uia_controls(self, controls: list[dict[str, Any]]) -> dict[str, Any]:
        anchors: dict[str, dict[str, Any]] = {}
        controls_with_rect = [item for item in controls if self._valid_rect(item.get("rect") or {})]

        def named_control(name: str, control_type: str | None = None) -> dict[str, Any] | None:
            for item in controls_with_rect:
                if name not in str(item.get("name") or ""):
                    continue
                if control_type and item.get("control_type") != control_type:
                    continue
                return item
            return None

        def named_control_any(names: tuple[str, ...], control_type: str | None = None) -> dict[str, Any] | None:
            for name in names:
                found = named_control(name, control_type)
                if found:
                    return found
            return None

        def edit_by_id(automation_id: str) -> dict[str, Any] | None:
            for item in controls_with_rect:
                if item.get("control_type") == "EditControl" and str(item.get("automation_id")) == automation_id:
                    return item
            return None

        buy_tab = named_control("买入[F1]", "TreeItemControl")
        sell_tab = named_control("卖出[F2]", "TreeItemControl")
        cancel_tab = named_control("撤单[F3]", "TreeItemControl")
        buy_tab = named_control_any(("买入[F1]",), "TreeItemControl") or buy_tab
        sell_tab = named_control_any(("卖出[F2]",), "TreeItemControl") or sell_tab
        cancel_tab = named_control_any(("撤单[F3]",), "TreeItemControl") or cancel_tab
        symbol_input = edit_by_id("1032")
        price_input = edit_by_id("1033")
        quantity_input = edit_by_id("1034")
        submit_buy = None
        for item in controls_with_rect:
            if (
                item.get("control_type") == "ButtonControl"
                and str(item.get("automation_id")) == "1006"
                and str(item.get("name")) == "买入"
            ):
                submit_buy = item
                break
        if not submit_buy:
            for item in controls_with_rect:
                if (
                    item.get("control_type") == "ButtonControl"
                    and str(item.get("automation_id")) == "1006"
                    and str(item.get("name")) == "买入"
                ):
                    submit_buy = item
                    break

        buy_anchors: dict[str, Any] = {}
        self._put_anchor(buy_anchors, "buy_tab", buy_tab)
        self._put_anchor(buy_anchors, "symbol_input", symbol_input)
        self._put_anchor(buy_anchors, "price_input", price_input)
        self._put_anchor(buy_anchors, "quantity_input", quantity_input)
        self._put_anchor(buy_anchors, "submit_button", submit_buy)
        if buy_anchors:
            anchors["buy"] = buy_anchors

        sell_anchors: dict[str, Any] = {}
        self._put_anchor(sell_anchors, "sell_tab", sell_tab)
        if symbol_input:
            self._put_anchor(sell_anchors, "symbol_input", symbol_input)
        if price_input:
            self._put_anchor(sell_anchors, "price_input", price_input)
        if quantity_input:
            self._put_anchor(sell_anchors, "quantity_input", quantity_input)
        if sell_anchors:
            anchors["sell"] = sell_anchors

        cancel_anchors: dict[str, Any] = {}
        self._put_anchor(cancel_anchors, "cancel_tab", cancel_tab)
        if cancel_anchors:
            anchors["cancel"] = cancel_anchors

        return anchors

    def _put_anchor(self, anchors: dict[str, Any], name: str, control: dict[str, Any] | None) -> None:
        if not control:
            return
        rect = control.get("rect") or {}
        if not self._valid_rect(rect):
            return
        anchors[name] = {
            **self._center(rect),
            "rect": rect,
            "control_name": control.get("name"),
            "control_type": control.get("control_type"),
            "automation_id": control.get("automation_id"),
            "source": "uiautomation",
        }

    def _valid_rect(self, rect: dict[str, Any]) -> bool:
        return int(rect.get("width") or 0) > 2 and int(rect.get("height") or 0) > 2

    def _center(self, rect: dict[str, Any]) -> dict[str, int]:
        return {
            "x": int((int(rect.get("left") or 0) + int(rect.get("right") or 0)) / 2),
            "y": int((int(rect.get("top") or 0) + int(rect.get("bottom") or 0)) / 2),
        }

    def _window_text(self, hwnd: int) -> str:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    def _child_texts(self, hwnd: int, limit: int) -> list[str]:
        user32 = ctypes.windll.user32
        texts: list[str] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def child_proc(child_hwnd: int, _lparam: int) -> bool:
            if len(texts) >= limit:
                return False
            text = self._window_text(child_hwnd).strip()
            if text:
                texts.append(text[:120])
            return True

        user32.EnumChildWindows(hwnd, child_proc, 0)
        return texts

    def _window_rect(self, hwnd: int) -> dict[str, int]:
        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
            "width": int(rect.right - rect.left),
            "height": int(rect.bottom - rect.top),
        }

    def _process_path(self, pid: int) -> str | None:
        if not pid:
            return None
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value
            return None
        finally:
            kernel32.CloseHandle(handle)

    def _required_controls(self, action: str) -> list[str]:
        if action == "buy":
            return ["buy_tab", "symbol_input", "price_input", "quantity_input", "submit_button"]
        if action == "sell":
            return ["sell_tab", "symbol_input", "price_input", "quantity_input", "submit_button"]
        if action == "cancel":
            return ["cancel_tab", "order_id_input", "submit_button"]
        return []

    def _anchored_steps(
        self,
        action: str,
        anchors: dict[str, Any],
        symbol: str | None,
        price: float | None,
        quantity: int | None,
        order_id: str | None,
    ) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        if action in {"buy", "sell"}:
            tab = "buy_tab" if action == "buy" else "sell_tab"
            steps.append(self._click_step(tab, anchors[tab]))
            steps.append(self._input_step("symbol_input", anchors["symbol_input"], self._ui_symbol(symbol)))
            steps.append(self._input_step("price_input", anchors["price_input"], price))
            steps.append(self._input_step("quantity_input", anchors["quantity_input"], quantity))
            steps.append(self._click_step("submit_button", anchors["submit_button"]))
        elif action == "cancel":
            steps.append(self._click_step("cancel_tab", anchors["cancel_tab"]))
            steps.append(self._input_step("order_id_input", anchors["order_id_input"], order_id or ""))
            steps.append(self._click_step("submit_button", anchors["submit_button"]))
        return steps

    def _estimated_steps(
        self,
        action: str,
        window: dict[str, Any] | None,
        symbol: str | None,
        price: float | None,
        quantity: int | None,
        order_id: str | None,
    ) -> list[dict[str, Any]]:
        rect = (window or {}).get("rect") or {}
        left = int(rect.get("left") or 0)
        top = int(rect.get("top") or 0)
        width = int(rect.get("width") or 0)
        if width <= 0:
            return []
        x = left + max(70, min(220, width // 7))
        y0 = top + 120
        if action in {"buy", "sell"}:
            return [
                {"name": f"{action}_tab", "kind": "click", "x": x, "y": y0, "source": "estimated"},
                {
                    "name": "symbol_input",
                    "kind": "input",
                    "x": x + 80,
                    "y": y0 + 70,
                    "value": self._ui_symbol(symbol),
                    "source": "estimated",
                },
                {"name": "price_input", "kind": "input", "x": x + 80, "y": y0 + 110, "value": price, "source": "estimated"},
                {"name": "quantity_input", "kind": "input", "x": x + 80, "y": y0 + 150, "value": quantity, "source": "estimated"},
                {"name": "submit_button", "kind": "click", "x": x + 80, "y": y0 + 210, "source": "estimated"},
            ]
        if action == "cancel":
            return [
                {"name": "cancel_tab", "kind": "click", "x": x, "y": y0 + 260, "source": "estimated"},
                {"name": "order_id_input", "kind": "input", "x": x + 80, "y": y0 + 320, "value": order_id or "", "source": "estimated"},
                {"name": "submit_button", "kind": "click", "x": x + 80, "y": y0 + 380, "source": "estimated"},
            ]
        return []

    def _click_step(self, name: str, point: Any) -> dict[str, Any]:
        x, y = self._xy(point)
        return {**self._anchor_metadata(point), "name": name, "kind": "click", "x": x, "y": y, "source": "anchor"}

    def _input_step(self, name: str, point: Any, value: Any) -> dict[str, Any]:
        x, y = self._xy(point)
        return {
            **self._anchor_metadata(point),
            "name": name,
            "kind": "input",
            "x": x,
            "y": y,
            "value": value,
            "source": "anchor",
        }

    def _anchor_metadata(self, point: Any) -> dict[str, Any]:
        if not isinstance(point, dict):
            return {}
        return {
            key: point[key]
            for key in ("automation_id", "control_name", "control_type", "rect")
            if key in point
        }

    def _ui_symbol(self, symbol: str | None) -> str:
        if not symbol:
            return ""
        text = str(symbol).strip().upper()
        match = re.match(r"^(SH|SZ|BJ)(\d{6})$", text)
        if match:
            return match.group(2)
        return text

    def _xy(self, point: Any) -> tuple[int, int]:
        if isinstance(point, dict):
            return int(point.get("x")), int(point.get("y"))
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            return int(point[0]), int(point[1])
        raise ValueError("coordinate anchor must be {x,y} or [x,y]")

    def _click(self, x: int, y: int) -> None:
        user32 = ctypes.windll.user32
        user32.SetCursorPos(x, y)
        time.sleep(0.03)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.03)
        user32.mouse_event(0x0004, 0, 0, 0, 0)

    def _send_ctrl_a(self) -> None:
        user32 = ctypes.windll.user32
        user32.keybd_event(0x11, 0, 0, 0)
        user32.keybd_event(0x41, 0, 0, 0)
        user32.keybd_event(0x41, 0, 0x0002, 0)
        user32.keybd_event(0x11, 0, 0x0002, 0)
        time.sleep(0.03)

    def _send_text(self, text: str) -> None:
        user32 = ctypes.windll.user32
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        KEYEVENTF_UNICODE = 0x0004

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

        for char in text:
            if self._send_virtual_key(char):
                time.sleep(0.01)
                continue
            scan = ord(char)
            down = INPUT(
                type=INPUT_KEYBOARD,
                union=INPUT_UNION(ki=KEYBDINPUT(0, scan, KEYEVENTF_UNICODE, 0, None)),
            )
            up = INPUT(
                type=INPUT_KEYBOARD,
                union=INPUT_UNION(ki=KEYBDINPUT(0, scan, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)),
            )
            user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(down))
            user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(up))
            time.sleep(0.01)

    def _send_virtual_key(self, char: str) -> bool:
        if len(char) != 1 or ord(char) > 127:
            return False
        user32 = ctypes.windll.user32
        vk_scan = user32.VkKeyScanW(ord(char))
        if vk_scan == -1:
            return False
        vk = vk_scan & 0xFF
        shift_state = (vk_scan >> 8) & 0xFF
        if shift_state & 1:
            user32.keybd_event(0x10, 0, 0, 0)
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 0x0002, 0)
        if shift_state & 1:
            user32.keybd_event(0x10, 0, 0x0002, 0)
        return True

    def _format_input_value(self, value: Any) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value or "")

    def _set_uia_value(self, hwnd: int, automation_id: str, value: str) -> bool:
        auto = _load_uiautomation()
        if auto is None:
            return False
        try:
            root = auto.ControlFromHandle(hwnd)
            control = self._find_uia_control(root, automation_id=automation_id)
            if control is None:
                return False
            try:
                control.SetFocus()
            except Exception:
                pass
            pattern = control.GetValuePattern()
            pattern.SetValue(value)
            return True
        except Exception:
            return False

    def _find_uia_control(self, control: Any, automation_id: str, depth: int = 0, max_depth: int = 9) -> Any | None:
        if depth > max_depth:
            return None
        try:
            if str(getattr(control, "AutomationId", "") or "") == automation_id:
                return control
            children = control.GetChildren()
        except Exception:
            return None
        for child in children:
            found = self._find_uia_control(child, automation_id=automation_id, depth=depth + 1, max_depth=max_depth)
            if found is not None:
                return found
        return None
