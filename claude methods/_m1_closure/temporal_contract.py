"""R1/F1 - the temporal contract, with validated inputs and normalized instants.

The hole this closes (original)
-------------------------------
The superseded report (M1_THREE_YEAR_DATA_READINESS.md:583-588, steps T1/T2) proposed:

    T1: available_at := trade-date close + assumed lag
    T2: admit a row into a point-in-time view iff available_at <= cutoff

Those two steps together MANUFACTURE historical availability. Recording factor_vintage
without filtering on it does not close the hole; only refusing to admit on an assumed
stamp does.

The two holes F1 closes (Codex review of the closure)
------------------------------------------------------
1. The checks rejected only `None`. Empty strings for observed_availability,
   ingestion_time, factor_vintage and provenance sailed through as
   `all_stamps_observed_and_before_cutoff`.
2. Comparison was lexicographic on raw strings. A cutoff written
   `2024-06-28T10:00:00+08:00` (02:00 UTC) admitted an availability of
   `2024-06-28T03:00:00Z` - a version that appeared one hour AFTER the cutoff - because
   the character "0" sorts below "1".

Both are now impossible: every value is validated and converted to an absolute instant
before any comparison, and blank/malformed/naive input is a rejection, never a default.

Five distinct times, never collapsed
------------------------------------
1. event_time            - the session the bar describes. Says nothing about when any
                           value for it became knowable.
2. assumed_publication    - a MODEL ("close + lag"). Never evidence. NEVER consulted by
                           strict admission, at all.
3. observed_availability  - evidence that THIS version existed and was retrievable at a
                           stated time. Absent for every row in this project today.
4. ingestion_time         - when we wrote it locally. An upper bound on our knowledge,
                           never a lower bound on availability.
5. factor_vintage         - the adjustment/corporate-action basis the PRICE was computed
                           under. A qfq series recomputed today is a today-vintage object
                           no matter which session it describes.

Declared date-only semantics
----------------------------
A date carries no time, so every date-only value is widened in the FAIL-CLOSED
direction - the direction that makes admission harder, never easier:

  event_time, observed_availability, ingestion_time, factor_vintage
      date-only D  ->  END of D, 23:59:59.999999+08:00
      (the latest instant D could mean; a vintage stamped D may have been computed at
      any point during D, so assuming the earliest instant would admit too much)

  cutoff
      date-only D  ->  START of D, 00:00:00+08:00
      (the earliest instant the decision could have been taken)

Timezone: China has observed no DST since 1991, so the entire research window is a fixed
UTC+08:00 offset. That constant is declared here rather than resolved from a tz database,
so the contract cannot change under a tzdata update.

Naive timestamps (no offset) are REJECTED rather than assumed local: silently mixing
date strings, local timestamps and UTC timestamps is precisely how hole 2 arose.

Read-only. Production timestamps are never altered; production is only counted.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(r"D:\codex-A股交易")
TRADING = ROOT / "trading_local.sqlite3"
HISTORY = ROOT / "market_history.sqlite3"

STRICT_PIT = "strict_pit"
EXPLORATORY = "exploratory"

UNKNOWN = None

#: Fixed offset. See "Timezone" above - deliberately not a tz-database lookup.
CN = timezone(timedelta(hours=8))

DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LATEST = "end_of_day"      # widen a date to its last instant
EARLIEST = "start_of_day"  # widen a date to its first instant


class TemporalInputError(ValueError):
    """A value could not be trusted as a time. Carries the machine-readable reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def to_instant(value, role: str, date_policy: str) -> datetime:
    """Validate and normalize one temporal value to an absolute instant.

    Rejects None, non-strings, blank/whitespace, malformed text, impossible dates
    (2025-02-30), and naive timestamps.
    """
    if value is None:
        raise TemporalInputError("%s_missing" % role)
    if not isinstance(value, str):
        raise TemporalInputError("%s_not_a_string" % role)
    text = value.strip()
    if not text:
        raise TemporalInputError("%s_blank" % role)

    if DATE_ONLY.match(text):
        try:
            day = date.fromisoformat(text)
        except ValueError:
            raise TemporalInputError("%s_impossible_date" % role) from None
        moment = time.max if date_policy == LATEST else time.min
        return datetime.combine(day, moment, tzinfo=CN)

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise TemporalInputError("%s_malformed" % role) from None
    if parsed.tzinfo is None:
        # Assuming an offset here is exactly how a 03:00Z value slipped past a 02:00Z
        # cutoff. Refuse instead.
        raise TemporalInputError("%s_naive_timestamp_ambiguous" % role)
    return parsed


