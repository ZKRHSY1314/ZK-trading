from __future__ import annotations

import pytest

from app.disclosures import (
    SUPPORTED_DISCLOSURE_FACT_TYPES,
    DisclosureConflictError,
    DisclosureFact,
    DisclosureLedger,
)
from app.storage.sqlite_store import SQLiteStore


def _ledger(tmp_path) -> DisclosureLedger:
    store = SQLiteStore(tmp_path / "disclosures.sqlite3")
    store.init()
    return DisclosureLedger(store)


def _fact(**overrides) -> DisclosureFact:
    values = {
        "fact_id": "sse-600000-2026-q2-forecast",
        "symbol": "SH600000",
        "fact_type": "earnings_forecast",
        "period_end": "2026-06-30",
        "published_at": "2026-07-10T18:00:00+08:00",
        "first_seen_at": "2026-07-10T18:01:00+08:00",
        "retrieved_at": "2026-07-10T18:02:00+08:00",
        "available_at": "2026-07-10T18:02:00+08:00",
        "source_tier": "exchange",
        "source_url": "https://www.sse.com.cn/disclosure/fixture",
        "raw_hash": "a" * 64,
        "revision": 1,
        "metrics": {"profit_change_pct_low": 20.0, "profit_change_pct_high": 30.0},
        "evidence": [{"field": "profit_change_pct", "text": "fixture evidence"}],
    }
    values.update(overrides)
    return DisclosureFact(**values)


def test_recorded_fact_is_returned_through_point_in_time_interface(tmp_path):
    ledger = _ledger(tmp_path)

    recorded = ledger.record(_fact())

    assert ledger.as_of("2026-07-10T18:01:59+08:00", symbol="SH600000") == []
    assert ledger.as_of("2026-07-10T18:02:00+08:00", symbol="SH600000") == [recorded]
    assert recorded.metrics["profit_change_pct_high"] == 30.0


def test_repeated_payload_is_idempotent_but_a_revision_identity_cannot_be_rewritten(tmp_path):
    ledger = _ledger(tmp_path)
    fact = _fact()

    first = ledger.record(fact)
    repeated = ledger.record(fact)

    assert repeated == first
    assert ledger.as_of("2026-07-11T00:00:00+08:00") == [first]
    with pytest.raises(DisclosureConflictError, match="immutable revision"):
        ledger.record(_fact(raw_hash="b" * 64, metrics={"profit_change_pct_low": -10.0}))


