import csv
import json
import math
import sqlite3
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


def clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return clean_record(value)
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if hasattr(value, "item"):
        return clean_value(value.item())
    return value


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {str(key).strip(): clean_value(value) for key, value in record.items() if key is not None}


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def maybe_float(value: Any) -> float | None:
    value = clean_value(value)
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace("%", ""))
    except ValueError:
        return None


def register_sources(conn: sqlite3.Connection, legacy_dir: Path) -> int:
    count = 0
    for path in sorted(legacy_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO source_documents(filename, file_type, size_bytes)
            VALUES (?, ?, ?)
            """,
            (path.name, path.suffix.lower().lstrip(".") or "unknown", path.stat().st_size),
        )
        count += 1
    return count


def insert_principle(conn: sqlite3.Connection, item: dict[str, Any], category: str) -> None:
    record = clean_record(item)
    conn.execute(
        """
        INSERT OR REPLACE INTO principles(
            id, name, description, source, category, severity, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.get("id"),
            record.get("原则") or record.get("name"),
            record.get("说明") or "",
            record.get("来源"),
            category,
            "hard",
            dump_json(record),
        ),
    )


def import_principles(conn: sqlite3.Connection, legacy_dir: Path) -> int:
    count = 0
    constitution = read_json(legacy_dir / "trading_constitution.json")
    for item in constitution.get("交易铁律", []):
        insert_principle(conn, item, "交易铁律")
        count += 1

    dengzhan = read_json(legacy_dir / "灯盏策略_完整数据.json")
    for item in dengzhan.get("新增原则", []):
        insert_principle(conn, item, "灯盏策略原则")
        count += 1
    return count


def insert_strategy(conn: sqlite3.Connection, item: dict[str, Any], category: str) -> None:
    record = clean_record(item)
    strategy_id = record.get("id")
    if not strategy_id:
        strategy_id = f"{category}_{record.get('策略') or record.get('策略名') or record.get('指标')}"

    conn.execute(
        """
        INSERT OR REPLACE INTO strategies(
            id, category, name, trigger_condition, operation_standard,
            position_management, indicators, risk_control, notes, source, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            strategy_id,
            category,
            record.get("策略名") or record.get("策略") or record.get("指标") or "",
            record.get("触发条件"),
            record.get("操作标准") or record.get("说明"),
            record.get("仓位管理"),
            record.get("参考指标"),
            record.get("风险控制"),
            record.get("注意事项") or record.get("应用") or record.get("备选条件"),
            record.get("来源"),
            dump_json(record),
        ),
    )


def insert_indicator(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    record = clean_record(item)
    conn.execute(
        """
        INSERT INTO technical_indicators(name, definition, calculation, usage, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            record.get("指标") or record.get("name") or "",
            record.get("定义"),
            record.get("计算方法"),
            record.get("应用"),
            dump_json(record),
        ),
    )


def import_strategies(conn: sqlite3.Connection, legacy_dir: Path) -> tuple[int, int]:
    strategy_count = 0
    indicator_count = 0

    strategy = read_json(legacy_dir / "trading_strategy.json")
    category_map = {
        "买入策略": "buy",
        "卖出策略": "sell",
        "仓位管理": "position",
    }
    for source_category, target_category in category_map.items():
        for item in strategy.get(source_category, []):
            insert_strategy(conn, item, target_category)
            strategy_count += 1
    for item in strategy.get("技术指标", []):
        insert_indicator(conn, item)
        indicator_count += 1

    dengzhan = read_json(legacy_dir / "灯盏策略_完整数据.json")
    for source_category, target_category in {
        "新增买入策略": "buy",
        "新增卖出策略": "sell",
        "选股策略": "selection",
    }.items():
        for item in dengzhan.get(source_category, []):
            insert_strategy(conn, item, target_category)
            strategy_count += 1
    for item in dengzhan.get("技术指标", []):
        insert_indicator(conn, item)
        indicator_count += 1

    return strategy_count, indicator_count


def import_cases(conn: sqlite3.Connection, legacy_dir: Path) -> int:
    data = read_json(legacy_dir / "trading_cases.json")
    count = 0
    for case_type, lesson_key in (("成功案例", "经验"), ("失败案例", "教训")):
        for item in data.get(case_type, []):
            record = clean_record(item)
            conn.execute(
                """
                INSERT OR REPLACE INTO trade_cases(
                    id, case_type, trade_date, stock_text, operation, result, lesson, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("id"),
                    "success" if case_type == "成功案例" else "failure",
                    record.get("日期"),
                    record.get("股票"),
                    record.get("操作"),
                    record.get("结果"),
                    record.get(lesson_key),
                    dump_json(record),
                ),
            )
            count += 1
    return count


def import_trade_records(conn: sqlite3.Connection, legacy_dir: Path) -> int:
    path = legacy_dir / "交易记录明细_Trading_Records.csv"
    count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            record = clean_record(row)
            conn.execute(
                """
                INSERT INTO trade_records(
                    trade_date, stock_code, stock_name, operation_type, reference_price,
                    pct_change_text, turnover_text, float_ratio_text, result, remarks, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("日期"),
                    record.get("股票代码"),
                    record.get("股票名称"),
                    record.get("操作类型"),
                    maybe_float(record.get("参考价格")),
                    record.get("涨幅"),
                    record.get("成交额"),
                    record.get("占流通盘"),
                    record.get("结果"),
                    record.get("备注"),
                    dump_json(record),
                ),
            )
            count += 1
    return count


