from datetime import datetime
import json
from app.storage.sqlite_store import SQLiteStore
from app.config import settings

class AIReviewWorker:
    def __init__(self):
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def generate_review(self) -> dict:
        # 1. Pull recent trades
        with self.store.connect() as conn:
            trades = conn.execute(
                "SELECT * FROM historical_backtest_trades ORDER BY trade_date DESC LIMIT 50"
            ).fetchall()

        # 2. Prepare prompt (in a real system, this goes to the ModelGateway)
        prompt = "Analyze the following trades and propose a rules.yaml patch:\n"
        for t in trades:
            prompt += f"{t['trade_date']} {t['symbol']} {t['side']} @ {t['price']}\n"

        # 3. Simulate AI call (placeholder since API keys are missing)
        proposed_patch = {
            "rules": [
                {
                    "id": "constitution_no_high_position",
                    "weight": 20,
                    "hard_block": False  # Simulated AI mistake
                }
            ],
            "min_market_cap": 3000000000, # Simulated AI mistake (too low)
            "max_position_ratio": 0.5, # Simulated AI mistake (too high)
            "candidate_tiers": {"strong_min_score": 85}
        }

        # 4. Apply safety blocks
        applied_blocks = []
        if proposed_patch.get("min_market_cap", 10000000000) < 5000000000:
            proposed_patch["min_market_cap"] = 5000000000 # hard floor
            applied_blocks.append("min_market_cap increased to safe floor of 5B")

        if proposed_patch.get("max_position_ratio", 0) > 0.2:
            proposed_patch["max_position_ratio"] = 0.2 # Cannot increase beyond 20%
            applied_blocks.append("max_position_ratio capped at safe limit of 20%")

        for rule in proposed_patch.get("rules", []):
            if "hard_block" in rule and not rule["hard_block"]:
                # Hard blocks cannot be disabled by AI
                rule["hard_block"] = True
                applied_blocks.append(f"hard_block enforced for rule {rule['id']}")

        # 5. Record the review proposal
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_parameter_proposals (
                    trades_analyzed, proposed_patch_json, safety_blocks_json, status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    len(trades),
                    json.dumps(proposed_patch, ensure_ascii=False),
                    json.dumps(applied_blocks, ensure_ascii=False),
                    "draft",
                )
            )
            proposal_id = cursor.lastrowid

        return {
            "id": proposal_id,
            "status": "success",
            "trades_analyzed": len(trades),
            "proposed_patch": proposed_patch,
            "safety_blocks_applied": applied_blocks,
            "timestamp": datetime.now().isoformat()
        }

    def list_proposals(self, limit: int = 20) -> list[dict]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM ai_parameter_proposals
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [self._proposal_model(row) for row in rows]

    def validate_proposal(self, proposal_id: int) -> dict:
        proposal = self._get_proposal(proposal_id)
        patch = proposal["proposed_patch"]
        latest_run = self.store.fetch_one(
            """
            SELECT metrics_json
            FROM historical_backtest_runs
            WHERE status = 'completed'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        metrics = json.loads(latest_run["metrics_json"]) if latest_run else {}
        trade_count = int(metrics.get("trade_count") or 0)
        max_drawdown = float(metrics.get("max_drawdown") or 0)
        validation = {
            "status": "validation_failed",
            "checks": {
                "sample_size": trade_count >= 20,
                "drawdown": max_drawdown <= 0.10,
                "hard_blocks_preserved": self._hard_blocks_preserved(patch),
                "live_trading_disabled": settings.enable_live_trading is False,
            },
            "metrics": metrics,
            "validated_at": datetime.now().isoformat(),
            "simulation_only": True,
        }
        if all(validation["checks"].values()):
            validation["status"] = "validation_passed"
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE ai_parameter_proposals
                SET status = ?, validation_json = ?
                WHERE id = ?
                """,
                (
                    validation["status"],
                    json.dumps(validation, ensure_ascii=False),
                    proposal_id,
                ),
            )
        return validation

    def approve_for_simulation(
        self,
        proposal_id: int,
        reviewed_by: str = "user",
        note: str | None = None,
    ) -> dict:
        proposal = self._get_proposal(proposal_id)
        if proposal["status"] != "validation_passed":
            raise ValueError("AI proposal must pass validation before simulation approval.")
        return self._review(proposal_id, "approved_for_simulation", reviewed_by, note)

    def reject(
        self,
        proposal_id: int,
        reviewed_by: str = "user",
        note: str | None = None,
    ) -> dict:
        self._get_proposal(proposal_id)
        return self._review(proposal_id, "rejected", reviewed_by, note)

    def _review(
        self,
        proposal_id: int,
        status: str,
        reviewed_by: str,
        note: str | None,
    ) -> dict:
        reviewed_at = datetime.now().isoformat()
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE ai_parameter_proposals
                SET status = ?, reviewed_by = ?, review_note = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (status, reviewed_by, note, reviewed_at, proposal_id),
            )
        proposal = self._get_proposal(proposal_id)
        proposal["reviewed_at"] = reviewed_at
        return proposal

    def _get_proposal(self, proposal_id: int) -> dict:
        row = self.store.fetch_one(
            "SELECT * FROM ai_parameter_proposals WHERE id = ?",
            (proposal_id,),
        )
        if not row:
            raise ValueError("AI proposal not found.")
        return self._proposal_model(row)

    def _proposal_model(self, row) -> dict:
        item = dict(row)
        item["proposed_patch"] = json.loads(item.pop("proposed_patch_json") or "{}")
        item["safety_blocks"] = json.loads(item.pop("safety_blocks_json") or "[]")
        item["validation"] = json.loads(item.pop("validation_json") or "{}")
        return item

    def _hard_blocks_preserved(self, patch: dict) -> bool:
        return all(rule.get("hard_block", True) for rule in patch.get("rules", []))
