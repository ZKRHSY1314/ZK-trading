# Reference-basis lineage audit — where the retained `qfq` labels come from

> **Status `proposed for review`.** Task `REF-BASIS-LINEAGE-20260909`, executing
> `_m2_codex_review/reference_basis_lineage_dispatch_20260909.txt` (`1cb6443f…`) under the user's
> continuous offline-analysis authorization.
>
> **Static provenance audit.** Existing source files read **as text** and existing retained JSON
> read as data. **No SQLite open, no provider or adapter invocation, no service-initializing
> import, no decoder, no replay, no network, no retrieval, no capture, no new extract.** No
> package was installed and no documentation fetched. No credential, config-secret or token file
> was opened. No numerical price-relation study was rerun and the proposed non-price study was not
> performed. No scratch script and no output directory were created.
>
> **This adopts nothing and certifies nothing.** It does not certify the vendor or reference basis,
> does not rewrite the P1 proposal and does not close U-6 by inference. **P1 open, U-6 deferred,
> every eligibility result false, source capability FAIL (including the retained EV6
> disagreements), both capture authorizations consumed.** Not M2 completion.
>
> **Revision 2** — corrected against `M2B_REFERENCE_BASIS_LINEAGE_CODEX_REVIEW.md` (`a3c6f832…`)
> findings **RL-R1** and **RL-R2**. Revision 1 (`33ca83bc…`) let current-code semantics harden into
> claims about historical label origins, the actual selection mechanism and upstream response
> semantics; §0 lists what is withdrawn. The verified traces, hashes and segment counts are
> preserved.
>
> **The one-sentence result, stated at the strength the bytes carry.** In the **inspected current
> code paths**, each stock reference source's `adjustment_mode` is assigned from a request argument
> or a hard-coded writer default, and for one source a startup migration can assign it from the
> `source` string alone; **no independently verified basis declaration is retained for any of these
> reference rows**, and the retained rows carry **no** binding to arguments, response metadata, code
> version or ingestion history — so **Q-3 remains open**, now with the missing links named. **Which
> path actually produced any retained label is not established by this audit**, and nothing here
> shows what the upstream responses did or did not declare.

---

## 0. What revision 2 corrects

| Finding | Correction |
|---|---|
| **RL-R1(a)** — the headline asserted "No reference source declares its basis" | **Withdrawn as an upstream claim.** Restated as: the inspected current paths assign the label from arguments or defaults, and **no independently verified basis declaration is retained** for these rows. A parser that discards metadata does not show the original response carried none |
| **RL-R1(b)** — the Tonghuashun echo was characterised as "not a convention declaration" | **Withdrawn.** The field supplies a **response-value versus request-code comparison**. Without the host contract or the original response, that proves neither echo-only semantics **nor** that the host did not silently apply another convention |
| **RL-R1(c)** — §3.2/§3.3/§8 said the `stock_zh_a_daily` and `local.quotes.candle` labels "were **not** produced" by D-2 and therefore "originated in the writer path" | **Withdrawn.** D-2 cannot alter a row whose `source` **at execution time** is an excluded string; that excludes one current branch under those inputs, and does **not** exclude an earlier `source` value, a different historical migration, or another writer. No positive attribution to the writer path is made for any segment |
| **RL-R1(d)** — §5 said the label's uniformity "is partly a selection effect" | **Withdrawn as a causal attribution.** The `ready` filter combined with the shown writer **can induce** uniformity **if that writer produced the rows**; the historical path is unbound, so the filter's actual contribution is **not established**. The uniformity **observation** stands |
| **RL-R1(e)** — D-1 implied the retained database necessarily passed through `ALTER TABLE … ADD COLUMN`, leaving pre-existing rows `'unknown'` and eligible for D-2 | **Withdrawn.** `CREATE TABLE IF NOT EXISTS daily_bar_cache` already declares the column (`sqlite_store.py:933`) and the `ALTER` is wrapped in `try/except sqlite3.OperationalError: pass` (`:1966-1969`), so a database created fresh never takes that path and a duplicate-column error is swallowed. Neither the ALTER's execution nor any row's eligibility for D-2 is asserted |
| **RL-R1(f)** — universal phrasings: "not pinned anywhere", "no local file can supply" | **Scoped** to the retained evidence actually inspected by this audit, which did not exhaust every local artefact |
| **RL-R2(a)** — C-4 and §10 sold `created_at` versus `updated_at` as discriminating a writer path from a bulk migration stamp | **Withdrawn.** D-2 (`sqlite_store.py:1978-1989`) updates **only `adjustment_mode`** and touches **neither** timestamp; the ordinary upsert (`daily_bar_cache.py:390-405`) changes `updated_at` while **preserving `created_at`**, so an old creation time arises without any migration; bulk ordinary insertion yields identical timestamps without one; and the two columns use **different clock conventions** — SQLite `CURRENT_TIMESTAMP` for `created_at` versus naive local `datetime.now()` written to `updated_at` — so raw subtraction assumes a common clock it does not have. **Timestamps alone cannot identify whether D-2 ran, and cannot resolve L-5 or L-6.** The discriminating type is a **migration/ingestion log or historically bound before/after evidence** |
| **RL-R2(b)** — §10 framed an unfiltered extract as deciding between "the convention was uniform" and "the filter only admitted one label" | **False dichotomy removed.** Such an extract would expose excluded rows and their **recorded** labels and quality flags; it would **not** establish a true convention or causally attribute observed uniformity to filtering. **No re-extract is requested or performed** |