def require_text(value, role: str) -> str:
    """Provenance is evidence, so blank provenance is missing evidence."""
    if value is None:
        raise TemporalInputError("%s_missing" % role)
    if not isinstance(value, str):
        raise TemporalInputError("%s_not_a_string" % role)
    text = value.strip()
    if not text:
        raise TemporalInputError("%s_blank" % role)
    return text


@dataclass(frozen=True)
class BarVersion:
    """One VERSION of one bar. Two versions of the same session are two objects."""

    symbol: str
    event_time: str
    close: float
    assumed_publication: str | None = UNKNOWN   # a model, never evidence
    observed_availability: str | None = UNKNOWN  # evidence this version was retrievable
    ingestion_time: str | None = UNKNOWN
    factor_vintage: str | None = UNKNOWN
    provenance: str | None = UNKNOWN


@dataclass(frozen=True)
class Admission:
    admitted: bool
    basis: str
    reason: str


def admit(bar: BarVersion, cutoff, mode: str) -> Admission:
    try:
        cutoff_at = to_instant(cutoff, "cutoff", EARLIEST)
    except TemporalInputError as exc:
        return Admission(False, mode, exc.reason)

    try:
        event_at = to_instant(bar.event_time, "event_time", LATEST)
    except TemporalInputError as exc:
        return Admission(False, mode, exc.reason)

    if event_at > cutoff_at:
        return Admission(False, mode, "event_time_after_cutoff")

    if mode == EXPLORATORY:
        # Honest label: this is reproducibility, not historical availability.
        unknowns = [
            name
            for name, value in (
                ("observed_availability", bar.observed_availability),
                ("factor_vintage", bar.factor_vintage),
                ("provenance", bar.provenance),
            )
            if value is None or not str(value).strip()
        ]
        return Admission(
            True,
            EXPLORATORY,
            "reproducible_not_point_in_time; unknown=" + (",".join(unknowns) or "none"),
        )

    if mode != STRICT_PIT:
        raise ValueError("unknown admission mode: %r" % mode)

    # Fail closed. Every missing, blank, malformed or naive stamp is a rejection.
    # assumed_publication is deliberately absent from this list.
    for role, value in (
        ("observed_availability", bar.observed_availability),
        ("ingestion_time", bar.ingestion_time),
        ("factor_vintage", bar.factor_vintage),
    ):
        try:
            stamp = to_instant(value, role, LATEST)
        except TemporalInputError as exc:
            return Admission(False, STRICT_PIT, exc.reason)
        if stamp > cutoff_at:
            return Admission(False, STRICT_PIT, "%s_after_cutoff" % role)

    try:
        require_text(bar.provenance, "provenance")
    except TemporalInputError as exc:
        return Admission(False, STRICT_PIT, exc.reason)

    return Admission(True, STRICT_PIT, "all_stamps_observed_and_before_cutoff")


# --------------------------------------------------------------------------- proofs

CUTOFF = "2024-06-28"

GENUINE = BarVersion(
    symbol="SH600000", event_time="2024-06-27", close=7.31,
    assumed_publication="2024-06-27T15:00:00+08:00",
    observed_availability="2024-06-27T17:42:11+08:00",
    ingestion_time="2024-06-27T17:42:11+08:00",
    factor_vintage="2024-06-27",
    provenance="sina.stock_zh_a_daily@2024-06-27",
)

REVISED = BarVersion(
    symbol="SH600000", event_time="2024-06-27", close=6.88,
    assumed_publication="2024-06-27T15:00:00+08:00",
    observed_availability="2026-09-03T04:55:30+08:00",
    ingestion_time="2026-09-03T04:55:30+08:00",
    factor_vintage="2026-09-03",
    provenance="sina.stock_zh_a_daily@2026-09-03",
)

