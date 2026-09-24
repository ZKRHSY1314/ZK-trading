from __future__ import annotations

import json
import sqlite3
import subprocess
from collections import Counter

import pandas as pd
import pytest

from app.config import settings
from scripts import compare_market_sources as comparison


def _unexpected(*_args, **_kwargs):
    raise AssertionError("This operation must not run in this test")


def _create_cache(path, aliases):
    """Create only an explicitly scoped synthetic database, never the app store."""
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE daily_bar_cache (symbol TEXT, trade_date TEXT, "
            "open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL, "
            "source TEXT, adjustment_mode TEXT, volume_unit TEXT, "
            "quality_status TEXT, updated_at TEXT, PRIMARY KEY(symbol, trade_date))"
        )
        for alias, price in aliases.items():
            for date in pd.date_range("2026-01-01", periods=140):
                connection.execute(
                    "INSERT INTO daily_bar_cache VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        alias, date.date().isoformat(), price, price + 1, price - 1,
                        price, 100, price * 10_000, "akshare.stock_zh_a_daily",
                        "qfq", "hand", "ready", "2026-09-03T16:00:00+08:00",
                    ),
                )


@pytest.mark.parametrize(
    ("aliases", "selected", "price"),
    [
        ({"600519": 10, "600519.SH": 20, "SH600519": 30}, "600519", 10),
        ({"600519.SH": 20, "SH600519": 30}, "600519.SH", 20),
        ({"SH600519": 30}, "SH600519", 30),
    ],
)
def test_cache_selects_one_alias_without_mixing_duplicate_dates(
    tmp_path, monkeypatch, aliases, selected, price
):
    database = tmp_path / "synthetic.sqlite3"
    _create_cache(database, aliases)
    before = database.read_bytes()
    monkeypatch.setattr(settings, "database_path", database)

    frame = comparison.cached_sample("600519.SH", 120)

    assert len(frame) == 120
    assert frame["date"].nunique() == 120
    assert not frame["date"].duplicated().any()
    assert set(frame["close"]) == {price}
    assert frame.attrs["selected_cache_symbol"] == selected
    assert frame.attrs["source"] == "akshare.stock_zh_a_daily"
    assert database.read_bytes() == before


def test_cache_missing_database_does_not_create_or_connect(tmp_path, monkeypatch):
    database = tmp_path / "not-created.sqlite3"
    monkeypatch.setattr(settings, "database_path", database)
    monkeypatch.setattr(comparison.sqlite3, "connect", _unexpected)

    assert comparison.cached_sample("600519.SH", 120).empty
    assert not database.exists()
    assert list(tmp_path.iterdir()) == []


def test_cache_query_is_sqlite_read_only_and_never_attempts_data_writes(
    tmp_path, monkeypatch
):
    database = tmp_path / "synthetic.sqlite3"
    _create_cache(database, {"600519": 10})
    before = database.read_bytes()
    paths_before = set(tmp_path.iterdir())
    monkeypatch.setattr(settings, "database_path", database)
    original_connect = sqlite3.connect
    connections, statements, denied = [], [], []
    read_actions = {
        sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_TRANSACTION,
    }

    def authorizer(action, arg1, arg2, _database_name, _trigger):
        if action in read_actions:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and arg1 == "query_only":
            return sqlite3.SQLITE_OK
        denied.append((action, arg1, arg2))
        return sqlite3.SQLITE_DENY

    def connect(database_uri, **kwargs):
        assert "?mode=ro" in str(database_uri)
        assert kwargs.get("uri") is True
        connection = original_connect(database_uri, **kwargs)
        connection.set_authorizer(authorizer)
        connection.set_trace_callback(statements.append)
        connections.append(connection)
        return connection

    monkeypatch.setattr(comparison.sqlite3, "connect", connect)
    try:
        frame = comparison.cached_sample("600519.SH", 5)
        assert len(frame) == 5
        assert any("query_only" in statement.lower() for statement in statements)
        assert denied == []
        assert all(
            statement.lstrip().upper().startswith(("SELECT", "PRAGMA"))
            for statement in statements
        )
    finally:
        for connection in connections:
            connection.close()

    assert database.read_bytes() == before
    assert set(tmp_path.iterdir()) == paths_before


def test_cache_without_matching_symbol_returns_empty(tmp_path, monkeypatch):
    database = tmp_path / "synthetic.sqlite3"
    _create_cache(database, {"000001": 10})
    monkeypatch.setattr(settings, "database_path", database)

    assert comparison.cached_sample("600519.SH", 120).empty


def test_cache_does_not_select_an_alias_with_only_an_error_marker(tmp_path, monkeypatch):
    database = tmp_path / "synthetic.sqlite3"
    _create_cache(database, {"SH600519": 30})
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO daily_bar_cache (symbol, trade_date, source) VALUES (?, ?, ?)",
            ("600519", "ERROR", "akshare.stock_zh_a_daily"),
        )
    monkeypatch.setattr(settings, "database_path", database)

    frame = comparison.cached_sample("600519.SH", 120)

    assert len(frame) == 120
    assert frame.attrs["selected_cache_symbol"] == "SH600519"
    assert set(frame["close"]) == {30}


def test_main_default_only_describes_plan_without_probe_or_database_access(
    monkeypatch, capsys
):
    monkeypatch.setattr(comparison.sys, "argv", ["compare_market_sources.py"])
    monkeypatch.setattr(comparison, "probe", _unexpected)
    monkeypatch.setattr(comparison, "run_probe", _unexpected)
    monkeypatch.setattr(comparison, "cached_sample", _unexpected)
    monkeypatch.setattr(comparison.subprocess, "run", _unexpected)

    assert comparison.main() == 0

    plan = json.loads(capsys.readouterr().out)
    assert plan["writes_market_database"] is False
    assert plan["requested_bars"] == 120
    assert plan["rounds"] == 2


