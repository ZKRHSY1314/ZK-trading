from __future__ import annotations

from app.storage.sqlite_store import SQLiteStore


def test_each_runtime_connection_enforces_foreign_keys(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "foreign-keys.sqlite3")
    store.init()

    with store.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_each_runtime_connection_waits_for_startup_write_contention(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "busy-timeout.sqlite3")
    store.init()

    with store.connect() as connection:
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] >= 30_000


def test_reset_knowledge_deletes_children_before_parent_rows(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "reset-order.sqlite3")
    store.init()
    with store.connect() as connection:
        cursor = connection.execute(
            "INSERT INTO potential_search_runs(status, source) VALUES ('completed', 'pytest')"
        )
        connection.execute(
            """
            INSERT INTO potential_search_items(run_id, symbol, source)
            VALUES (?, 'SH600000', 'pytest')
            """,
            (cursor.lastrowid,),
        )

    store.reset_knowledge()

    assert store.fetch_one("SELECT COUNT(*) AS count FROM potential_search_runs") == {
        "count": 0
    }
    assert store.fetch_one("SELECT COUNT(*) AS count FROM potential_search_items") == {
        "count": 0
    }


def test_daily_bar_metadata_migration_does_not_rewrite_unclassifiable_rows(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "migration.sqlite3")
    store.init()

    with store.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE daily_bar_update_audit(row_id INTEGER NOT NULL);
            CREATE TRIGGER audit_daily_bar_update
            AFTER UPDATE ON daily_bar_cache
            BEGIN
                INSERT INTO daily_bar_update_audit(row_id) VALUES (NEW.id);
            END;
            """
        )
        conn.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status
            ) VALUES (?, '2026-07-14', 10, 11, 9, 10.5, 100, NULL, ?, 'unknown', 'unknown', 'ready')
            """,
            [
                ("SH000001", "akshare.stock_zh_index_daily"),
                ("SH600001", "sina.cn.kline_daily_fallback"),
            ],
        )

    store.init()

    with store.connect() as conn:
        rows = conn.execute(
            """
            SELECT symbol, adjustment_mode, volume_unit, quality_status
            FROM daily_bar_cache
            ORDER BY symbol
            """
        ).fetchall()
        first_pass_updates = conn.execute(
            "SELECT COUNT(*) FROM daily_bar_update_audit"
        ).fetchone()[0]
        conn.execute("DELETE FROM daily_bar_update_audit")

    assert [tuple(row) for row in rows] == [
        ("SH000001", "none", "unknown", "ready"),
        ("SH600001", "unknown", "share", "review_only_unknown_adjustment"),
    ]
    assert first_pass_updates == 3

    store.init()

    with store.connect() as conn:
        second_pass_updates = conn.execute(
            "SELECT COUNT(*) FROM daily_bar_update_audit"
        ).fetchone()[0]

    assert second_pass_updates == 0