def insert_stock_profile(
    conn: sqlite3.Connection,
    record: dict[str, Any],
    dataset_name: str,
    source_file: str,
) -> None:
    normalized = clean_record(record)
    symbol = normalized.get("代码") or normalized.get("股票代码") or normalized.get("symbol")
    if not symbol:
        return
    conn.execute(
        """
        INSERT INTO stock_profiles(
            symbol, name, current_price, pct_change, five_day_pct, main_entry_date,
            launch_date, accumulation_years, avg_cost, operation_cost_line, sell_target,
            stop_loss, risk_level, profit_rate, pb, pe_ttm, recent_high, high_profit_rate,
            limit_up_count, test_line_count, score, rating, dataset_name, source_file, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            symbol,
            normalized.get("名称") or normalized.get("股票名称") or normalized.get("name"),
            maybe_float(normalized.get("现价")),
            maybe_float(normalized.get("涨幅")),
            maybe_float(normalized.get("5日涨幅")),
            normalized.get("主力进场日期"),
            normalized.get("启动日期"),
            maybe_float(normalized.get("吸筹年数")),
            maybe_float(normalized.get("成本均价")),
            maybe_float(normalized.get("操作成本线")),
            maybe_float(normalized.get("卖点")),
            maybe_float(normalized.get("止损位")),
            normalized.get("风险大小") or normalized.get("risk_level"),
            maybe_float(normalized.get("盈利率")),
            maybe_float(normalized.get("市净率")),
            maybe_float(normalized.get("TTM市盈率")),
            maybe_float(normalized.get("近期高点")),
            maybe_float(normalized.get("高点盈利率")),
            maybe_float(normalized.get("涨停数量")),
            maybe_float(normalized.get("试盘线数量")),
            maybe_float(normalized.get("积分") or normalized.get("score")),
            normalized.get("评价") or normalized.get("rating"),
            dataset_name,
            source_file,
            dump_json(normalized),
        ),
    )


def import_stock_profiles(conn: sqlite3.Connection, legacy_dir: Path) -> int:
    count = 0

    training_path = legacy_dir / "自选股训练数据集_v1.0.json"
    training = read_json(training_path)
    for dataset_name, dataset in training.items():
        if not isinstance(dataset, dict) or "数据" not in dataset:
            continue
        for record in dataset.get("数据", []):
            before = conn.total_changes
            insert_stock_profile(conn, record, dataset_name, training_path.name)
            if conn.total_changes > before:
                count += 1

    excel_path = legacy_dir / "自选股-操作成本线、卖点.xlsx"
    workbook = pd.read_excel(excel_path, sheet_name=None)
    for sheet_name, frame in workbook.items():
        for record in frame.to_dict(orient="records"):
            before = conn.total_changes
            insert_stock_profile(conn, record, sheet_name, excel_path.name)
            if conn.total_changes > before:
                count += 1

    xls_path = legacy_dir / "自选股.xls"
    try:
        xls_workbook = pd.read_excel(xls_path, sheet_name=None, engine="xlrd")
    except Exception as exc:
        try:
            xls_frame = pd.read_csv(xls_path, sep="\t", encoding="gbk")
        except Exception:
            print(f"跳过 {xls_path.name}: {exc}")
        else:
            for record in xls_frame.to_dict(orient="records"):
                before = conn.total_changes
                insert_stock_profile(conn, record, "自选股文本表", xls_path.name)
                if conn.total_changes > before:
                    count += 1
    else:
        for sheet_name, frame in xls_workbook.items():
            for record in frame.to_dict(orient="records"):
                before = conn.total_changes
                insert_stock_profile(conn, record, sheet_name, xls_path.name)
                if conn.total_changes > before:
                    count += 1

    return count


def import_strategy_documents(conn: sqlite3.Connection, legacy_dir: Path) -> int:
    count = 0
    for filename in ["灯盏策略_完整数据.json", "选股策略与庄股成本计算_v3.0.json"]:
        data = read_json(legacy_dir / filename)
        doc_name = data.get("策略名称") or filename
        for section, content in data.items():
            title = None
            if isinstance(content, dict):
                title = content.get("策略名称") or content.get("策略编号")
            conn.execute(
                """
                INSERT INTO strategy_documents(doc_name, section, title, content_json, source_file)
                VALUES (?, ?, ?, ?, ?)
                """,
                (doc_name, section, title, dump_json(clean_value(content)), filename),
            )
            count += 1
    return count


def import_user_seed(conn: sqlite3.Connection) -> dict[str, int]:
    seed_path = Path("configs/user_knowledge_seed.json")
    if not seed_path.exists():
        return {
            "user_stock_notes": 0,
            "trade_cases": 0,
            "stock_profiles": 0,
            "main_force_phase_patterns": 0,
        }

    seed = read_json(seed_path)
    counts = {
        "user_stock_notes": 0,
        "trade_cases": 0,
        "stock_profiles": 0,
        "main_force_phase_patterns": 0,
    }

    for item in seed.get("user_stock_notes", []):
        record = clean_record(item)
        conn.execute(
            """
            INSERT OR REPLACE INTO user_stock_notes(
                id, symbol, name, note_type, priority, content, tags_json, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("id"),
                record.get("symbol"),
                record.get("name"),
                record.get("note_type"),
                int(record.get("priority") or 50),
                record.get("content") or "",
                dump_json(record.get("tags") or []),
                dump_json(record),
            ),
        )
        counts["user_stock_notes"] += 1

    for item in seed.get("trade_cases", []):
        record = clean_record(item)
        conn.execute(
            """
            INSERT OR REPLACE INTO trade_cases(
                id, case_type, trade_date, stock_text, operation, result, lesson, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("id"),
                record.get("case_type"),
                record.get("trade_date"),
                record.get("stock_text"),
                record.get("operation"),
                record.get("result"),
                record.get("lesson"),
                dump_json(record),
            ),
        )
        counts["trade_cases"] += 1

    for item in seed.get("stock_profiles", []):
        before = conn.total_changes
        insert_stock_profile(conn, item, item.get("dataset_name") or "用户补充", seed_path.name)
        if conn.total_changes > before:
            counts["stock_profiles"] += 1

    for item in seed.get("main_force_phase_patterns", []):
        record = clean_record(item)
        conn.execute(
            """
            INSERT OR REPLACE INTO main_force_phase_patterns(
                id, symbol, name, pattern_type, status, priority, phase_timeline_json,
                theory_tags_json, training_focus_json, caution_notes_json, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("id"),
                record.get("symbol"),
                record.get("name"),
                record.get("pattern_type"),
                record.get("status"),
                int(record.get("priority") or 50),
                dump_json(record.get("phase_timeline") or []),
                dump_json(record.get("theory_tags") or []),
                dump_json(record.get("training_focus") or []),
                dump_json(record.get("caution_notes") or []),
                dump_json(record),
            ),
        )
        counts["main_force_phase_patterns"] += 1

    return counts


