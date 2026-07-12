from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.config import settings
from app.reference_data import ReferenceIngestService
from app.storage.sqlite_store import SQLiteStore
from scripts.ingest_reference_data import main


class _Provider:
    def __init__(self) -> None:
        self.buyback_amount = 1_000_000.0
        self.announcement_date = "2026-07-11"
        self.latest_price = 10.0
        self.sequence = 1
        self.industry_members = ["600000", "430047"]
        self.concept_members = ["000001", "300750"]

    def get_industry_boards(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "\u677f\u5757\u540d\u79f0": "\u534a\u5bfc\u4f53\u884c\u4e1a",
                    "\u677f\u5757\u4ee3\u7801": "BK1001",
                },
                {
                    "\u677f\u5757\u540d\u79f0": "\u7164\u70ad\u884c\u4e1a",
                    "\u677f\u5757\u4ee3\u7801": "BK1002",
                },
            ]
        )

    def get_industry_members(self, symbol: str) -> pd.DataFrame:
        assert symbol == "BK1001"
        return pd.DataFrame({"\u4ee3\u7801": self.industry_members})

    def get_concept_boards(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"\u677f\u5757\u540d\u79f0": "AI\u7b97\u529b", "\u677f\u5757\u4ee3\u7801": "BK2001"}]
        )

    def get_concept_members(self, symbol: str) -> pd.DataFrame:
        assert symbol == "BK2001"
        return pd.DataFrame({"\u4ee3\u7801": self.concept_members})

    def get_sina_industry_boards(self) -> pd.DataFrame:
        return pd.DataFrame(columns=["label", "\u677f\u5757"])

    def get_sina_industry_members(self, symbol: str) -> pd.DataFrame:
        raise AssertionError(symbol)

    def get_share_buybacks(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "序号": self.sequence,
                    "\u80a1\u7968\u4ee3\u7801": "600000",
                    "\u80a1\u7968\u7b80\u79f0": "fixture",
                    "最新价": self.latest_price,
                    "\u56de\u8d2d\u8d77\u59cb\u65f6\u95f4": "2026-06-01",
                    "\u6700\u65b0\u516c\u544a\u65e5\u671f": self.announcement_date,
                    "\u8ba1\u5212\u56de\u8d2d\u91d1\u989d\u533a\u95f4-\u4e0b\u9650": 500_000.0,
                    "\u8ba1\u5212\u56de\u8d2d\u91d1\u989d\u533a\u95f4-\u4e0a\u9650": 2_000_000.0,
                    "\u5df2\u56de\u8d2d\u91d1\u989d": self.buyback_amount,
                    "\u5b9e\u65bd\u8fdb\u5ea6": "\u5b9e\u65bd\u4e2d",
                }
            ]
        )


def _clock(hour: int = 4) -> datetime:
    return datetime(2026, 7, 12, hour, tzinfo=timezone.utc)


def _service(tmp_path, provider: object | None = None, *, hour: int = 4):
    store = SQLiteStore(tmp_path / "reference.sqlite3")
    service = ReferenceIngestService(
        store=store,
        provider=provider or _Provider(),
        clock=lambda: _clock(hour),
        sleep_fn=lambda _: None,
    )
    return store, service