def test_worker_timeout_is_censored_not_zero_and_does_not_expose_output(monkeypatch):
    ticks = iter([10.0, 50.25])
    monkeypatch.setattr(comparison.time, "perf_counter", lambda: next(ticks))
    invoked = []

    def timeout(command, **kwargs):
        invoked.append((command, kwargs))
        raise subprocess.TimeoutExpired(
            command, kwargs["timeout"], output="secret-stdout", stderr="secret-stderr"
        )

    monkeypatch.setattr(comparison.subprocess, "run", timeout)
    result = comparison.run_probe("tonghuasun", "600519.SH", 120, "synthetic-home", 40)

    assert result["status"] == "timeout"
    assert result["seconds"] is None
    assert result["deadline_seconds"] == 40
    assert result["process_wall_seconds"] == pytest.approx(40.25)
    assert "secret" not in json.dumps(result)
    command, kwargs = invoked[0]
    assert command[command.index("--probe") + 1] == "tonghuasun"
    assert kwargs.get("shell", False) is False
    assert kwargs["timeout"] == 40


@pytest.mark.parametrize(
    ("target_kind", "already_exists"),
    [("existing", True), ("outside_root", True), ("outside_root", False),
     ("database", True), ("database", False)],
)
def test_output_target_is_rejected_before_probe_and_existing_content_is_preserved(
    tmp_path, monkeypatch, target_kind, already_exists
):
    backend = tmp_path / "backend"
    backend.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    target = {
        "existing": output / "existing.json",
        "outside_root": tmp_path / "outside.json",
        "database": output / "market.sqlite3",
    }[target_kind]
    if already_exists:
        target.write_bytes(b"preserve-this-file")
    monkeypatch.setattr(comparison, "BACKEND", backend)
    monkeypatch.setattr(comparison, "run_probe", _unexpected)
    monkeypatch.setattr(comparison, "cached_sample", _unexpected)
    monkeypatch.setattr(
        comparison.sys, "argv",
        ["compare_market_sources.py", "--run", "--product-home", "synthetic-home",
         "--output", str(target)],
    )

    with pytest.raises(SystemExit) as error:
        comparison.main()

    assert error.value.code == 2
    if already_exists:
        assert target.read_bytes() == b"preserve-this-file"
    else:
        assert not target.exists()


def _successful_probe(source, seconds=2.0):
    frame = pd.DataFrame([
        {"date": "2026-09-01", "open": 10.0, "high": 11.0, "low": 9.0,
         "close": 10.5, "volume": 100.0, "amount": 1050.0}
    ])
    return {
        "status": "success", "seconds": seconds, "attempts": [],
        "attributes": {"source": source, "adjustment_mode": "qfq"},
        "frame": json.loads(frame.to_json(orient="split")),
    }


def _configure_mocked_run(tmp_path, monkeypatch, *, rounds=1):
    backend = tmp_path / "backend"
    backend.mkdir()
    output = tmp_path / "output" / "result.json"
    monkeypatch.setattr(comparison, "BACKEND", backend)
    monkeypatch.setattr(comparison, "cached_sample", lambda *_args: pd.DataFrame())
    monkeypatch.setattr(
        comparison.sys, "argv",
        ["compare_market_sources.py", "--run", "--symbols", "600519.SH",
         "--rounds", str(rounds), "--product-home", "synthetic-home",
         "--output", str(output)],
    )
    return output


def test_latency_summary_keeps_timeouts_out_of_successful_median(tmp_path, monkeypatch):
    output = _configure_mocked_run(tmp_path, monkeypatch, rounds=2)
    counts = Counter()

    def probe(source, *_args):
        counts[source] += 1
        if source == "tonghuasun" and counts[source] == 1:
            return _successful_probe(source, seconds=2.0)
        return {"status": "timeout", "seconds": None, "deadline_seconds": 40,
                "process_wall_seconds": 40.1}

    monkeypatch.setattr(comparison, "run_probe", probe)

    assert comparison.main() == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    summaries = {row["source"]: row for row in report["latency_summary"]}
    assert summaries["tonghuasun"]["attempted"] == 2
    assert summaries["tonghuasun"]["successes"] == 1
    assert summaries["tonghuasun"]["median_seconds"] == 2.0
    assert summaries["legacy_chain"]["attempted"] == 2
    assert summaries["legacy_chain"]["successes"] == 0
    assert summaries["legacy_chain"]["median_seconds"] is None
    assert all(row["seconds"] is None for row in report["runs"] if row["status"] == "timeout")


def test_comparison_source_labels_survive_nested_profiles(tmp_path, monkeypatch):
    output = _configure_mocked_run(tmp_path, monkeypatch)
    monkeypatch.setattr(comparison, "run_probe", lambda source, *_args: _successful_probe(source))

    assert comparison.main() == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(report["comparisons"]) == 2
    assert {row["right_source"] for row in report["comparisons"]} == {
        "legacy_chain", "sina_reference",
    }
    for row in report["comparisons"]:
        assert row["left_source"] == "tonghuasun"
        assert isinstance(row["left"], dict)
        assert isinstance(row["right"], dict)
        assert row["left"]["source"] == row["left_source"]
        assert row["right"]["source"] == row["right_source"]