def import_all(reset: bool = True) -> dict[str, int]:
    legacy_dir = settings.legacy_data_dir.resolve()
    if not legacy_dir.exists():
        raise FileNotFoundError(f"找不到资料目录: {legacy_dir}")

    store = SQLiteStore(settings.database_path)
    store.init()
    if reset:
        store.reset_knowledge()

    with store.connect() as conn:
        summary = {
            "source_documents": register_sources(conn, legacy_dir),
            "principles": import_principles(conn, legacy_dir),
        }
        strategy_count, indicator_count = import_strategies(conn, legacy_dir)
        summary["strategies"] = strategy_count
        summary["technical_indicators"] = indicator_count
        summary["trade_cases"] = import_cases(conn, legacy_dir)
        summary["trade_records"] = import_trade_records(conn, legacy_dir)
        summary["stock_profiles"] = import_stock_profiles(conn, legacy_dir)
        summary["strategy_documents"] = import_strategy_documents(conn, legacy_dir)
        user_seed_counts = import_user_seed(conn)
        summary["user_stock_notes"] = user_seed_counts["user_stock_notes"]
        summary["trade_cases"] += user_seed_counts["trade_cases"]
        summary["stock_profiles"] += user_seed_counts["stock_profiles"]
        summary["main_force_phase_patterns"] = user_seed_counts["main_force_phase_patterns"]
        conn.execute(
            """
            INSERT INTO import_runs(source_dir, status, summary_json)
            VALUES (?, ?, ?)
            """,
            (str(legacy_dir), "success", dump_json(summary)),
        )

    return store.table_counts()


def main() -> None:
    counts = import_all(reset=True)
    print("导入完成:")
    for table, count in counts.items():
        print(f"- {table}: {count}")


if __name__ == "__main__":
    main()