def test_dry_run_fetches_and_reports_real_source_shapes_without_record_writes(tmp_path) -> None:
    store, service = _service(tmp_path)

    result = service.run(rate_limit_seconds=0, include_global=False)

    assert result["status"] == "planned"
    assert result["mode"] == "dry_run"
    assert result["safety"] == {
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
        "writes_enabled": False,
        "broker_operations_enabled": False,
    }
    assert result["sectors"]["external_board_count"] == 3
    assert result["sectors"]["mapped_board_count"] == 2
    assert result["sectors"]["unmapped_board_count"] == 1
    assert result["sectors"]["member_board_coverage_pct"] == 100.0
    assert result["sectors"]["member_rows"] == 4
    assert result["sectors"]["valid_member_rows"] == 3
    assert result["sectors"]["unique_member_symbols"] == 3
    assert result["sectors"]["membership_records_planned"] == 3
    assert result["sectors"]["membership_records_written"] == 0
    assert result["disclosures"]["facts_planned"] == 1
    assert result["disclosures"]["facts_written"] == 0
    assert result["disclosures"]["freshness"] == {
        "latest_published_date": "2026-07-11",
        "age_days": 1,
        "status": "fresh",
    }
    assert store.fetch_one("SELECT COUNT(*) AS count FROM sector_membership_history")["count"] == 0
    assert store.fetch_one("SELECT COUNT(*) AS count FROM sector_membership_snapshots")["count"] == 0
    assert store.fetch_one(
        "SELECT COUNT(*) AS count FROM sector_membership_snapshot_members"
    )["count"] == 0
    assert store.fetch_one("SELECT COUNT(*) AS count FROM disclosure_facts")["count"] == 0


def test_apply_records_point_in_time_memberships_and_disclosure_idempotently(tmp_path) -> None:
    provider = _Provider()
    store, service = _service(tmp_path, provider)

    first = service.run(apply=True, rate_limit_seconds=0, include_global=False)
    repeated = ReferenceIngestService(
        store=store,
        provider=provider,
        clock=lambda: datetime(2026, 7, 13, 4, tzinfo=timezone.utc),
        sleep_fn=lambda _: None,
    ).run(apply=True, rate_limit_seconds=0, include_global=False)

    assert first["status"] == "completed"
    assert first["sectors"]["membership_records_written"] == 3
    assert first["sectors"]["membership_snapshots_written"] == 2
    assert first["disclosures"]["facts_written"] == 1
    assert repeated["sectors"]["membership_records_written"] == 0
    assert repeated["sectors"]["membership_records_existing"] == 3
    assert repeated["sectors"]["membership_snapshots_written"] == 0
    assert repeated["sectors"]["membership_snapshots_unchanged"] == 2
    assert store.fetch_one("SELECT COUNT(*) AS count FROM sector_membership_snapshots") == {
        "count": 2
    }
    assert repeated["disclosures"]["facts_written"] == 0
    assert repeated["disclosures"]["facts_unchanged"] == 1
    memberships = store.fetch_all(
        """
        SELECT member.symbol, snapshot.sector, snapshot.source,
               snapshot.effective_date, snapshot.observed_at, snapshot.confidence
        FROM sector_membership_snapshots AS snapshot
        JOIN sector_membership_snapshot_members AS member
          ON member.snapshot_id = snapshot.id
        ORDER BY member.symbol, snapshot.sector
        """
    )
    assert [(item["symbol"], item["sector"]) for item in memberships] == [
        ("SH600000", "semiconductors"),
        ("SZ000001", "ai_compute"),
        ("SZ300750", "ai_compute"),
    ]
    assert all(item["effective_date"] == "2026-07-12" for item in memberships)
    assert all(item["observed_at"] == "2026-07-12T04:00:00+00:00" for item in memberships)
    assert store.fetch_one("SELECT COUNT(*) AS count FROM sector_membership_history")["count"] == 0
    fact = store.fetch_one(
        """
        SELECT fact_id, symbol, fact_type, published_at, retrieved_at,
               available_at, raw_hash, revision, review_only
        FROM disclosure_facts
        """
    )
    assert fact == {
        "fact_id": "eastmoney-buyback-SH600000-2026-06-01",
        "symbol": "SH600000",
        "fact_type": "share_buyback",
        "published_at": "2026-07-10T16:00:00Z",
        "retrieved_at": "2026-07-12T04:00:00Z",
        "available_at": "2026-07-12T04:00:00Z",
        "raw_hash": fact["raw_hash"],
        "revision": 1,
        "review_only": 1,
    }
    assert len(fact["raw_hash"]) == 64


