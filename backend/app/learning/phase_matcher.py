import json
import math
from difflib import SequenceMatcher
from typing import Any

from app.config import settings
from app.data.symbols import normalize_a_share_code, with_exchange_prefix
from app.learning.phase_replay import CORE_REPLAY_TARGETS, MainForcePhaseReplayService
from app.storage.sqlite_store import SQLiteStore


PHASE_ORDER = [
    "accumulation",
    "test_pull",
    "markup",
    "distribution",
    "post_distribution_watch",
    "observe",
]


class PhaseSimilarityService:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.replay_service = MainForcePhaseReplayService()

    def create_match(
        self,
        symbol: str,
        name: str | None = None,
        lookback_years: float = 3,
        persist: bool = True,
    ) -> dict[str, Any]:
        target = self.replay_service.create_replay(
            symbol=symbol,
            name=name,
            lookback_years=lookback_years,
        )
        core_replays = self._core_replays(lookback_years)
        matches = [self._compare(target, core) for core in core_replays]
        matches.sort(key=lambda item: item["score"], reverse=True)
        summary = self._summary(target, matches)
        result = {
            "target_symbol": target["symbol"],
            "target_name": target.get("name"),
            "target_replay_id": target.get("id"),
            "summary": summary,
            "matches": matches,
        }
        if persist:
            result["id"] = self._persist_match(result)
        return result

    def latest_matches(
        self,
        symbol: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if symbol:
            where = "WHERE target_symbol = ?"
            params.append(with_exchange_prefix(normalize_a_share_code(symbol)))
        params.append(max(1, min(limit, 100)))
        rows = self.store.fetch_all(
            f"""
            SELECT id, target_symbol, target_name, target_replay_id,
                   summary_json, matches_json, created_at
            FROM main_force_phase_matches
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._match_model(row) for row in rows]

    def get_match(self, match_id: int) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT id, target_symbol, target_name, target_replay_id,
                   summary_json, matches_json, created_at
            FROM main_force_phase_matches
            WHERE id = ?
            """,
            (match_id,),
        )
        return self._match_model(row) if row else None

    def latest_guardrail(self, symbol: str) -> dict[str, Any] | None:
        matches = self.latest_matches(symbol=symbol, limit=1)
        if not matches:
            return None
        match = matches[0]
        summary = match.get("summary", {})
        best = summary.get("best_match") or {}
        score = float(best.get("score") or 0)
        latest_phase = summary.get("target_latest_phase")
        if (
            best.get("core_symbol") == "SZ002081"
            and score >= 70
            and latest_phase in {"distribution", "post_distribution_watch"}
        ):
            return {
                "match_id": match["id"],
                "risk_level": "phase_distribution_guardrail",
                "action": "observe",
                "allowed": False,
                "reason": (
                    f"阶段匹配更接近金螳螂出货完成样本，匹配分 {score:.1f}，"
                    "短期只复盘不追高"
                ),
                "best_match": best,
                "diagnosis": summary.get("diagnosis"),
                "next_actions": summary.get("next_actions", []),
            }
        return None

    def _core_replays(self, lookback_years: float) -> list[dict[str, Any]]:
        replays = []
        for target in CORE_REPLAY_TARGETS:
            latest = self.replay_service.latest_replays(symbol=target.symbol, limit=1)
            replay = latest[0] if latest else self.replay_service.create_replay(
                symbol=target.symbol,
                name=target.name,
                lookback_years=lookback_years,
            )
            replay["sample_role"] = target.role
            replays.append(replay)
        return replays

    def _compare(self, target: dict[str, Any], core: dict[str, Any]) -> dict[str, Any]:
        target_summary = target["summary"]
        core_summary = core["summary"]
        phase_similarity = self._phase_vector_similarity(
            target_summary.get("phase_counts", {}),
            core_summary.get("phase_counts", {}),
        )
        path_similarity = self._path_similarity(
            target_summary.get("phase_path", []),
            core_summary.get("phase_path", []),
        )
        latest_similarity = self._latest_phase_similarity(
            target_summary.get("latest_phase"),
            core_summary.get("latest_phase"),
        )
        return_similarity = self._return_similarity(
            target_summary.get("period_return_pct"),
            core_summary.get("period_return_pct"),
        )
        score = (
            0.38 * phase_similarity
            + 0.30 * path_similarity
            + 0.18 * latest_similarity
            + 0.14 * return_similarity
        )
        inference = self._inference(core, score, target_summary)
        return {
            "core_symbol": core["symbol"],
            "core_name": core.get("name"),
            "sample_role": core.get("sample_role"),
            "score": round(score * 100, 2),
            "phase_similarity": round(phase_similarity * 100, 2),
            "path_similarity": round(path_similarity * 100, 2),
            "latest_phase_similarity": round(latest_similarity * 100, 2),
            "return_similarity": round(return_similarity * 100, 2),
            "core_latest_phase": core_summary.get("latest_phase"),
            "target_latest_phase": target_summary.get("latest_phase"),
            "inference": inference,
            "core_diagnosis": core_summary.get("diagnosis"),
        }

    def _summary(self, target: dict[str, Any], matches: list[dict[str, Any]]) -> dict[str, Any]:
        best = matches[0] if matches else None
        latest_phase = target["summary"].get("latest_phase")
        if not best:
            diagnosis = "暂无可用核心样本，无法生成阶段相似度判断。"
        elif best["core_symbol"] == "SZ002081" and best["score"] >= 55:
            diagnosis = "目标股阶段结构更接近金螳螂路径，优先检查是否存在拉升后派发或出货后观察风险。"
        elif best["core_symbol"] == "SZ002115" and best["score"] >= 55:
            diagnosis = "目标股阶段结构更接近三维通信路径，优先复盘低位吸筹和启动前试盘证据。"
        else:
            diagnosis = "目标股与核心样本相似度中等或偏低，暂不迁移结论，继续积累阶段证据。"

        actions = [
            "仅把阶段相似度作为复盘和训练信号，不生成实盘交易指令。",
            "把相似度最高样本的吸筹、试盘、拉升、出货证据逐段对照目标股。",
        ]
        if latest_phase in {"distribution", "post_distribution_watch"}:
            actions.append("目标股最新阶段偏出货/出货后观察，模拟系统应保持保守。")
        elif latest_phase == "markup":
            actions.append("目标股最新阶段偏拉升，回看启动前是否具备充分吸筹和试盘证据。")
        else:
            actions.append("目标股最新阶段仍偏观察，优先等待更多量价证据。")

        return {
            "target_symbol": target["symbol"],
            "target_name": target.get("name"),
            "target_latest_phase": latest_phase,
            "target_latest_phase_name": target["summary"].get("latest_phase_name"),
            "target_period_return_pct": target["summary"].get("period_return_pct"),
            "best_match": best,
            "diagnosis": diagnosis,
            "next_actions": actions,
            "safety_note": "阶段匹配只用于训练、复盘和模式迁移，不构成买卖建议。",
        }

    def _phase_vector_similarity(
        self,
        left_counts: dict[str, int],
        right_counts: dict[str, int],
    ) -> float:
        left = [float(left_counts.get(phase, 0)) for phase in PHASE_ORDER]
        right = [float(right_counts.get(phase, 0)) for phase in PHASE_ORDER]
        left_norm = math.sqrt(sum(item * item for item in left))
        right_norm = math.sqrt(sum(item * item for item in right))
        if not left_norm or not right_norm:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)

    def _path_similarity(self, left_path: list[str], right_path: list[str]) -> float:
        if not left_path or not right_path:
            return 0.0
        return SequenceMatcher(a=left_path, b=right_path).ratio()

    def _latest_phase_similarity(self, left: str | None, right: str | None) -> float:
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0
        distribution_like = {"distribution", "post_distribution_watch"}
        if left in distribution_like and right in distribution_like:
            return 0.7
        trend_like = {"test_pull", "markup"}
        if left in trend_like and right in trend_like:
            return 0.55
        return 0.0

    def _return_similarity(self, left: float | None, right: float | None) -> float:
        if left is None or right is None:
            return 0.0
        return max(0.0, 1 - min(abs(float(left) - float(right)) / 220, 1))

    def _inference(
        self,
        core: dict[str, Any],
        score: float,
        target_summary: dict[str, Any],
    ) -> str:
        confidence = "高" if score >= 0.7 else ("中" if score >= 0.55 else "低")
        latest = target_summary.get("latest_phase")
        if core["symbol"] == "SZ002081":
            return f"{confidence}相似于金螳螂出货完成样本；若目标股最新阶段为 {latest}，优先复核追高和派发风险。"
        if core["symbol"] == "SZ002115":
            return f"{confidence}相似于三维通信成功样本；若目标股最新阶段为 {latest}，优先复核启动前吸筹和试盘证据。"
        return f"{confidence}相似于 {core['symbol']}；需要人工复盘确认。"

    def _persist_match(self, result: dict[str, Any]) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO main_force_phase_matches(
                    target_symbol, target_name, target_replay_id, summary_json, matches_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    result["target_symbol"],
                    result.get("target_name"),
                    result.get("target_replay_id"),
                    json.dumps(result["summary"], ensure_ascii=False, default=str),
                    json.dumps(result["matches"], ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def _match_model(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "target_symbol": row["target_symbol"],
            "target_name": row.get("target_name"),
            "target_replay_id": row.get("target_replay_id"),
            "summary": json.loads(row["summary_json"] or "{}"),
            "matches": json.loads(row["matches_json"] or "[]"),
            "created_at": row.get("created_at"),
        }
