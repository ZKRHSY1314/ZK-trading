import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

from app.config import settings
from app.data.akshare_provider import AkshareProvider, MarketDataProvider
from app.data.symbols import normalize_a_share_code, with_exchange_prefix
from app.storage.sqlite_store import SQLiteStore


class PhaseReplayError(RuntimeError):
    pass


@dataclass(frozen=True)
class CoreReplayTarget:
    symbol: str
    name: str
    role: str


CORE_REPLAY_TARGETS = [
    CoreReplayTarget("SZ002081", "金螳螂", "拉升出货完成样本"),
    CoreReplayTarget("SZ002115", "三维通信", "方法验证成功样本"),
]


class MainForcePhaseReplayService:
    def __init__(self, provider: MarketDataProvider | None = None) -> None:
        self.provider = provider or AkshareProvider()
        self.store = SQLiteStore(settings.database_path)
        self.store.init()

    def create_replay(
        self,
        symbol: str,
        name: str | None = None,
        lookback_years: float = 3,
        persist: bool = True,
    ) -> dict[str, Any]:
        code = normalize_a_share_code(symbol)
        prefixed = with_exchange_prefix(code)
        hist, data_source = self._load_daily_bars(code)
        bars = self._prepare_bars(hist, lookback_years)
        if len(bars) < 80:
            raise PhaseReplayError(f"{prefixed} 历史数据不足，无法生成阶段回放")

        features = self._feature_frame(bars)
        labeled = self._label_phases(features, prefixed)
        segments = self._segments(labeled)
        summary = self._summary(prefixed, name, labeled, segments)
        replay = {
            "symbol": prefixed,
            "name": name,
            "lookback_years": lookback_years,
            "data_source": data_source,
            "bars_count": len(labeled),
            "latest_phase": summary["latest_phase"],
            "summary": summary,
            "segments": segments,
            "features": self._feature_snapshot(labeled),
        }
        if persist:
            replay["id"] = self._persist_replay(replay)
        return replay

    def create_core_sample_replays(self, lookback_years: float = 3) -> dict[str, Any]:
        results = []
        errors = []
        for target in CORE_REPLAY_TARGETS:
            try:
                replay = self.create_replay(
                    symbol=target.symbol,
                    name=target.name,
                    lookback_years=lookback_years,
                )
                replay["sample_role"] = target.role
                results.append(replay)
            except Exception as exc:
                errors.append(
                    {
                        "symbol": target.symbol,
                        "name": target.name,
                        "sample_role": target.role,
                        "error": str(exc),
                    }
                )
        return {
            "status": "completed" if not errors else "partial",
            "created_count": len(results),
            "error_count": len(errors),
            "results": results,
            "errors": errors,
            "note": "阶段回放只用于训练、复盘和模式识别，不生成实盘交易指令。",
        }

    def latest_replays(
        self,
        symbol: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(with_exchange_prefix(normalize_a_share_code(symbol)))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 100)))
        rows = self.store.fetch_all(
            f"""
            SELECT id, symbol, name, lookback_years, data_source, bars_count,
                   latest_phase, summary_json, segments_json, features_json, created_at
            FROM main_force_phase_replays
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._replay_model(row) for row in rows]

    def get_replay(self, replay_id: int) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT id, symbol, name, lookback_years, data_source, bars_count,
                   latest_phase, summary_json, segments_json, features_json, created_at
            FROM main_force_phase_replays
            WHERE id = ?
            """,
            (replay_id,),
        )
        return self._replay_model(row) if row else None

    def _load_daily_bars(self, code: str) -> tuple[pd.DataFrame, str]:
        try:
            hist = self.provider.get_daily_bars(code)
            if not hist.empty:
                return hist, "akshare.stock_zh_a_hist"
        except Exception as exc:
            akshare_error = str(exc)
        else:
            akshare_error = "AKShare 历史日线为空"

        try:
            fallback = self._load_sina_daily_bars(code)
        except Exception as exc:
            raise PhaseReplayError(
                f"AKShare 历史日线获取失败: {akshare_error}; Sina 兜底也失败: {exc}"
            ) from exc
        if fallback.empty:
            raise PhaseReplayError(
                f"AKShare 历史日线获取失败: {akshare_error}; Sina 兜底为空"
            )
        return fallback, "sina.cn.kline_daily_fallback"

    def _load_sina_daily_bars(self, code: str) -> pd.DataFrame:
        prefix = "sh" if code.startswith("6") else "sz"
        url = (
            "https://quotes.sina.cn/cn/api/jsonp.php/var%20_phaseReplay=/"
            "CN_MarketDataService.getKLineData?"
            f"symbol={prefix}{code}&scale=240&ma=no&datalen=1200"
        )
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
        match = re.search(r"var\s+_phaseReplay=\((.*)\);?", body, re.S)
        if not match:
            raise PhaseReplayError("Sina JSONP 响应无法解析")
        rows = json.loads(match.group(1))
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        result = pd.DataFrame(
            {
                "日期": frame["day"],
                "开盘": pd.to_numeric(frame["open"], errors="coerce"),
                "收盘": pd.to_numeric(frame["close"], errors="coerce"),
                "最高": pd.to_numeric(frame["high"], errors="coerce"),
                "最低": pd.to_numeric(frame["low"], errors="coerce"),
                "成交量": pd.to_numeric(frame["volume"], errors="coerce"),
                "成交额": None,
            }
        )
        result["涨跌幅"] = result["收盘"].pct_change() * 100
        return result

    def _prepare_bars(self, hist: pd.DataFrame, lookback_years: float) -> pd.DataFrame:
        columns = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "pct_change",
        }
        missing = [source for source in columns if source not in hist.columns]
        if missing:
            raise PhaseReplayError(f"历史日线缺少字段: {', '.join(missing)}")

        bars = hist.rename(columns=columns)[list(columns.values())].copy()
        bars["date"] = pd.to_datetime(bars["date"]).dt.date
        for column in ["open", "close", "high", "low", "volume", "amount", "pct_change"]:
            bars[column] = pd.to_numeric(bars[column], errors="coerce")
        bars = bars.dropna(subset=["date", "close", "high", "low", "volume"])
        start_date = date.today() - timedelta(days=int(lookback_years * 365))
        bars = bars[bars["date"] >= start_date].sort_values("date").reset_index(drop=True)
        return bars

    def _feature_frame(self, bars: pd.DataFrame) -> pd.DataFrame:
        frame = bars.copy()
        frame["prev_close"] = frame["close"].shift(1)
        frame["ma20"] = frame["close"].rolling(20, min_periods=5).mean()
        frame["ma60"] = frame["close"].rolling(60, min_periods=20).mean()
        frame["ma120"] = frame["close"].rolling(120, min_periods=40).mean()
        frame["volume_ma20"] = frame["volume"].rolling(20, min_periods=5).mean()
        frame["high_120"] = frame["high"].rolling(120, min_periods=20).max()
        frame["low_120"] = frame["low"].rolling(120, min_periods=20).min()
        frame["return_20"] = frame["close"].pct_change(20)
        frame["return_60"] = frame["close"].pct_change(60)
        frame["return_120"] = frame["close"].pct_change(120)
        frame["range_pct"] = (frame["high"] - frame["low"]) / frame["prev_close"]
        frame["volume_ratio"] = frame["volume"] / frame["volume_ma20"]
        spread_base = frame["ma60"].replace(0, pd.NA)
        frame["ma_spread"] = (frame["ma20"] - frame["ma60"]).abs() / spread_base
        price_range = (frame["high_120"] - frame["low_120"]).replace(0, pd.NA)
        frame["position_120"] = (frame["close"] - frame["low_120"]) / price_range
        frame["drawdown_from_120_high"] = frame["close"] / frame["high_120"] - 1
        return frame

    def _label_phases(self, frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
        labels = []
        distribution_seen = False
        for _, row in frame.iterrows():
            label, evidence = self._classify_row(row, distribution_seen)
            if label == "distribution":
                distribution_seen = True
            if symbol == "SZ002081" and distribution_seen and label in {"observe", "accumulation"}:
                label = "post_distribution_watch"
                evidence.append("用户确认金螳螂已完成拉升出货，后续优先作为出货后观察样本。")
            labels.append((label, evidence))
        frame = frame.copy()
        frame["phase"] = [item[0] for item in labels]
        frame["evidence"] = [item[1] for item in labels]
        return frame

    def _classify_row(self, row: pd.Series, distribution_seen: bool) -> tuple[str, list[str]]:
        volume_ratio = self._num(row.get("volume_ratio"))
        position = self._num(row.get("position_120"))
        ret20 = self._num(row.get("return_20"))
        ret60 = self._num(row.get("return_60"))
        ret120 = self._num(row.get("return_120"))
        ma_spread = self._num(row.get("ma_spread"))
        drawdown = self._num(row.get("drawdown_from_120_high"))
        range_pct = self._num(row.get("range_pct"))
        close = self._num(row.get("close"))
        high = self._num(row.get("high"))

        evidence: list[str] = []
        if distribution_seen and drawdown is not None and drawdown < -0.08:
            return "post_distribution_watch", ["已出现出货段后回落，进入出货后观察。"]

        high_rejection = close and high and close < high * 0.97
        if (
            position is not None
            and position > 0.78
            and volume_ratio is not None
            and volume_ratio > 1.45
            and (high_rejection or (ret20 is not None and ret20 < -0.03))
        ):
            evidence.append("高位区域放量且冲高回落/短线转弱，疑似派发。")
            return "distribution", evidence

        if (
            (ret20 is not None and ret20 > 0.18)
            or (ret60 is not None and ret60 > 0.35)
        ) and volume_ratio is not None and volume_ratio > 1.05:
            evidence.append("短中期涨幅扩大且成交量同步放大，进入拉升段。")
            return "markup", evidence

        if (
            volume_ratio is not None
            and volume_ratio > 1.8
            and range_pct is not None
            and range_pct > 0.045
            and (ret20 is None or ret20 < 0.16)
        ):
            evidence.append("放量脉冲但尚未形成持续主升，适合作为试盘观察。")
            return "test_pull", evidence

        if (
            position is not None
            and position < 0.65
            and ma_spread is not None
            and ma_spread < 0.09
            and (ret120 is None or ret120 < 0.25)
        ):
            evidence.append("价格未脱离长期区间且均线收敛，符合吸筹/整理特征。")
            return "accumulation", evidence

        return "observe", ["阶段信号不充分，保留观察。"]

    def _segments(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        segments = []
        current_phase = None
        start_idx = 0
        for idx, phase in enumerate(frame["phase"].tolist()):
            if current_phase is None:
                current_phase = phase
                start_idx = idx
                continue
            if phase != current_phase:
                segments.append(self._segment_model(frame.iloc[start_idx:idx], current_phase))
                current_phase = phase
                start_idx = idx
        segments.append(self._segment_model(frame.iloc[start_idx:], current_phase or "observe"))
        return [segment for segment in segments if segment["bars"] >= 3]

    def _segment_model(self, segment: pd.DataFrame, phase: str) -> dict[str, Any]:
        first = segment.iloc[0]
        last = segment.iloc[-1]
        start_close = self._num(first.get("close")) or 0
        end_close = self._num(last.get("close")) or start_close
        max_volume_ratio = segment["volume_ratio"].dropna().max()
        evidence = []
        for item in segment["evidence"].tolist():
            for note in item:
                if note not in evidence:
                    evidence.append(note)
        return {
            "phase": phase,
            "phase_name": self._phase_name(phase),
            "start_date": str(first["date"]),
            "end_date": str(last["date"]),
            "bars": int(len(segment)),
            "start_close": round(start_close, 3),
            "end_close": round(end_close, 3),
            "return_pct": round((end_close - start_close) / start_close * 100, 3)
            if start_close
            else None,
            "max_close": round(float(segment["close"].max()), 3),
            "max_volume_ratio": round(float(max_volume_ratio), 3)
            if pd.notna(max_volume_ratio)
            else None,
            "evidence": evidence[:4],
        }

    def _summary(
        self,
        symbol: str,
        name: str | None,
        frame: pd.DataFrame,
        segments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        first = frame.iloc[0]
        latest = frame.iloc[-1]
        latest_phase = str(latest["phase"])
        phase_counts = {
            phase: int(count)
            for phase, count in frame["phase"].value_counts().sort_index().items()
        }
        return {
            "symbol": symbol,
            "name": name,
            "start_date": str(first["date"]),
            "end_date": str(latest["date"]),
            "bars_count": int(len(frame)),
            "latest_phase": latest_phase,
            "latest_phase_name": self._phase_name(latest_phase),
            "latest_close": self._round(latest.get("close")),
            "period_return_pct": self._period_return(frame),
            "phase_counts": phase_counts,
            "segment_count": len(segments),
            "phase_path": [segment["phase"] for segment in segments],
            "diagnosis": self._diagnosis(symbol, latest_phase, segments),
            "training_questions": self._training_questions(symbol),
            "safety_note": "阶段回放只用于训练和复盘，不构成买卖建议。",
        }

    def _feature_snapshot(self, frame: pd.DataFrame) -> dict[str, Any]:
        latest = frame.iloc[-1]
        return {
            "latest": {
                "date": str(latest["date"]),
                "close": self._round(latest.get("close")),
                "volume_ratio": self._round(latest.get("volume_ratio")),
                "return_20": self._pct(latest.get("return_20")),
                "return_60": self._pct(latest.get("return_60")),
                "return_120": self._pct(latest.get("return_120")),
                "position_120": self._round(latest.get("position_120")),
                "drawdown_from_120_high": self._pct(latest.get("drawdown_from_120_high")),
            },
            "phase_order": [
                "accumulation",
                "test_pull",
                "markup",
                "distribution",
                "post_distribution_watch",
            ],
        }

    def _persist_replay(self, replay: dict[str, Any]) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO main_force_phase_replays(
                    symbol, name, lookback_years, data_source, bars_count, latest_phase,
                    summary_json, segments_json, features_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    replay["symbol"],
                    replay.get("name"),
                    replay["lookback_years"],
                    replay["data_source"],
                    replay["bars_count"],
                    replay["latest_phase"],
                    json.dumps(replay["summary"], ensure_ascii=False, default=str),
                    json.dumps(replay["segments"], ensure_ascii=False, default=str),
                    json.dumps(replay["features"], ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def _replay_model(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "symbol": row["symbol"],
            "name": row.get("name"),
            "lookback_years": row["lookback_years"],
            "data_source": row["data_source"],
            "bars_count": row["bars_count"],
            "latest_phase": row.get("latest_phase"),
            "summary": json.loads(row["summary_json"] or "{}"),
            "segments": json.loads(row["segments_json"] or "[]"),
            "features": json.loads(row["features_json"] or "{}"),
            "created_at": row.get("created_at"),
        }

    def _diagnosis(
        self,
        symbol: str,
        latest_phase: str,
        segments: list[dict[str, Any]],
    ) -> str:
        if symbol == "SZ002081":
            return "金螳螂作为已完成拉升出货样本，重点学习吸筹、试盘、拉升与高位派发的阶段衔接，短期只复盘不追高。"
        if symbol == "SZ002115":
            return "三维通信作为方法验证成功样本，重点对照拉升前的低位吸筹和启动信号。"
        if latest_phase == "distribution":
            return "最近处于疑似派发段，优先复盘风险释放和成交量结构。"
        if latest_phase == "markup":
            return "最近处于拉升段，适合回看前期吸筹和试盘证据是否充分。"
        if any(segment["phase"] == "test_pull" for segment in segments):
            return "阶段路径中出现试盘片段，可用于训练启动前的试探性放量。"
        return "阶段信号仍偏观察，适合继续积累样本。"

    def _training_questions(self, symbol: str) -> list[str]:
        questions = [
            "哪些片段像长期吸筹，而不是普通横盘？",
            "哪几段放量更像试盘，而不是主升？",
            "真正拉升开始前，价格和成交量发生了什么变化？",
            "高位出货或出货后观察阶段有哪些风险信号？",
        ]
        if symbol == "SZ002081":
            questions.append("为什么金螳螂当前更适合作为出货完成样本，而不是短线追高样本？")
        if symbol == "SZ002115":
            questions.append("三维通信的成功路径中，哪些早期信号最值得迁移到新样本？")
        return questions

    def _phase_name(self, phase: str) -> str:
        return {
            "accumulation": "吸筹/整理",
            "test_pull": "试盘",
            "markup": "拉升",
            "distribution": "派发/出货",
            "post_distribution_watch": "出货后观察",
            "observe": "观察",
        }.get(phase, phase)

    def _period_return(self, frame: pd.DataFrame) -> float | None:
        start = self._num(frame.iloc[0].get("close"))
        end = self._num(frame.iloc[-1].get("close"))
        if not start or end is None:
            return None
        return round((end - start) / start * 100, 3)

    def _pct(self, value: Any) -> float | None:
        number = self._num(value)
        return round(number * 100, 3) if number is not None else None

    def _round(self, value: Any) -> float | None:
        number = self._num(value)
        return round(number, 4) if number is not None else None

    def _num(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
        return float(value)