def test_changed_buyback_payload_appends_a_revision(tmp_path) -> None:
    provider = _Provider()
    store, first_service = _service(tmp_path, provider, hour=4)
    first_service.run(apply=True, rate_limit_seconds=0, include_global=False)
    provider.buyback_amount = 1_500_000.0
    provider.announcement_date = "2026-07-12"
    second_service = ReferenceIngestService(
        store=store,
        provider=provider,
        clock=lambda: _clock(5),
        sleep_fn=lambda _: None,
    )

    result = second_service.run(apply=True, rate_limit_seconds=0, include_global=False)

    assert result["disclosures"]["new_revisions"] == 1
    assert result["disclosures"]["facts_written"] == 1
    rows = store.fetch_all(
        "SELECT revision, published_at, available_at, raw_hash FROM disclosure_facts "
        "ORDER BY revision"
    )
    assert [row["revision"] for row in rows] == [1, 2]
    assert rows[0]["raw_hash"] != rows[1]["raw_hash"]
    assert rows[1]["published_at"] == "2026-07-11T16:00:00Z"
    assert rows[1]["available_at"] == "2026-07-12T05:00:00Z"


def test_dynamic_buyback_price_and_sequence_do_not_create_fake_revision(tmp_path) -> None:
    provider = _Provider()
    store, first_service = _service(tmp_path, provider, hour=4)
    first_service.run(apply=True, rate_limit_seconds=0, include_global=False)
    provider.latest_price = 11.5
    provider.sequence = 99
    second_service = ReferenceIngestService(
        store=store,
        provider=provider,
        clock=lambda: _clock(5),
        sleep_fn=lambda _: None,
    )

    result = second_service.run(apply=True, rate_limit_seconds=0, include_global=False)

    assert result["disclosures"]["facts_written"] == 0
    assert result["disclosures"]["facts_unchanged"] == 1
    assert result["disclosures"]["new_revisions"] == 0
    assert store.fetch_one("SELECT COUNT(*) AS count FROM disclosure_facts")["count"] == 1


def test_ambiguous_same_day_buyback_identity_is_rejected_instead_of_merged(tmp_path) -> None:
    class _DuplicateProvider(_Provider):
        def get_share_buybacks(self) -> pd.DataFrame:
            row = super().get_share_buybacks().iloc[0].to_dict()
            duplicate = {**row, "序号": 2, "已回购金额": 2_000_000.0}
            return pd.DataFrame([row, duplicate])

    store, service = _service(tmp_path, _DuplicateProvider())

    result = service.run(apply=True, rate_limit_seconds=0, include_global=False)

    assert result["status"] == "partial"
    assert result["disclosures"]["status"] == "partial"
    assert result["disclosures"]["valid_rows"] == 1
    assert "ambiguous duplicate buyback identity" in result["disclosures"]["errors"][0]["error"]
    assert store.fetch_one("SELECT COUNT(*) AS count FROM disclosure_facts")["count"] == 1


def test_reference_available_at_is_recorded_after_each_slow_fetch(tmp_path) -> None:
    times = iter(
        [
            datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 12, 4, 5, tzinfo=timezone.utc),
            datetime(2026, 7, 12, 4, 8, tzinfo=timezone.utc),
        ]
    )
    store = SQLiteStore(tmp_path / "retrieval-time.sqlite3")
    service = ReferenceIngestService(
        store=store,
        provider=_Provider(),
        clock=lambda: next(times),
        sleep_fn=lambda _: None,
    )

    service.run(
        apply=True,
        board_limit=1,
        disclosure_limit=1,
        rate_limit_seconds=0,
        include_global=False,
    )

    snapshot = store.fetch_one(
        "SELECT observed_at, effective_date FROM sector_membership_snapshots"
    )
    disclosure = store.fetch_one("SELECT available_at FROM disclosure_facts")
    assert snapshot == {
        "observed_at": "2026-07-12T04:05:00+00:00",
        "effective_date": "2026-07-12",
    }
    assert disclosure["available_at"] == "2026-07-12T04:08:00Z"