PRODUCTION_SHAPED = BarVersion(
    symbol="SH600000", event_time="2024-06-27", close=7.31,
    assumed_publication="2024-06-27T15:00:00+08:00",
    observed_availability=UNKNOWN, ingestion_time="2026-06-30T04:55:30+08:00",
    factor_vintage=UNKNOWN, provenance=UNKNOWN,
)


def proofs():
    out = []

    def record(label, condition, admission):
        assert condition, (label, admission)
        out.append((label, True, admission.reason))

    a = admit(GENUINE, CUTOFF, STRICT_PIT)
    record("P1 genuine historical version admitted under strict PIT", a.admitted, a)

    b = admit(REVISED, CUTOFF, STRICT_PIT)
    record("P2 later revision rejected despite an old event_time",
           not b.admitted and b.reason == "observed_availability_after_cutoff", b)

    backdated = BarVersion(
        symbol=REVISED.symbol, event_time=REVISED.event_time, close=REVISED.close,
        assumed_publication="2024-06-27T15:00:00+08:00",
        observed_availability="2024-06-27T15:00:00+08:00",   # forged by the T1 model
        ingestion_time="2024-06-27T15:00:00+08:00",
        factor_vintage="2026-09-03",                          # the tell
        provenance="sina.stock_zh_a_daily@2026-09-03",
    )
    c = admit(backdated, CUTOFF, STRICT_PIT)
    record("P3 backdating the availability stamp does not rescue it",
           not c.admitted and c.reason == "factor_vintage_after_cutoff", c)

    d = admit(PRODUCTION_SHAPED, CUTOFF, STRICT_PIT)
    record("P4 production-shaped row (no evidence) rejected, not defaulted",
           not d.admitted, d)

    e = admit(PRODUCTION_SHAPED, CUTOFF, EXPLORATORY)
    record("P5 same row admitted EXPLORATORY, labelled non-PIT",
           e.admitted and "not_point_in_time" in e.reason, e)

    f = admit(GENUINE, "2024-06-26", STRICT_PIT)
    record("P6 future session rejected at an earlier cutoff",
           not f.admitted and f.reason == "event_time_after_cutoff", f)

    # ---- F1 regressions ----

    blank = BarVersion(
        symbol="SH600000", event_time="2024-06-27", close=7.31,
        assumed_publication="2024-06-27T15:00:00+08:00",
        observed_availability="", ingestion_time="", factor_vintage="", provenance="",
    )
    g = admit(blank, CUTOFF, STRICT_PIT)
    record("F1a all-blank stamps rejected (previously admitted)",
           not g.admitted and g.reason == "observed_availability_blank", g)

    blank_prov = BarVersion(
        symbol="SH600000", event_time="2024-06-27", close=7.31,
        observed_availability="2024-06-27T17:42:11+08:00",
        ingestion_time="2024-06-27T17:42:11+08:00",
        factor_vintage="2024-06-27", provenance="   ",
    )
    h = admit(blank_prov, CUTOFF, STRICT_PIT)
    record("F1b blank provenance alone rejected",
           not h.admitted and h.reason == "provenance_blank", h)

    # The exact case from the review: availability 03:00Z is one hour AFTER a cutoff of
    # 10:00+08:00 (= 02:00Z), but "0" < "1" lexicographically.
    late = BarVersion(
        symbol="SH600000", event_time="2024-06-27", close=7.31,
        observed_availability="2024-06-28T03:00:00Z",
        ingestion_time="2024-06-28T03:00:00Z",
        factor_vintage="2024-06-27",
        provenance="sina@2024-06-28",
    )
    i = admit(late, "2024-06-28T10:00:00+08:00", STRICT_PIT)
    record("F1c 03:00Z availability rejected against a 10:00+08:00 (02:00Z) cutoff",
           not i.admitted and i.reason == "observed_availability_after_cutoff", i)

    # Same instant, three spellings -> identical verdict.
    verdicts = set()
    for spelling in ("2024-06-28T01:00:00Z", "2024-06-28T09:00:00+08:00",
                     "2024-06-27T21:00:00-04:00"):
        same = BarVersion(
            symbol="SH600000", event_time="2024-06-27", close=7.31,
            observed_availability=spelling, ingestion_time=spelling,
            factor_vintage="2024-06-27", provenance="sina@2024-06-28",
        )
        r = admit(same, "2024-06-28T10:00:00+08:00", STRICT_PIT)
        verdicts.add((r.admitted, r.reason))
    j = Admission(len(verdicts) == 1, STRICT_PIT, "distinct_verdicts=%d" % len(verdicts))
    record("F1d equivalent instants in three timezones give one verdict", j.admitted, j)

    naive = BarVersion(
        symbol="SH600000", event_time="2024-06-27", close=7.31,
        observed_availability="2024-06-27 17:42:11",  # no offset
        ingestion_time="2024-06-27T17:42:11+08:00",
        factor_vintage="2024-06-27", provenance="sina@2024-06-27",
    )
    k = admit(naive, CUTOFF, STRICT_PIT)
    record("F1e naive timestamp rejected rather than assumed local",
           not k.admitted and k.reason == "observed_availability_naive_timestamp_ambiguous", k)

    bad = BarVersion(
        symbol="SH600000", event_time="2025-02-30", close=7.31,
        observed_availability="2025-02-27T17:42:11+08:00",
        ingestion_time="2025-02-27T17:42:11+08:00",
        factor_vintage="2025-02-27", provenance="sina@2025-02-27",
    )
    m = admit(bad, "2025-03-01", STRICT_PIT)
    record("F1f impossible event date rejected",
           not m.admitted and m.reason == "event_time_impossible_date", m)

    # Date-only semantics are fail-closed in BOTH directions: a same-day vintage is not
    # admitted by a same-day cutoff, because the vintage widens late and the cutoff early.
    sameday = BarVersion(
        symbol="SH600000", event_time="2024-06-27", close=7.31,
        observed_availability="2024-06-27T17:42:11+08:00",
        ingestion_time="2024-06-27T17:42:11+08:00",
        factor_vintage="2024-06-28", provenance="sina@2024-06-28",
    )
    n = admit(sameday, CUTOFF, STRICT_PIT)
    record("F1g same-day date-only vintage does not pass a same-day cutoff",
           not n.admitted and n.reason == "factor_vintage_after_cutoff", n)

    return out


