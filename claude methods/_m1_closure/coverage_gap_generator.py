"""R2 - the single coverage/gap generator. Supersedes coverage_05_manifest.py.

One pinned calendar, one listing-interval definition, one computation emitting the
manifest and the gap shape together, so the two cannot disagree: they are columns of
the same per-symbol record, and the identity

    observed + leading_gap + interior_gap + trailing_gap == eligible

is asserted for every computable security before anything is written.

CALENDAR PROVENANCE (corrected after Codex review). calendar.json is an OFFLINE AUDIT
REFERENCE shipped inside the installed akshare package. It is NOT what the runtime uses:
app/data/trading_calendar.py:61 calls ak.tool_trade_date_hist_sina(), which issues
requests.get("https://finance.sina.com.cn/realstock/company/klc_td_sh.txt") and falls
back to weekday_fallback when offline. An earlier closure note claimed the runtime already
consumed this file. That claim was wrong and is retracted. Which calendar any historical
runtime actually used remains UNKNOWN.

Read-only: both databases opened mode=ro with PRAGMA query_only=1.
"""

from __future__ import annotations

import bisect
import csv
import hashlib
import io
import json
import sqlite3
from pathlib import Path

ROOT = Path(r"D:\codex-A股交易")
TRADING = ROOT / "trading_local.sqlite3"
HISTORY = ROOT / "market_history.sqlite3"
CALENDAR = ROOT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
OUT = ROOT / "claude methods/_m1_closure"

WINDOW_START = "2023-09-04"
WINDOW_END = "2026-09-04"
CALENDAR_BASIS = "akshare_file_fold_calendar_json__offline_audit_reference"


def ro(path):
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.execute("PRAGMA query_only=1")
    conn.row_factory = sqlite3.Row
    return conn


def load_calendar():
    raw = CALENDAR.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw.decode("utf-8"))
    values = [str(x["trade_date"] if isinstance(x, dict) else x) for x in data]
    sessions = sorted(
        {
            (v[:4] + "-" + v[4:6] + "-" + v[6:8]) if len(v) == 8 and v.isdigit() else v
            for v in values
        }
    )
    return sessions, digest


SESSIONS, CALENDAR_SHA256 = load_calendar()


def sessions_between(start, end):
    if not start or not end or start > end:
        return []
    return SESSIONS[bisect.bisect_left(SESSIONS, start): bisect.bisect_right(SESSIONS, end)]