def test_external_failures_are_structured_and_never_reported_complete(tmp_path) -> None:
    class _FailingProvider:
        def get_industry_boards(self):
            raise RuntimeError("industry source unavailable")

        def get_industry_members(self, symbol: str):
            raise AssertionError(symbol)

        def get_concept_boards(self):
            return pd.DataFrame([{"board_name": "AI\u7b97\u529b", "board_code": "BK9"}])

        def get_concept_members(self, symbol: str):
            raise TimeoutError(f"members timed out: {symbol}")

        def get_sina_industry_boards(self):
            return pd.DataFrame(columns=["label", "\u677f\u5757"])

        def get_sina_industry_members(self, symbol: str):
            raise AssertionError(symbol)

        def get_share_buybacks(self):
            raise ConnectionError("buyback source unavailable")

    _, service = _service(tmp_path, _FailingProvider())

    result = service.run(rate_limit_seconds=0, include_global=False)

    assert result["status"] == "partial"
    assert result["sectors"]["status"] == "partial"
    assert result["disclosures"]["status"] == "error"
    assert result["sectors"]["errors"][0] == {
        "stage": "board_list",
        "source": "akshare.stock_board_industry_name_em",
        "kind": "industry",
        "error_type": "RuntimeError",
        "error": "industry source unavailable",
    }
    assert result["disclosures"]["errors"][0]["error_type"] == "ConnectionError"


def test_sina_industry_fallback_plans_members_when_eastmoney_boards_fail(tmp_path) -> None:
    class _SinaFallbackProvider(_Provider):
        def get_industry_boards(self):
            raise ConnectionError("eastmoney industry unavailable")

        def get_concept_boards(self):
            raise ConnectionError("eastmoney concept unavailable")

        def get_sina_industry_boards(self) -> pd.DataFrame:
            return pd.DataFrame([{"label": "new_dzqj", "\u677f\u5757": "\u7535\u5b50\u5668\u4ef6"}])

        def get_sina_industry_members(self, symbol: str) -> pd.DataFrame:
            assert symbol == "new_dzqj"
            return pd.DataFrame({"code": ["600000", "000001"]})

    store, service = _service(tmp_path, _SinaFallbackProvider())

    result = service.run(
        apply=True,
        board_limit=1,
        rate_limit_seconds=0,
        include_global=False,
    )

    assert result["status"] == "partial"
    assert result["sectors"]["status"] == "partial"
    assert result["sectors"]["membership_records_written"] == 2
    rows = store.fetch_all(
        """
        SELECT member.symbol, snapshot.sector, snapshot.source, snapshot.confidence
        FROM sector_membership_snapshots AS snapshot
        JOIN sector_membership_snapshot_members AS member
          ON member.snapshot_id = snapshot.id
        ORDER BY member.symbol
        """
    )
    assert [(row["symbol"], row["sector"]) for row in rows] == [
        ("SH600000", "semiconductors"),
        ("SZ000001", "semiconductors"),
    ]
    assert all(row["source"].startswith("akshare.sina.sina_industry:") for row in rows)
    assert all(row["confidence"] == 0.65 for row in rows)


def test_sector_snapshots_remove_and_readd_members_without_rewriting_history(tmp_path) -> None:
    provider = _Provider()
    store = SQLiteStore(tmp_path / "snapshot-lifecycle.sqlite3")

    def ingest(at: datetime) -> dict:
        return ReferenceIngestService(
            store=store,
            provider=provider,
            clock=lambda: at,
            sleep_fn=lambda _: None,
        ).run(
            apply=True,
            board_limit=1,
            rate_limit_seconds=0,
            include_global=False,
        )

    first_at = datetime(2026, 7, 12, 15, tzinfo=timezone.utc)
    first = ingest(first_at)
    provider.industry_members = ["000001"]
    removed_at = datetime(2026, 7, 12, 16, tzinfo=timezone.utc)
    removed = ingest(removed_at)
    provider.industry_members = ["600000"]
    readded_at = datetime(2026, 7, 13, 16, tzinfo=timezone.utc)
    readded = ingest(readded_at)

    assert first["sectors"]["membership_snapshots_written"] == 1
    assert removed["sectors"]["membership_snapshots_written"] == 1
    assert readded["sectors"]["membership_snapshots_written"] == 1
    snapshots = store.fetch_all(
        """
        SELECT member_hash, member_count, observed_at, effective_date
        FROM sector_membership_snapshots
        ORDER BY observed_at
        """
    )
    assert [row["effective_date"] for row in snapshots] == [
        "2026-07-12",
        "2026-07-13",
        "2026-07-14",
    ]
    assert snapshots[0]["member_hash"] == snapshots[2]["member_hash"]

    resolver = ReferenceIngestService(
        store=store,
        provider=provider,
        clock=lambda: readded_at,
        sleep_fn=lambda _: None,
    ).exposure
    assert resolver.sectors_for(
        "SH600000", as_of="2026-07-12T15:30:00+00:00"
    )
    assert resolver.sectors_for(
        "SH600000", as_of="2026-07-12T16:30:00+00:00"
    ) == []
    assert resolver.sectors_for(
        "SH600000", as_of="2026-07-13T16:30:00+00:00"
    )
    assert store.fetch_one("SELECT COUNT(*) AS count FROM sector_membership_snapshots") == {
        "count": 3
    }