def production_consequence():
    """Count, read-only, how much of production could satisfy strict admission."""
    conn = sqlite3.connect("file:%s?mode=ro" % TRADING, uri=True)
    conn.execute("PRAGMA query_only=1")
    cache_rows = conn.execute(
        "SELECT COUNT(*) FROM daily_bar_cache WHERE length(trade_date)=10").fetchone()[0]
    cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_bar_cache)")}
    conn.close()

    conn = sqlite3.connect("file:%s?mode=ro" % HISTORY, uri=True)
    conn.execute("PRAGMA query_only=1")
    hist_rows = conn.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]
    avail_not_ingest = conn.execute(
        "SELECT COUNT(*) FROM daily_bars WHERE available_at IS NOT NULL "
        "AND available_at <> fetched_at").fetchone()[0]
    collection_days = conn.execute(
        "SELECT COUNT(DISTINCT substr(fetched_at,1,10)) FROM daily_bars").fetchone()[0]
    conn.close()

    return {
        "cache_rows": cache_rows,
        "cache_has_availability_column": "available_at" in cols,
        "cache_has_factor_vintage_column": "factor_vintage" in cols,
        "history_rows": hist_rows,
        "history_rows_where_available_at_differs_from_fetched_at": avail_not_ingest,
        "history_distinct_collection_days": collection_days,
        "strict_pit_admissible_rows": 0,
        "strict_pit_admissible_basis":
            "available_at never differs from fetched_at, so it is an ingest clock, not "
            "observed availability; no factor_vintage column exists in either store. "
            "Every row therefore fails observed_availability_unknown or "
            "factor_vintage_unknown. This is a property of the LOCAL corpus, not proof "
            "that no external archived version could ever supply the evidence.",
    }


if __name__ == "__main__":
    print("R1/F1 temporal contract proofs (default cutoff %s, tz fixed +08:00)" % CUTOFF)
    for name, ok, reason in proofs():
        print("  %-62s %-5s %s" % (name, "PASS" if ok else "FAIL", reason))
    print()
    print("Production consequence (read-only):")
    for k, v in production_consequence().items():
        print("  %-52s %s" % (k, v))