Preserved: the per-source code trace, all eight source-file hashes, the seven stock and four index
source/fetch groups, the per-segment binding table, the named missing links, and the
certification-withheld conclusion.

---

## 1. Read scope and hashes

**Project source, read as text only.** Worktree state versus `HEAD` (`73f266d`) is recorded because
current code is not evidence about historical rows.

| File | lines | SHA-256 | vs `HEAD` |
|---|---|---|---|
| `backend/app/data/akshare_provider.py` | 116 | `375f34adc34adf131e44194002dc96242c45269fd445b693f2eb0bcdc84acccf` | unmodified |
| `backend/app/data/daily_bar_cache.py` | 1062 | `90ec7bd0038147bd48ef5f9e3a354d720eeed4d05443b0a9a93039e71d7ff533` | unmodified |
| `backend/app/data/tonghuasun_provider.py` | 556 | `3cd5a67c014925454d4896d5abe456430f9e758d06a4babab146a097265310f3` | unmodified |
| `backend/app/data/source_comparison.py` | 367 | `3490c0090928256674e4732989d9d24cc632f312a69202b4e350b5f8f4713c7d` | unmodified |
| `backend/app/config.py` | 67 | `1cb7dd7bc7d48593eda083db80d31f1d712323c49df74c4d0d1f57416129e7d7` | unmodified |
| `backend/app/storage/sqlite_store.py` | 2051 | `35b2e6f9d345c6a3c4b0bf3105b51827704acbebc72ebd649d06d8221394adbe` | **MODIFIED** — 135 insertions / 1 deletion uncommitted |

The uncommitted `sqlite_store.py` change belongs to the user's working tree and **was not touched**.
It does **not** affect this audit's subject: the `adjustment_mode` migration region (`:1976-1991`) is
**byte-identical between `HEAD` and the worktree**, verified by diffing that region alone.

**Installed AkShare, read as text and hashed without importing the package.**

| File | SHA-256 | Retained pin? |
|---|---|---|
| `backend/.venv/Lib/site-packages/akshare/stock/stock_zh_a_sina.py` | `a3acc94625983ec233b769d36afe742107dd865588ccf3799b582babd72de2b8` | **yes** — equals the value in the retained basis record (see §6, L-4) |
| `backend/.venv/Lib/site-packages/akshare/stock_feature/stock_hist_em.py` | `749a94a192bcd79ee76867fb8dfc7c563613cf08afb1dd72ca5a97c471bcd3d8` | **no — not pinned in any retained artefact inspected here** |

`akshare/_version.py` gives `__version__ = "1.18.64"`, matching the retained
`basis_evidence_ref.capture_pins.adapter_constants.akshare_version`.

**Retained JSON read as data.**

| Artifact | SHA-256 |
|---|---|
| `claude methods/_m2_smoke/revision_20260908T082833Z_r2abc_v2/reference/reference_extract.json` | `ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2` |
| `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/PROVENANCE.json` | `1a262d74110e30ef33e32d291038fc6c78a8c70204ccdad581017e9330575456` |
| `claude methods/_m2_smoke/basis_eval_…__br_r1_r4/basis_records.json` | `c5b1bf3c2f660dcca84c1f3d44fba8252b1580d98fbce300d5412340d32448de` |
| `claude methods/_m2_smoke/basis_eval_…__br_r1_r4/PROVENANCE.json` | `a1b662a2cf67bb331202cec7e086887e59115994abd9828d4bcde7d4aafee514` |

**Documents read for scope and prior findings:** `M2B_U6_RETAINED_STUDY.md` `65fbe917…`,
`M2B_U6_RETAINED_STUDY_CODEX_ACCEPTANCE.md` `a6967def…`, `M2B_U6_READINESS_ASSESSMENT.md`
`de130cf0…`, `M2B_P1_BASIS_CONTRACT_PROPOSAL.md` `71e0dc52…`, and the dispatch `1cb6443f…`.

---

## 2. The question, narrowed

The accepted study and the readiness assessment both name **Q-3 / §3.3 condition 4** as the
decisive open item: the retained reference rows *record* a basis label, and nothing establishes it
is *true of the rows*. This audit asks what the existing bytes can settle about **how that label
got there** — which is a different and answerable question from what the upstream convention
actually was.

Four candidate origins are traced for each source: **(a)** a request argument we chose; **(b)** a
declaration in the response; **(c)** a writer default or fallback; **(d)** a schema default or a
migration.

---

## 3. Trace, per reference source

### 3.1 `akshare.stock_zh_a_hist` — SH600011, 37 rows, `updated_at 2026-07-15T14:16:19`

**Loader.** `daily_bar_cache.py:148`:

```python
"akshare.stock_zh_a_hist": lambda: self.builder.provider.get_daily_bars(code),
```

