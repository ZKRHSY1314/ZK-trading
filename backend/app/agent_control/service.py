import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

from app.candidates.auto_discovery import AutoDiscoveryScanner
from app.candidates.offhour_search import OffhourPotentialSearchService
from app.config import settings
from app.models import AgentControlEvent, AgentControlTask, AgentTaskInput
from app.monitoring.service import MonitoringService
from app.automation.supervisor import AutomationSupervisor
from app.research.offhour import OffhourResearchLoopService
from app.storage.sqlite_store import SQLiteStore


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class AgentControlService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.safe_tasks = {
            "offhour_potential_search",
            "potential_search",
            "auto_discovery_scan",
            "monitoring_run",
            "full_simulation_cycle",
            "frontend_browser_check",
            "offhour_research_loop",
        }
        self.observation_tasks = {
            "local_dashboard_observation"
        }
        self.blocked_tasks = {
            "live_trading",
            "broker_login",
            "credential_storage",
            "filesystem_write"
        }
        self.blocked_keywords = {
            "live",
            "broker",
            "credential",
            "password",
            "order",
            "buy",
            "sell",
            "trade",
            "filesystem",
            "delete",
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "safe_tasks": sorted(self.safe_tasks),
            "observation_tasks": sorted(self.observation_tasks),
            "blocked_tasks": sorted(self.blocked_tasks),
            "blocked_keywords": sorted(self.blocked_keywords),
            "live_trading_enabled": settings.enable_live_trading,
            "broker_control_blocked": True,
        }

    def create_task(self, input_data: AgentTaskInput) -> AgentControlTask:
        task_type = input_data.task_type.strip().lower()
        status = "pending"
        approval_status = "auto_approved"
        error = None
        if task_type in self.blocked_tasks or any(keyword in task_type for keyword in self.blocked_keywords):
            status = "blocked"
            approval_status = "blocked"
            error = f"Task type '{task_type}' is blocked for safety reasons."
        elif task_type in self.observation_tasks:
            approval_status = "pending"
        elif task_type not in self.safe_tasks:
            status = "blocked"
            approval_status = "blocked"
            error = f"Task type '{task_type}' is not recognized as a safe task."

        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agent_control_tasks (
                    task_type, status, requested_by, payload_json, error, approval_status, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? = 'blocked' THEN CURRENT_TIMESTAMP ELSE NULL END)
                """,
                (
                    task_type,
                    status,
                    input_data.requested_by,
                    json.dumps(input_data.payload, ensure_ascii=False),
                    error,
                    approval_status,
                    status,
                )
            )
            task_id = cursor.lastrowid
            
        task = self.get_task(task_id)
        if not task:
            raise RuntimeError("Failed to create task")
        
        self.record_event(task_id, "created", f"Task created with approval_status {approval_status}")
        return self.get_task(task_id) or task

    def get_task(self, task_id: int) -> AgentControlTask | None:
        row = self.store.fetch_one(
            "SELECT * FROM agent_control_tasks WHERE id = ?", (task_id,)
        )
        if not row:
            return None
        
        events_rows = self.store.fetch_all(
            "SELECT * FROM agent_control_events WHERE task_id = ? ORDER BY id", (task_id,)
        )
        events = [
            AgentControlEvent(
                id=e["id"],
                task_id=e["task_id"],
                event_type=e["event_type"],
                message=e["message"],
                metadata=json.loads(e["metadata_json"] or "{}"),
                created_at=e["created_at"]
            )
            for e in events_rows
        ]
        
        return AgentControlTask(
            id=row["id"],
            task_type=row["task_type"],
            status=row["status"],
            requested_by=row["requested_by"],
            payload=json.loads(row["payload_json"] or "{}"),
            result=json.loads(row["result_json"] or "{}"),
            error=row["error"],
            approval_status=row["approval_status"],
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            rejected_by=row["rejected_by"],
            rejected_at=row["rejected_at"],
            approval_note=row["approval_note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            events=events
        )

    def list_tasks(self, limit: int = 50) -> list[AgentControlTask]:
        rows = self.store.fetch_all(
            "SELECT * FROM agent_control_tasks ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        )
        tasks = []
        for row in rows:
            tasks.append(
                AgentControlTask(
                    id=row["id"],
                    task_type=row["task_type"],
                    status=row["status"],
                    requested_by=row["requested_by"],
                    payload=json.loads(row["payload_json"] or "{}"),
                    result=json.loads(row["result_json"] or "{}"),
                    error=row["error"],
                    approval_status=row["approval_status"],
                    approved_by=row["approved_by"],
                    approved_at=row["approved_at"],
                    rejected_by=row["rejected_by"],
                    rejected_at=row["rejected_at"],
                    approval_note=row["approval_note"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    completed_at=row["completed_at"],
                    events=[]
                )
            )
        return tasks

    def record_event(self, task_id: int, event_type: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_control_events (task_id, event_type, message, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, event_type, message, meta_json)
            )

    def _update_task(self, task_id: int, status: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        query = "UPDATE agent_control_tasks SET status = ?, updated_at = CURRENT_TIMESTAMP"
        params: list[Any] = [status]
        
        if result is not None:
            query += ", result_json = ?"
            params.append(json.dumps(result, ensure_ascii=False))
            
        if error is not None:
            query += ", error = ?"
            params.append(error)
            
        if status in ("completed", "failed", "blocked"):
            query += ", completed_at = CURRENT_TIMESTAMP"
            
        query += " WHERE id = ?"
        params.append(task_id)
        
        with self.store.connect() as conn:
            conn.execute(query, tuple(params))

    def approve_task(self, task_id: int, user: str, note: str | None = None) -> AgentControlTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("Task not found")
        if task.status == "blocked":
            raise ValueError("Cannot approve a blocked task")
        if task.approval_status != "pending":
            raise ValueError(f"Task approval_status is {task.approval_status}, expected pending")
            
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE agent_control_tasks 
                SET approval_status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP, approval_note = ?
                WHERE id = ?
                """,
                (user, note, task_id)
            )
        self.record_event(task_id, "approved", f"Task approved by {user}", {"note": note})
        return self.get_task(task_id)  # type: ignore
        
    def reject_task(self, task_id: int, user: str, note: str | None = None) -> AgentControlTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("Task not found")
        if task.approval_status != "pending":
            raise ValueError(f"Task approval_status is {task.approval_status}, expected pending")
            
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE agent_control_tasks 
                SET approval_status = 'rejected',
                    status = 'rejected',
                    rejected_by = ?,
                    rejected_at = CURRENT_TIMESTAMP,
                    approval_note = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user, note, task_id)
            )
        self.record_event(task_id, "rejected", f"Task rejected by {user}", {"note": note})
        return self.get_task(task_id)  # type: ignore

    def list_audit_events(self, limit: int = 50) -> list[AgentControlEvent]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM agent_control_events
            WHERE event_type IN ('approved', 'rejected')
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        )
        return [
            AgentControlEvent(
                id=e["id"],
                task_id=e["task_id"],
                event_type=e["event_type"],
                message=e["message"],
                metadata=json.loads(e["metadata_json"] or "{}"),
                created_at=e["created_at"]
            )
            for e in rows
        ]

    def execute_task(self, task_id: int) -> AgentControlTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("Task not found")
            
        if task.status in ("completed", "failed", "blocked", "rejected"):
            return task

        if task.approval_status == "pending":
            raise ValueError("Task requires approval before execution")

        if settings.enable_live_trading:
            error = "Agent control queue refuses to run while live trading is enabled."
            self._update_task(task_id, "blocked", error=error)
            self.record_event(task_id, "blocked", error)
            return self.get_task(task_id) or task
            
        self._update_task(task_id, "running")
        self.record_event(task_id, "started", "Task execution started")
        
        result = {}
        error = None
        status = "completed"
        
        try:
            if task.task_type in ("offhour_potential_search", "potential_search"):
                limit = task.payload.get("limit", 100)
                result = OffhourPotentialSearchService().run(limit=limit, persist=True)
            elif task.task_type == "auto_discovery_scan":
                limit = task.payload.get("limit", 50)
                result = AutoDiscoveryScanner().scan(limit=limit, persist=True)
            elif task.task_type == "monitoring_run":
                limit = task.payload.get("limit", 5)
                result = MonitoringService().run_once(limit=limit)
            elif task.task_type == "full_simulation_cycle":
                limit = task.payload.get("limit", 5)
                monitor_limit = task.payload.get("monitor_limit", 5)
                review_symbol = task.payload.get("review_symbol", "SZ002081")
                result = AutomationSupervisor().run_cycle(limit=limit, monitor_limit=monitor_limit, review_symbol=review_symbol)
            elif task.task_type == "offhour_research_loop":
                result = OffhourResearchLoopService().run(
                    limit=task.payload.get("limit", 100),
                    strategy_limit=task.payload.get("strategy_limit", 50),
                    history_days=task.payload.get("history_days", 240),
                    write_artifact=task.payload.get("write_artifact", True),
                    refresh_history=task.payload.get("refresh_history", False),
                    requested_by=task.requested_by,
                )
            elif task.task_type == "frontend_browser_check":
                completed = subprocess.run(
                    ["npm.cmd", "run", "automation:browser"],
                    cwd=FRONTEND_DIR,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if completed.returncode != 0:
                    raise RuntimeError(completed.stderr or completed.stdout)
                result = {
                    "stdout": completed.stdout,
                    "stderr": completed.stderr
                }
            elif task.task_type == "local_dashboard_observation":
                try:
                    dashboard_url = task.payload.get("url") or "http://127.0.0.1:3000"
                    if not str(dashboard_url).startswith("http://127.0.0.1:"):
                        raise ValueError("local_dashboard_observation only allows 127.0.0.1 URLs")
                    req = urllib.request.Request(str(dashboard_url))
                    with urllib.request.urlopen(req, timeout=5) as response:
                        html = response.read().decode("utf-8")
                        status_code = response.status
                        content_type = response.headers.get("content-type")
                    health = self._fetch_local_json("http://127.0.0.1:8000/health")
                    result = {
                        "status": "success",
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                        "url": str(dashboard_url),
                        "dashboard_reachable": True,
                        "status_code": status_code,
                        "content_type": content_type,
                        "html_bytes": len(html.encode("utf-8")),
                        "app_root_present": 'id="app"' in html,
                        "backend_health": health,
                        "html_preview": html[:500]
                    }
                except urllib.error.URLError as e:
                    result = {
                        "status": "partial",
                        "dashboard_reachable": False,
                        "reason": str(e)
                    }
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
                
        except Exception as exc:
            status = "failed"
            error = str(exc)
            
        self._update_task(task_id, status, result=result, error=error)
        self.record_event(task_id, "finished", f"Task finished with status {status}", {"error": error})
        
        return self.get_task(task_id) or task

    def _fetch_local_json(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload)