def build():
    conn = ro(TRADING)
    conn.execute("ATTACH ? AS mh", ("file:%s?mode=ro" % HISTORY,))

    instruments = {
        r["symbol"]: dict(r)
        for r in conn.execute(
            "SELECT symbol, name, exchange, asset_type, list_date, delist_date, status "
            "FROM mh.instruments"
        )
    }
    observed = {}
    for r in conn.execute(
        "SELECT symbol, trade_date FROM daily_bar_cache "
        "WHERE quality_status='ready' AND trade_date BETWEEN ? AND ? "
        "AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
        (WINDOW_START, WINDOW_END),
    ):
        observed.setdefault(r["symbol"], set()).add(r["trade_date"])
    conn.close()

    window_sessions = set(sessions_between(WINDOW_START, WINDOW_END))
    records = []
    totals = {
        "securities_in_inventory": 0,
        "computable_with_observations": 0,
        "unknown_list_date": 0,
        "zero_observation_but_eligible": 0,
        "not_a_stock_excluded": 0,
        "off_calendar_rows_excluded": 0,
        "eligible_sum": 0,
        "observed_sum": 0,
        "leading_sum": 0,
        "interior_sum": 0,
        "trailing_sum": 0,
    }

    for symbol in sorted(set(observed) | set(instruments)):
        meta = instruments.get(symbol, {})
        if meta.get("exchange") == "INDEX" or (meta and meta.get("asset_type") != "stock"):
            totals["not_a_stock_excluded"] += 1
            continue

        seen_all = observed.get(symbol, set())
        # Rows dated on something the pinned calendar does not call a session are
        # counted separately, never silently folded into "observed".
        off_calendar = seen_all - window_sessions
        totals["off_calendar_rows_excluded"] += len(off_calendar)

        list_date = meta.get("list_date")
        delist_date = meta.get("delist_date")
        if not list_date:
            basis = "unknown_list_date"
            eligible_list = []
            totals["unknown_list_date"] += 1
        else:
            basis = "listing_interval_pinned_calendar"
            eligible_list = sessions_between(
                max(list_date, WINDOW_START),
                min(delist_date, WINDOW_END) if delist_date else WINDOW_END,
            )

        eligible_set = set(eligible_list)
        seen = seen_all & eligible_set
        n_elig = len(eligible_list)
        n_obs = len(seen)

        if n_elig and n_obs:
            first_i = eligible_list.index(min(seen))
            last_i = eligible_list.index(max(seen))
            leading = first_i
            trailing = n_elig - last_i - 1
            interior = (last_i - first_i + 1) - n_obs
            first_obs, last_obs = min(seen), max(seen)
        elif n_elig:
            leading, interior, trailing = n_elig, 0, 0
            first_obs = last_obs = ""
            totals["zero_observation_but_eligible"] += 1
        else:
            leading = interior = trailing = 0
            first_obs = last_obs = ""

        if n_elig:
            # The reconciliation identity. Nothing is written if it ever fails.
            assert n_obs + leading + interior + trailing == n_elig, (
                "%s: %d+%d+%d+%d != %d" % (symbol, n_obs, leading, interior, trailing, n_elig)
            )
            if n_obs:
                totals["computable_with_observations"] += 1
            totals["eligible_sum"] += n_elig
            totals["observed_sum"] += n_obs
            totals["leading_sum"] += leading
            totals["interior_sum"] += interior
            totals["trailing_sum"] += trailing

        totals["securities_in_inventory"] += 1
        records.append({
            "symbol": symbol,
            "name": meta.get("name", ""),
            "exchange": meta.get("exchange", ""),
            "asset_type": meta.get("asset_type", ""),
            "list_date": list_date or "",
            "delist_date": delist_date or "",
            "status": meta.get("status", ""),
            "eligibility_basis": basis,
            "eligible_sessions": n_elig,
            "observed_sessions": n_obs,
            "leading_gap": leading,
            "interior_gap": interior,
            "trailing_gap": trailing,
            "first_observed": first_obs,
            "last_observed": last_obs,
            "off_calendar_rows": len(off_calendar),
            "coverage_ratio": round(n_obs / n_elig, 6) if n_elig else "",
            # Gap causes stay unknown. This project holds no suspension or delist
            # calendar, so naming a reason here would be fabricated evidence.
            "gap_cause": "unknown_no_suspension_or_delist_calendar",
        })

    return {"records": records, "totals": totals}


def write(result):
    records = result["records"]
    OUT.mkdir(parents=True, exist_ok=True)
    cols = list(records[0].keys())
    # utf-8 without BOM. The superseded generator used utf-8-sig, which put a BOM on
    # the header and corrupted the first column name for strict CSV readers.
    with io.open(OUT / "coverage_reconciled.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(records)

    meta = {
        "generator": "coverage_gap_generator.py",
        "supersedes": [
            "_m1_evidence/coverage_05_manifest.py",
            "_m1_evidence/coverage_manifest.csv",
            "_m1_evidence/coverage_gap_shape.csv",
        ],
        "window": [WINDOW_START, WINDOW_END],
        "calendar_basis": CALENDAR_BASIS,
        "calendar_path": str(CALENDAR),
        "calendar_sha256": CALENDAR_SHA256,
        "calendar_is_runtime_source": False,
        "calendar_note": (
            "Offline audit reference only. app/data/trading_calendar.py:61 calls "
            "ak.tool_trade_date_hist_sina(), which issues an HTTP request to Sina and "
            "falls back to weekday_fallback offline. Which calendar any historical "
            "runtime used is UNKNOWN."
        ),
        "nominal_window_sessions": len(sessions_between(WINDOW_START, WINDOW_END)),
        "listing_interval_definition": (
            "eligible = pinned-calendar sessions in [max(list_date, window_start), "
            "min(delist_date, window_end)]; unknown list_date => not computable"
        ),
        "reconciliation_identity":
            "observed + leading_gap + interior_gap + trailing_gap == eligible",
        "totals": result["totals"],
    }
    (OUT / "coverage_reconciled_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    res = build()
    write(res)
    t = res["totals"]
    print("calendar sha256      %s" % CALENDAR_SHA256)
    print("nominal window       %d sessions" % len(sessions_between(WINDOW_START, WINDOW_END)))
    print("rows written         %d" % len(res["records"]))
    for k in t:
        print("  %-32s %s" % (k, t[k]))
    ident = t["observed_sum"] + t["leading_sum"] + t["interior_sum"] + t["trailing_sum"]
    print("identity             %d == %d  %s" % (
        ident, t["eligible_sum"], "OK" if ident == t["eligible_sum"] else "MISMATCH"))