def test_existing_raw_hash_cannot_hide_changed_extracted_facts(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record(_fact())

    with pytest.raises(DisclosureConflictError, match="raw_hash"):
        ledger.record(
            _fact(
                revision=2,
                metrics={"profit_change_pct_low": -10.0},
            )
        )


def test_changed_fact_must_use_the_next_revision_number(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record(_fact())

    with pytest.raises(DisclosureConflictError, match="next revision is 2"):
        ledger.record(
            _fact(
                revision=3,
                raw_hash="c" * 64,
                metrics={"profit_change_pct_low": 5.0},
            )
        )


def test_as_of_uses_only_the_latest_revision_visible_at_that_time(tmp_path):
    ledger = _ledger(tmp_path)
    first = ledger.record(_fact())
    revised = ledger.record(
        _fact(
            revision=2,
            published_at="2026-07-10T20:00:00+08:00",
            first_seen_at="2026-07-10T20:01:00+08:00",
            retrieved_at="2026-07-10T20:02:00+08:00",
            available_at="2026-07-10T20:02:00+08:00",
            raw_hash="d" * 64,
            metrics={"profit_change_pct_low": 10.0, "profit_change_pct_high": 15.0},
        )
    )

    assert ledger.as_of("2026-07-10T19:00:00+08:00") == [first]
    assert ledger.as_of("2026-07-10T20:01:59+08:00") == [first]
    assert ledger.as_of("2026-07-10T20:02:00+08:00") == [revised]


def test_revision_cannot_change_the_fact_identity(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record(_fact())

    with pytest.raises(DisclosureConflictError, match="fact identity"):
        ledger.record(
            _fact(
                symbol="SZ000001",
                revision=2,
                raw_hash="f" * 64,
            )
        )


def test_revision_available_at_cannot_move_backwards(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record(_fact())

    with pytest.raises(DisclosureConflictError, match="available_at cannot move backwards"):
        ledger.record(
            _fact(
                revision=2,
                published_at="2026-07-10T17:00:00+08:00",
                first_seen_at="2026-07-10T17:01:00+08:00",
                retrieved_at="2026-07-10T17:02:00+08:00",
                available_at="2026-07-10T17:02:00+08:00",
                raw_hash="1" * 64,
            )
        )


def test_feature_summary_is_factual_review_only_and_cutoff_safe(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record(_fact())
    ledger.record(
        _fact(
            fact_id="sse-600000-2026-q2-balance",
            fact_type="balance_sheet",
            raw_hash="e" * 64,
            metrics={"total_assets": 1000.0, "debt_ratio": 0.4, "audited": True},
        )
    )

    summary = ledger.feature_summary(
        "2026-07-10T18:02:00+08:00",
        symbol="sh600000",
    )

    assert summary["schema_version"] == "disclosure_feature_summary.v1"
    assert summary["review_only"] is True
    assert summary["symbol"] == "SH600000"
    assert summary["fact_count"] == 2
    assert summary["fact_type_counts"] == {"balance_sheet": 1, "earnings_forecast": 1}
    assert summary["numeric_metrics"]["total_assets"] == {
        "count": 1,
        "latest": 1000.0,
        "min": 1000.0,
        "max": 1000.0,
        "mean": 1000.0,
    }
    assert "audited" not in summary["numeric_metrics"]
    assert set(summary).isdisjoint({"decision", "recommendation", "buy", "sell"})


def test_fact_rejects_non_structured_metrics_and_evidence():
    with pytest.raises(ValueError, match="metrics must be an object"):
        _fact(metrics=[])
    with pytest.raises(ValueError, match="evidence must be a list of objects"):
        _fact(evidence=["unstructured"])


def test_supported_fact_types_cover_financial_statements_and_corporate_events():
    assert SUPPORTED_DISCLOSURE_FACT_TYPES == {
        "balance_sheet",
        "income_statement",
        "cash_flow_statement",
        "earnings_forecast",
        "share_buyback",
        "shareholder_reduction",
        "share_unlock",
        "private_placement",
        "major_contract",
    }


def test_point_in_time_market_and_sector_tables_are_migrated_with_required_indexes(tmp_path):
    store = SQLiteStore(tmp_path / "point-in-time-schema.sqlite3")
    store.init()

    with store.connect() as conn:
        global_columns = {
            row["name"]: row["type"] for row in conn.execute("PRAGMA table_info(global_market_bars)")
        }
        global_indexes = {
            row["name"] for row in conn.execute("PRAGMA index_list(global_market_bars)")
        }
        sector_columns = {
            row["name"]: row["type"]
            for row in conn.execute("PRAGMA table_info(sector_membership_history)")
        }
        sector_indexes = {
            row["name"] for row in conn.execute("PRAGMA index_list(sector_membership_history)")
        }

    assert global_columns == {
        "symbol": "TEXT",
        "asset_class": "TEXT",
        "bar_time": "TEXT",
        "open": "REAL",
        "high": "REAL",
        "low": "REAL",
        "close": "REAL",
        "volume": "REAL",
        "source": "TEXT",
        "available_at": "TEXT",
        "quality_status": "TEXT",
    }
    assert {
        "idx_global_market_bars_symbol_time",
        "idx_global_market_bars_available",
    } <= global_indexes
    assert sector_columns == {
        "id": "INTEGER",
        "symbol": "TEXT",
        "sector": "TEXT",
        "effective_from": "TEXT",
        "effective_to": "TEXT",
        "source": "TEXT",
        "available_at": "TEXT",
        "confidence": "REAL",
    }
    assert {
        "idx_sector_membership_symbol_effective",
        "idx_sector_membership_sector_available",
    } <= sector_indexes