Called with **no `adjust` argument**, so `AkshareProvider.get_daily_bars`'s own default applies —
`akshare_provider.py:66`, `adjust: str = "qfq"` — which is passed to
`ak.stock_zh_a_hist(..., adjust=adjust, ...)` at `:69-74`.

**Upstream.** `stock_hist_em.py:979-987` maps the argument to a request parameter:

```python
adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
params = {... "fqt": adjust_dict[adjust], ...}
```

So adjustment is **requested**, as `fqt`. AkShare's own signature default is `adjust: str = ""`
(unadjusted) — ours overrides it to `"qfq"`. Nothing in the returned frame names a basis: the
function assigns fixed Chinese column names and returns them.

**Where the label comes from.** `AkshareProvider.get_daily_bars` sets **no `frame.attrs` at all** —
no `source`, no `adjustment_mode`, no `volume_unit`. The writer therefore falls through to its own
default, `daily_bar_cache.py:194-203`:

```python
adjustment_mode = "qfq"                      # <- assumed BEFORE inspecting anything
quality_status = "ready"
effective_source = source
volume_unit = "hand"
if isinstance(raw_bars, pd.DataFrame):
    adjustment_mode = str(raw_bars.attrs.get("adjustment_mode") or adjustment_mode).lower()
```

With no attr present, `adjustment_mode` stays the hard-coded `"qfq"` from line 194, and
`effective_source` stays the loader key `"akshare.stock_zh_a_hist"` from line 196.

**A second candidate origin.** §4's startup migration, as it currently stands, assigns
`adjustment_mode = 'qfq'` to any row still `'unknown'` whose `source` string at execution time is
`akshare.stock_zh_a_hist`. So the label could have come from the writer default above **or** from
that migration. **The retained evidence distinguishes neither** (L-6), and neither is asserted.

**Candidate origins in current code: (a) request argument + (c) writer default, or (d) migration.
No response declaration is retained — which is not a finding that the response contained none.
Which origin produced this segment's label is not established.**

### 3.2 `akshare.stock_zh_a_daily` — SH600011, 470 + 1 rows; BJ920000, 1 row

**Loader.** `daily_bar_cache.py:149-151` calls
`self.builder.provider.get_daily_bars_sina(code, adjust="qfq")` — the string `"qfq"` is a
**literal in our own call site**.

**Provider.** `akshare_provider.py:106-115`:

```python
frame = ak.stock_zh_a_daily(symbol=f"{prefix}{code}", adjust=adjust)
...
frame.attrs["source"] = "akshare.stock_zh_a_daily"
frame.attrs["adjustment_mode"] = "qfq" if adjust == "qfq" else "unknown"
frame.attrs["volume_unit"] = "hand"
```

Line 114 is explicit: **the label is a function of the argument we passed**, nothing else. The
writer then adopts it at `daily_bar_cache.py:199-201`.

This is the same construction the P1 proposal already identified as the defect M2a's provenance
module exists to close (`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` §1, citing
`akshare_provider.py:114-115`). **This audit's addition is that the reference side of the
comparison rests on the identical construction**, so the reference leg is not the independent
check that condition 4 asks for.