def test_live_trading_flag_blocks_provider_calls_and_all_writes(tmp_path, monkeypatch) -> None:
    class _MustNotRun:
        def __getattr__(self, name: str):
            raise AssertionError(f"provider accessed while blocked: {name}")

    _, service = _service(tmp_path, _MustNotRun())
    monkeypatch.setattr(settings, "enable_live_trading", True)

    result = service.run(apply=True)

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"
    assert result["safety"]["writes_enabled"] is False
    assert result["sectors"] == {"status": "not_run"}
    assert result["disclosures"] == {"status": "not_run"}
    assert result["global_markets"] == {"status": "not_run"}


def test_cli_defaults_to_dry_run_and_requires_explicit_apply(capsys) -> None:
    class _Runner:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def run(self, **kwargs: object) -> dict[str, object]:
            self.kwargs = kwargs
            return {
                "status": "completed" if kwargs["apply"] else "planned",
                "mode": "apply" if kwargs["apply"] else "dry_run",
                "safety": {"live_trading_enabled": False},
            }

    runner = _Runner()

    assert (
        main(
            ["--board-limit", "4", "--disclosure-limit", "5", "--rate-limit-seconds", "0"],
            service=runner,
        )
        == 0
    )
    assert runner.kwargs == {
        "apply": False,
        "board_limit": 4,
        "disclosure_limit": 5,
        "rate_limit_seconds": 0.0,
        "global_days": 30,
        "include_global": True,
        "include_sox": True,
        "global_symbol_limit": None,
    }
    assert '"mode": "dry_run"' in capsys.readouterr().out

    assert (
        main(
            [
                "--skip-global",
                "--skip-sox",
                "--global-days",
                "6",
                "--global-symbol-limit",
                "3",
            ],
            service=runner,
        )
        == 0
    )
    assert runner.kwargs["include_global"] is False
    assert runner.kwargs["include_sox"] is False
    assert runner.kwargs["global_days"] == 6
    assert runner.kwargs["global_symbol_limit"] == 3

    assert main(["--apply"], service=runner) == 0
    assert runner.kwargs["apply"] is True


def test_cli_returns_nonzero_for_partial_and_error_statuses() -> None:
    class _Runner:
        def __init__(self, status: str) -> None:
            self.status = status

        def run(self, **_: object) -> dict[str, object]:
            return {"status": self.status, "safety": {"live_trading_enabled": False}}

    assert main([], service=_Runner("partial")) == 2
    assert main([], service=_Runner("error")) == 1
    assert main([], service=_Runner("unsupported")) == 2


def test_cli_apply_exception_does_not_claim_writes_were_disabled(capsys) -> None:
    class _FailingRunner:
        def run(self, **_: object) -> dict[str, object]:
            raise RuntimeError("write transaction failed")

    assert main(["--apply"], service=_FailingRunner()) == 1
    output = capsys.readouterr().out
    assert '"writes_enabled": true' in output
    assert '"write_outcome_known": false' in output