`stock_zh_a_sina.py` (`a3acc946…`) is the module whose transformation behaviour the retained basis
record already describes: `hfq` multiplies by the factor series, `qfq` divides by it, `adjust=""`
returns the klc series untouched. That is **our-side transformation** knowledge (statement (b) of
the proposal's §1), not a vendor declaration.

**Candidate origin in current code: (a) request argument, adopted by (c).** D-2's current branch
cannot alter a row whose `source` at execution time is `akshare.stock_zh_a_daily`, since that
string is absent from its `WHERE` list — but that excludes only **that branch under those
inputs**, not an earlier `source` value, a different historical migration text, or another
writer. **No origin is attributed to this segment**, and no response declaration is retained,
which is not a finding that none existed.

### 3.3 `tonghuasun.local.quotes.candle` — BJ920000, 470 + 30 rows; SH600011, 30 rows

**Loader.** `daily_bar_cache.py:141-147` calls
`self.tonghuasun_provider.get_daily_bars(symbol, adjust="qfq", days=days)` — again a **literal
`"qfq"` at our call site**.

**Provider.** `tonghuasun_provider.py:42`, `:216-249`:

```python
_ADJUSTMENT_VALUES = {"": 0, "none": 0, "qfq": 1, "hfq": 2}
...
adjustment_name = str(adjust or "").strip().lower()
if adjustment_name not in _ADJUSTMENT_VALUES:
    raise ValueError(f"unsupported Tonghuashun adjustment mode: {adjust}")
...
payload = {... "adjustment": _ADJUSTMENT_VALUES[adjustment_name]}
data = self._post_candles(payload)
echoed_adjustment = data.get("adjustment")
if echoed_adjustment is not None:
    try:
        matches_request = int(echoed_adjustment) == payload["adjustment"]
    except (TypeError, ValueError):
        matches_request = False
    if not matches_request:
        raise TonghuasunDataError(
            "local Tonghuashun candle response has a mismatched adjustment mode"
        )
...
frame.attrs["adjustment_mode"] = adjustment_name or "none"
```

**This is the only one of the three with any response-side comparison — and what that comparison
means is not determined by this code alone.** Two limits, both visible in the code:

1. The check is **conditional** — `if echoed_adjustment is not None`. When the field is absent no
   verification happens, and line 249 still labels the frame from the **request name**.
2. When present, the code compares a **response value against the request code it sent**. What
   the host's field denotes is governed by the host's contract, which this audit did not read
   and which is not in the retained evidence. So this comparison establishes **neither** that
   the field is a mere echo of the request **nor** that the host could not have applied some
   other convention while returning a matching value. It carries no factor, divisor or
   reference date either way.

Whether the field was present for the retained rows is **not recorded anywhere in the retained
evidence** — the extract keeps no response metadata (L-1).

**Candidate origin in current code: (a) request argument, adopted by (c), with a conditional
response-versus-request comparison whose semantics are undetermined here.** As with §3.2, D-2's
current branch excludes this `source` string, which excludes that branch under those inputs and
nothing more. **No origin is attributed to these segments.**

### 3.4 `akshare.stock_zh_index_daily` — SH000300, context only

The index rows are labelled `none`, and two independent code paths agree on that value:
`_normalize_index_bars` hard-codes `adjustment_mode="none"` (`daily_bar_cache.py:927`), and §4's
migration's `ELSE 'none'` branch covers `source LIKE 'akshare.stock_zh_index_daily%'`. Included for
completeness; per the proposal's **U-7** an index observation is not evidence about a stock's basis,
and none is drawn.

---

## 4. Cache defaults, fallbacks, stickiness and the startup migration

**D-1 — schema default.** `sqlite_store.py:933` and `:1962`:

```sql
adjustment_mode TEXT NOT NULL DEFAULT 'unknown'
ALTER TABLE daily_bar_cache ADD COLUMN adjustment_mode TEXT NOT NULL DEFAULT 'unknown'
```

Two paths exist, and **which one this database took is not established**. `CREATE TABLE IF NOT
EXISTS daily_bar_cache` (`:922-939`) already declares the column, so a database created fresh never
needs the `ALTER`; and the `ALTER` statements are wrapped in `try/except sqlite3.OperationalError:
pass` (`:1966-1969`), so a duplicate-column error on an existing table is swallowed silently.
Revision 1 asserted that the column "was added by migration" and that pre-existing rows therefore
became `'unknown'` and were eligible for D-2. **That is withdrawn**: no retained evidence shows the
`ALTER` executed on this database, and none shows any retained row was ever `'unknown'`.

**D-2 — the startup migration assigns the label from the `source` string alone.**
`sqlite_store.py:1976-1991`:

```sql
UPDATE daily_bar_cache
SET adjustment_mode = CASE
        WHEN source IN ('akshare.stock_zh_a_hist', 'tencent.fqkline.qfq')
            THEN 'qfq'
        ELSE 'none'
    END
WHERE adjustment_mode = 'unknown'
  AND (
    source IN ('akshare.stock_zh_a_hist', 'tencent.fqkline.qfq')
    OR source LIKE 'akshare.stock_zh_index_daily%'
    OR source LIKE 'sina.cn.index_kline_daily_fallback%'
  )
```

What this shows, and what it does not:

* **A source-string-only assignment path exists in this codebase.** For a row whose `source` at
  execution time is `akshare.stock_zh_a_hist`, and whose `adjustment_mode` is `'unknown'` at that
  moment, this statement would set `'qfq'` on the strength of the source string alone.
* `akshare.stock_zh_a_daily` and `tonghuasun.local.quotes.candle` are **absent from the `WHERE`
  list**, so **this branch, under those inputs, cannot alter such a row**. Revision 1 read that as
  showing those labels "were not assigned by this migration" and so "originated in the writer
  path". **Both halves are withdrawn.** The predicate is evaluated against a row's `source` **at
  execution time**, which need not be its present value; and this is only the migration **as it
  stands now**. An earlier `source` value, a different historical migration text, or another
  writer are all unexcluded.
* **Which text ran, when, and on which rows is not recorded** (L-5). Nothing here establishes that
  this statement ever executed against any retained row, in either direction.

**D-3 — the label is sticky.** `_upsert_bar`'s conflict guard, `daily_bar_cache.py:406-413`:

```sql
WHERE NOT (
    daily_bar_cache.quality_status = 'ready'
    AND daily_bar_cache.adjustment_mode = 'qfq'
    AND (
        excluded.quality_status != 'ready'
        OR excluded.adjustment_mode != 'qfq'
    )
)
```

A row already `ready` + `qfq` is **protected from being replaced** by a later write carrying a
weaker status or label. So a once-assigned `qfq` survives subsequent contradicting writes rather
than being corrected by them.

**D-4 — `updated_at` is a local write clock, not a fetch or response time.**
`daily_bar_cache.py:388` computes `now_str = datetime.now().isoformat(timespec="seconds")` and
`:441` stores it as `updated_at`. So a segment's `updated_at` dates **the write**, on this machine's
clock. It does not date the upstream data, does not identify the code that ran, and is not a
capture pin.

**D-5 — the current source policy is not the historical one.** `config.py:35` gives
`daily_bar_source_policy: str = "tonghuasun_first"`, whose order is
`tonghuasun.local.quotes.candle → akshare.stock_zh_a_daily → tencent.fqkline.qfq →
akshare.stock_zh_a_hist` (`daily_bar_cache.py:170-175`). That is **today's default**. Which policy
was in force for any retained segment is not recorded, and the mixture of sources across the three
symbols is consistent with more than one policy plus fallbacks.

**D-6 — the codebase can demand evidence before labelling `qfq`, and does so elsewhere.** For the
Tencent raw path, `daily_bar_cache.py:682-698` upgrades to `qfq` **only** after an independent
factor check:

```python
frame.attrs["adjustment_mode"] = "qfq"
frame.attrs["source"] = "tencent.fqkline.raw+sina.qfq_factor.unit_verified"
frame.attrs["factor_verification_status"] = "verified"
frame.attrs["factor_evidence"] = factor_evidence
```

No equivalent verification exists for any of the three sources in §3. This shows the pattern is
achievable in this codebase; it is **not** evidence about the retained rows.

**D-7 — the codebase already recognises the distinction, then collapses it.**
`source_comparison.py:139-144` keeps `request_adjustment` and `adjustment_mode` as separate keys —
but when no explicit request value is supplied it does:

```python
out.attrs["request_adjustment"] = _mode(frame.attrs.get("adjustment_mode"))
```

i.e. it treats the stored label as the request. The cache table has **one** column, so the
distinction has nowhere to live once a row is written.

---

## 5. A selection mechanism the current writer path could induce

`daily_bar_cache.py:195, 204-205`:

```python
quality_status = "ready"
...
if adjustment_mode != "qfq":
    quality_status = "review_only_unadjusted"
```

The retained extract's SQL filtered `quality_status = 'ready'`
(`reference_extract.json → rules.filters`, and its `sql` field). **Conditional statement:** *if* a
stock row was written through this branch *and* the writer's `adjustment_mode` were anything other
than `qfq`, the row would carry `review_only_unadjusted` and the extract's filter would exclude it.

**What that does and does not license.** Two facts are directly evidenced: the filter is recorded
in the retained extract, and the uniformity of the label across the extract's stock rows is an
observation about those bytes. What is **not** established is the filter's actual contribution to
that uniformity — because the historical writer path for the retained rows is unbound (L-5), it is
unknown whether this branch produced them, and therefore unknown whether the filter ever excluded
anything for these symbols and spans.

**Revision 1 said the uniformity "is at least partly a property of the extraction filter combined
with this writer branch". That causal attribution is withdrawn.** The correct form is the
conditional above: this is a mechanism the current code **could** produce, not a mechanism shown to
have operated. Equally, nothing here shows the uniformity reflects a genuinely uniform convention.
**Both readings remain open**, and the accepted study's §5.1 remark — that uniformity "removes one
failure mode" — should be read as an observation about the extract rather than as evidence about
the convention. **No numerical result of that study changes.**

**Further bound.** Even as a conditional, this concerns rows written through
`_refresh_stock_symbol`. D-2's path and any other writer could set a label without passing through
lines 204-205.

---

## 6. What the retained provenance actually binds, per segment

Per-row fields in the extract are exactly: `trade_date, close, volume, amount, source,
adjustment_mode, volume_unit, quality_status, updated_at`. The file's `database_fingerprint` adds
only the SQLite file's path, size and mtime.

| Segment | rows | span | Arguments | Response metadata | Code version | Transformation | Stored label | Ingestion / migration history |
|---|---|---|---|---|---|---|---|---|
| SH600011 `stock_zh_a_hist` / `2026-07-15T14:16:19` | 37 | 2024-06-21 … 2024-08-12 | **not recorded** | **not recorded** | **not recorded, and `stock_hist_em.py` is unpinned** | **not recorded** | `qfq` | **not recorded** — writer default *or* D-2 migration |
| SH600011 `stock_zh_a_daily` / `2026-09-03T17:21:19` | 470 | 2024-08-13 … 2026-07-23 | **not recorded** | **not recorded** | not recorded; `stock_zh_a_sina.py` hash known only as a 2026-09-08 check-time observation | **not recorded** | `qfq` | **not recorded** |
| SH600011 `stock_zh_a_daily` / `2026-09-04T15:09:56` | 1 | 2026-07-24 | as above | as above | as above | as above | `qfq` | **not recorded** |
| SH600011 `local.quotes.candle` / `2026-09-04T18:06:09` | 30 | 2026-07-27 … 2026-09-04 | **not recorded** | **not recorded** — including whether the response carried `adjustment` at all | **not recorded** | **not recorded** | `qfq` | **not recorded** |
| BJ920000 `local.quotes.candle` / `2026-09-03T19:39:41` | 470 | 2024-08-13 … 2026-07-23 | as above | as above | as above | as above | `qfq` | **not recorded** |
| BJ920000 `stock_zh_a_daily` / `2026-09-04T15:02:08` | 1 | 2026-07-24 | as above (§3.2) | **not recorded** | as above | **not recorded** | `qfq` | **not recorded** |
| BJ920000 `local.quotes.candle` / `2026-09-04T18:06:31` | 30 | 2026-07-27 … 2026-09-04 | as above | as above | as above | as above | `qfq` | **not recorded** |
| SH000300 `stock_zh_index_daily` × 4 fetch times | 2 / 1 / 475 / 60 | 2024-06-19 … 2026-09-02 | **not recorded** | **not recorded** | **not recorded** | **not recorded** | `none` | **not recorded** |

**The named missing links, precisely.**

* **L-1 — no response metadata.** No field of the retained evidence inspected here records anything
  the upstream response said, for any segment. For `local.quotes.candle` this means the presence or
  absence of the `adjustment` field (§3.3), and its value, are unknown per row. **This is a
  statement about what the retained bytes contain, not about what the responses contained.**
* **L-2 — no invocation arguments.** The `adjust` value actually passed is not stored. It can be
  *inferred* from current code, which is not evidence about a historical call.
* **L-3 — no code-version binding.** No field of the retained evidence inspected here ties a row to
  a provider, cache or AkShare version. `stock_hist_em.py` (`749a94a1…`) is **not pinned in any
  retained artefact this audit read** — which is a statement about the artefacts inspected, not a
  claim that no local file anywhere records it.
* **L-4 — the one available code hash is a check-time observation, not a capture pin.**
  `stock_zh_a_sina.py`'s current hash `a3acc946…` equals
  `basis_records.json → basis_evidence_ref.check_time_observations.adapter_basis_facts.source_sha256`.
  That record labels itself: *"a check-time observation of the installed file, NOT a capture-time
  pin; it is never back-dated"*, `observed_at 2026-09-08T09:22:59Z`. It also concerns the **vendor
  replay** path, not reference ingestion. Equality of a current hash with a later observation of
  the same file says nothing about which bytes ran when a 2026-07-15 or 2026-09-03 row was written.
* **L-5 — no ingestion or migration history.** Nothing in the retained evidence inspected here
  records which writer path, which source policy, or which migration version touched a row, or how
  many times. The table has a `created_at` column (`sqlite_store.py:936`) that the retained extract
  did not select — but §10 explains why **those timestamps could not resolve this link even if
  read**, because D-2 writes neither timestamp and ordinary upserts preserve `created_at` while
  changing `updated_at`.
* **L-6 — candidate origins are indistinguishable in the retained fields.** For `stock_zh_a_hist`,
  the writer default (§3.1) and the source-string migration (D-2) would both yield `qfq` and leave
  identical traces. For the other two sources, D-2's current branch is excluded by its `WHERE`
  list, but an earlier `source` value, another migration text or another writer are not — so no
  segment's origin is determined.
* **L-7 — `updated_at` binds a write, not a fetch.** Per D-4.

**Absence of a link is not evidence for any particular alternative.** None of L-1…L-7 shows that a
mislabelling occurred, that the upstream series was unadjusted, that any upstream response lacked a
basis declaration, or that any specific code path ran. They show that the retained bytes inspected
here do not decide it — in any direction.

---

## 7. Evidence-to-claim matrix

| # | Claim | Direct evidence | Code semantics vs historical evidence | Limitation | Evidence type that would resolve it |
|---|---|---|---|---|---|
| C-1 | In the current path, `stock_zh_a_daily`'s label is computed from the argument we passed | `akshare_provider.py:114`; call site `daily_bar_cache.py:150` | **Code semantics.** Current code; not proof it produced the retained rows | Does not establish what the upstream series actually was | A response field, or a factor series, declaring the convention applied — recorded per row at write time |
| C-2 | In the current path, `get_daily_bars` sets no provider attr and the writer default supplies `qfq` | `akshare_provider.py:66-74` (no `attrs`); `daily_bar_cache.py:148, 194-201` | **Code semantics** | Same, plus L-6: D-2 could equally have stamped it, and no origin is attributed | Per-row provenance recording the writer path and the arguments |
| C-3 | In the current path, `local.quotes.candle`'s label comes from the request name, with a conditional comparison of a response value against the request code | `tonghuasun_provider.py:216-249`, esp. `234-243, 249` | **Code semantics** | **What that response field denotes is undetermined here** — the host contract was not read and is not retained, so the comparison shows neither echo-only semantics nor that no other convention was applied. The check is also conditional on the field's presence, unrecorded per row (L-1) | The host's field contract, plus the original response retained per row, plus an upstream statement of the convention applied |
| C-4 | A startup migration **can** assign `qfq` from the `source` string alone, for a row whose `source` at execution time is `stock_zh_a_hist` | `sqlite_store.py:1976-1991`; DDL `:922-939`; guarded `ALTER` `:1961-1969` | **Code semantics**, and only the *current* migration text (L-5) | Establishes the path exists in this codebase, **not** that it ran on any row, and **not** that any row was ever `'unknown'`. Its `WHERE` list excludes only that branch under those inputs | **A migration or ingestion log, or historically bound before/after evidence.** *Not* `created_at`/`updated_at`: D-2 writes neither timestamp — see §10 |
| C-5 | Once `ready`+`qfq`, a row resists replacement by a weaker-labelled write | `daily_bar_cache.py:406-413` | **Code semantics** | Does not show any such write was attempted | An overwrite/attempt log |
| C-6 | In the current path `updated_at` is written from naive local `datetime.now()`, while `created_at` takes the SQLite `CURRENT_TIMESTAMP` default | `daily_bar_cache.py:388, 391-393, 441`; DDL `sqlite_store.py:936-937` | **Code semantics**, consistent with the retained values' shape | Cannot date the upstream data or the code; and the two columns use **different clock conventions**, so differencing them assumes a common clock they do not share | A recorded fetch timestamp and response identifier, on one stated clock |
| C-7 | **Conditionally:** *if* a stock row came through `:204-205` and its writer label were not `qfq`, the extract's `ready` filter would exclude it | `daily_bar_cache.py:195, 204-205`; extract `rules.filters` / `rules.sql` | **Mixed** — code semantics, plus the filter as a **recorded** property of the extract | The historical writer path is unbound (L-5), so the filter's **actual** contribution to the observed uniformity is not established, in either direction | An unfiltered extract would show which **recorded** labels and quality flags exist for these rows — it would **not** establish a true convention or attribute the uniformity causally |
| C-8 | The retained rows carry no argument, response, code-version or ingestion binding | `reference_extract.json` per-row fields; `database_fingerprint` | **Historical evidence** — a direct property of the retained bytes | None; this is what the file contains | Not a limitation to resolve — it is the finding |
| C-9 | `stock_zh_a_sina.py`'s hash appears in the retained record only as a 2026-09-08 check-time observation; `stock_hist_em.py` appears in no retained artefact read here | `basis_records.json` `check_time_observations`; §1 hash table | **Historical evidence about the record**, not about the rows | No pin in the inspected evidence binds either module to a retained reference row; this audit did not exhaust every local artefact | Capture-time code pins written alongside each ingested batch |
| C-10 | The index label `none` is agreed by two code paths | `daily_bar_cache.py:927`; `sqlite_store.py:1982` `ELSE 'none'` | **Code semantics** | Per U-7, irrelevant to a stock's basis | — (out of scope by direction) |
| C-11 | The codebase can gate a `qfq` label on independent factor evidence | `daily_bar_cache.py:682-698` | **Code semantics** | Not applied to any of the three sources; no evidence about retained rows | — (it is the model, not the evidence) |

---

## 8. What this settles about Q-3, and what it does not

**Directly evidenced properties of the retained bytes.**

1. **No independently verified basis declaration is retained for any of these reference rows.**
   Per-row provenance is a source string, a label, a unit, a quality flag and a write timestamp
   (§6). This is a statement about what the retained evidence contains — **not** a finding that the
   upstream responses declared nothing.
2. **The per-segment binding is empty in every dimension that matters** (§6): arguments, response
   metadata, code version, transformation and ingestion history are all unrecorded in the evidence
   inspected here.
3. **Condition 4 cannot be satisfied from this record**, and now for an identified reason: no
   inspected artefact carries the needed statement, and none of the fields that exist could carry
   it. That is a property of the retained schema, not of a search that stopped early.
4. **The label's uniformity across the extract's stock rows is a real observation** about those
   bytes. Its cause is **not** established (§5).

**Current-code conditionals — true of the inspected code, not of any retained row.**

5. In each inspected stock path the label is assigned from a request argument or a hard-coded
   writer default (§§3.1–3.3), and for one source a startup migration could assign it from the
   `source` string alone (D-2). **So the reference leg's label is produced by the same *kind* of
   construction the P1 proposal identified at `akshare_provider.py:114`** — a statement about code
   shape, not about which path ran.
6. **No segment's origin is attributed.** Revision 1 concluded that the `stock_zh_a_daily` and
   `local.quotes.candle` labels "were not produced" by D-2 and so came from the writer path. **That
   is withdrawn.** D-2's `WHERE` list excludes only that branch, evaluated against a row's `source`
   at execution time; an earlier `source` value, a different historical migration text and another
   writer all remain unexcluded (L-6).

**Not established, and not to be read into the above.**

* **No mislabelling is asserted.** Nothing here shows any reference row is wrongly labelled, that
  its upstream series was unadjusted, or that any convention differed from the label.
* **No upstream response semantics are asserted.** Nothing here shows what any response did or did
  not declare, nor what the Tonghuashun `adjustment` field denotes — its contract was not read and
  is not retained.
* **No historical execution is asserted.** Neither the `ALTER TABLE` (D-1) nor the D-2 `UPDATE` is
  shown to have run against any retained row, and no writer path is shown to have produced one.
* **No reference basis is certified, in either direction.** Condition 4 stays unsatisfied; it is
  not converted into a finding that the label is false.
* **Current code is not proof of the historical path.** Every C-1…C-7 row is current-code semantics.
  The worktree's `sqlite_store.py` even differs from `HEAD` today, which is a live demonstration of
  why a file's present contents cannot stand in for what ran months ago.
* **The accepted numerical study is untouched.** Its 14 interval outcomes, seven conditional step
  comparisons, six identified in-interval comparisons with five exact matches and E-1 discrepant,
  and its certification-withheld conclusion all stand. This audit explains *why* the reference leg
  cannot close Q-3; it does not re-open or re-decide anything numerical.
* **U-6 is not closed by inference**, no threshold or label is defined, and the P1 proposal is
  unchanged.

**Net effect on the decision.** The readiness assessment withheld certification chiefly because the
reference basis is recorded but not independently established. That reason is now **sharper in a
specific way**: the inspected record contains no field capable of carrying such an establishment,
and in current code the label is produced from a request argument or a default rather than from any
verified declaration. **What is still not known is which path produced any retained label, and what
the upstream responses said.** The conclusion is unchanged — `vendor_basis` stays `unverified`,
**fail-closed rather than disproved**.

---

## 9. Preservation

**Created:** `claude methods/M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md` only. **Modified:** nothing.

Verified after the audit: the accepted G1 delivery is **46/46 byte-identical** to the frozen
`_m2_codex_review/g1_review_20260909_r3_doc1/reviewed_delivery`, no file added or removed; the five
accepted G3 r2 pins match; `reference_extract.json` `ea021004…` is unchanged after reading; the
basis module, its tests and both `basis_eval_*` outputs match; the five smoke producers and
`closure_r2abc_v2.py` match; the retained study `65fbe917…`, the readiness assessment `de130cf0…`,
the P1 proposal `71e0dc52…`, goal `f8b699e5…`, request `c39726d0…`, all G1/G3/U-6 acceptance and
review documents, this task's dispatch `1cb6443f…`, all reviewer snapshots and the coordination
state are unchanged. **All six project source files and both AkShare files were read as text and are
unchanged**, including the user's uncommitted `sqlite_store.py` edit, which was left exactly as
found. No SQLite open, provider call, service-initializing import, decoder, replay, network call,
capture or extract. No scratch script or output directory. Git was not staged, committed or pushed;
HEAD remains `73f266d` with an empty index.

---

## 10. What would and would not resolve the open links

**Revision 1's proposal is withdrawn as stated.** It recommended an unfiltered, column-complete
re-extract and presented `created_at` versus `updated_at` as discriminating a writer path from a
bulk migration stamp. **Those timestamps cannot do that**, for four reasons visible in the code
read here:

* **D-2 writes neither timestamp.** `sqlite_store.py:1978-1989` sets `adjustment_mode` only, so a
  label assigned by that statement leaves **no timestamp trace at all**.
* **Ordinary upserts already produce an old `created_at` with a new `updated_at`.**
  `daily_bar_cache.py:391-393` omits `created_at` from the INSERT column list, and `:394-405` omits
  it from the `DO UPDATE SET` list — so it takes the DDL default on insert and is **preserved** on
  every later update. So an ordinary re-write **can produce** a large gap between the two — which
  means observing such a gap identifies neither that re-write nor a migration, and rules out
  neither.
* **Bulk ordinary insertion yields identical timestamps** across many rows, with no migration
  involved.
* **The two columns use different clock conventions.** `created_at` defaults to SQLite
  `CURRENT_TIMESTAMP` (`sqlite_store.py:936`); `updated_at` receives naive local
  `datetime.now().isoformat(timespec="seconds")` (`daily_bar_cache.py:388`). Subtracting them
  assumes a common clock and timezone that they do not share. No database was opened, so their
  actual stored semantics here are unverified in any case.

**So L-5 and L-6 are not resolvable by timestamps.** The discriminating evidence type is a
**migration or ingestion log**, or **historically bound before/after evidence** — a record, written
at the time, of which statement or writer touched which rows. No such record exists in the
inspected evidence, and none can be manufactured from the columns that do.

**What an unfiltered extract could and could not do.** It could reveal rows the `ready` filter
excluded, together with their **recorded** labels and quality flags — a bounded descriptive
observation bearing on C-7. It could **not** establish whether the true convention was uniform, and
could **not** causally attribute the observed uniformity to filtering. Revision 1 framed it as
deciding between "the convention was uniform" and "the filter only admitted one label"; **that
dichotomy is false** and is withdrawn. **No re-extract is requested or performed here**, and any
such access would need its own authorization, which does not exist.

**What would actually resolve C-1 to C-3.** An upstream artefact stating the convention applied —
a response field, a factor series, or a documented host contract — **recorded per row at write
time**. That historically bound evidence is **absent from the artefacts inspected here** and
**cannot be reconstructed from the selected row fields alone**; it must **not** be presumed absent
from every uninspected local file, since this audit did not exhaust them. Recording it going
forward is a change to what future ingestion writes. It is named as the resolving evidence type,
not proposed as work.

**Not worth doing.** Further price-relation modelling on the same intervals; the accepted study's
own acceptance says not to keep fitting relation families to the same evidence.

**Not executed here.** The dispatch and this review both exclude the other-writer inventory and the
non-price study; neither was performed, and neither is requested.

**Stop: `proposed for review`.** This audit certifies nothing, adopts nothing, and authorizes
nothing.
