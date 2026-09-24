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
> **The one-sentence result.** For all three stock reference sources the stored `adjustment_mode`
> traces to a **request argument or a hard-coded writer default** — for one source, possibly to a
> **startup migration that reads the `source` string alone** — and in no case to a response
> declaration of the price convention actually applied; the retained rows carry **no** binding to
> arguments, response metadata, code version or ingestion history, so **Q-3 remains open, and is
> now open for identified reasons rather than unexamined ones**.

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
| `backend/.venv/Lib/site-packages/akshare/stock_feature/stock_hist_em.py` | `749a94a192bcd79ee76867fb8dfc7c563613cf08afb1dd72ca5a97c471bcd3d8` | **no — not pinned anywhere in the retained evidence** |

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

**A second possible origin for this source only.** §4's startup migration assigns
`adjustment_mode = 'qfq'` to any row still `'unknown'` **whose `source` string is
`akshare.stock_zh_a_hist`**. So this segment's label could equally have been written by the default
above **or** stamped later from the source string alone. **The retained evidence cannot distinguish
the two** (see L-6).

**Origin: (a) request argument + (c) writer default, and possibly (d) migration. Not (b).**

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

**Origin: (a) request argument, adopted by (c). Not (b), not (d).**

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

**This is the strongest of the three, and it is still not (b).** Two limits, both in the code:

1. The check is **conditional** — `if echoed_adjustment is not None`. When the field is absent no
   verification happens, and line 249 still labels the frame from the **request name**.
2. When present, the check compares an **integer echo of the request code** against the code we
   sent. That evidences *which mode the host was asked for* and that it did not silently
   substitute another; it is **not a declaration of the price convention the host actually
   applied**, and it carries no factor, divisor or reference date.

Whether the field was present for the retained rows is **not recorded anywhere in the retained
evidence** — the extract keeps no response metadata (L-1).

**Origin: (a) request argument, with a conditional request-echo consistency check; adopted by (c).
Not a convention declaration.**

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

The column was **added by migration** with default `'unknown'`, so every row that existed before
that migration became `'unknown'` and was eligible for D-2.

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

Two consequences, and one limit worth stating plainly:

* `akshare.stock_zh_a_hist` **is** in the list — so §3.1's segment has a second candidate origin.
* `akshare.stock_zh_a_daily` and `tonghuasun.local.quotes.candle` are **not** in the list — so
  §3.2's and §3.3's labels were **not** assigned by this migration; their origin is the writer path.
* This is the migration **as it stands now**. Which migration text ran when each retained row was
  written is **not recorded** (L-5). Its presence establishes that a source-string-only assignment
  path exists in this codebase, not that it executed on any particular row.

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

## 5. A selection effect the retained extract inherits

`daily_bar_cache.py:195, 204-205`:

```python
quality_status = "ready"
...
if adjustment_mode != "qfq":
    quality_status = "review_only_unadjusted"
```

The retained extract's SQL filtered `quality_status = 'ready'`
(`reference_extract.json → rules.filters`, and its `sql` field). **On this writer path, a stock row
whose label was anything other than `qfq` would carry `review_only_unadjusted` and therefore could
not appear in the extract at all.**

This qualifies a sentence I wrote in the accepted study. §5.1 there reports the label is
"internally uniform per symbol" and calls that "one failure mode removed". The uniformity is
**real as an observation about the extract**, but it is **at least partly a property of the
extraction filter combined with this writer branch** — not independent evidence that one
convention was applied throughout. **No numerical result of that study changes**; only that
interpretive remark is narrowed. The study's own §5.1 already declined to infer anything about the
label's reliability, and this audit does not reverse that in the other direction either.

**Bound on this finding.** It applies to rows written through `_refresh_stock_symbol`. D-2's
migration path and any other writer could set a label without passing through lines 204-205, and
whether every retained row came through that path is **not recorded** (L-5).

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

* **L-1 — no response metadata.** No retained field records anything the upstream response said,
  for any segment. For `local.quotes.candle` this specifically means the presence or absence of the
  `adjustment` echo field (§3.3) is unknown per row.
* **L-2 — no invocation arguments.** The `adjust` value actually passed is not stored. It can be
  *inferred* from current code, which is not evidence about a historical call.
* **L-3 — no code-version binding.** No retained field ties a row to a provider, cache or AkShare
  version. `stock_hist_em.py` (`749a94a1…`) is **not pinned in the retained evidence at all**.
* **L-4 — the one available code hash is a check-time observation, not a capture pin.**
  `stock_zh_a_sina.py`'s current hash `a3acc946…` equals
  `basis_records.json → basis_evidence_ref.check_time_observations.adapter_basis_facts.source_sha256`.
  That record labels itself: *"a check-time observation of the installed file, NOT a capture-time
  pin; it is never back-dated"*, `observed_at 2026-09-08T09:22:59Z`. It also concerns the **vendor
  replay** path, not reference ingestion. Equality of a current hash with a later observation of
  the same file says nothing about which bytes ran when a 2026-07-15 or 2026-09-03 row was written.
* **L-5 — no ingestion or migration history.** Nothing records which writer path, which source
  policy, or which migration version touched a row, or how many times. The table **does** have a
  `created_at` column (`sqlite_store.py:936`), and **the retained extract did not select it** — see
  §10.
* **L-6 — for `stock_zh_a_hist`, two origins are indistinguishable.** Writer default (§3.1) and
  source-string migration (D-2) both produce `qfq` and leave identical traces in the retained
  fields.
* **L-7 — `updated_at` binds a write, not a fetch.** Per D-4.

**Absence of a link is not evidence for any particular alternative.** None of L-1…L-7 shows that a
mislabelling occurred, that the upstream series was unadjusted, or that any specific path ran. They
show that the retained bytes do not decide it.

---

## 7. Evidence-to-claim matrix

| # | Claim | Direct evidence | Code semantics vs historical evidence | Limitation | Evidence type that would resolve it |
|---|---|---|---|---|---|
| C-1 | For `stock_zh_a_daily`, the stored label is computed from the argument we passed | `akshare_provider.py:114`; call site `daily_bar_cache.py:150` | **Code semantics.** Current code; not proof it produced the retained rows | Does not establish what the upstream series actually was | A response field, or a factor series, declaring the convention applied — recorded per row at write time |
| C-2 | For `stock_zh_a_hist`, no provider attr is set and the writer default supplies `qfq` | `akshare_provider.py:66-74` (no `attrs`); `daily_bar_cache.py:148, 194-201` | **Code semantics** | Same, plus L-6: D-2 could equally have stamped it | Per-row provenance recording the writer path and the arguments |
| C-3 | For `local.quotes.candle`, the label comes from the request name; the response echo, when present, verifies only the requested code | `tonghuasun_provider.py:216-249`, esp. `234-243, 249` | **Code semantics** | An echo is not a convention declaration; and the check is conditional on the field's presence, which is unrecorded per row (L-1) | Recording the echoed value per row, plus an upstream statement of the convention (not just the requested mode) |
| C-4 | A startup migration can assign `qfq` from the `source` string alone, for `stock_zh_a_hist` | `sqlite_store.py:1976-1991`; column default `:933, :1962` | **Code semantics**, and only the *current* migration text (L-5) | Establishes the path exists, not that it ran on any row | Migration/ingestion audit rows, or `created_at` versus `updated_at` per row |
| C-5 | Once `ready`+`qfq`, a row resists replacement by a weaker-labelled write | `daily_bar_cache.py:406-413` | **Code semantics** | Does not show any such write was attempted | An overwrite/attempt log |
| C-6 | `updated_at` is the local write time | `daily_bar_cache.py:388, 441` | **Code semantics**, and it matches the retained values' shape | Cannot date the upstream data or the code | A recorded fetch timestamp and response identifier |
| C-7 | The extract's `ready` filter plus `:204-205` mean a non-`qfq` stock row could not appear | `daily_bar_cache.py:195, 204-205`; extract `rules.filters` / `rules.sql` | **Mixed** — code semantics plus a **recorded** property of the retained extract | Applies to that writer path only; other paths unverified (L-5) | An unfiltered extract over the same rows, showing what `quality_status` values exist |
| C-8 | The retained rows carry no argument, response, code-version or ingestion binding | `reference_extract.json` per-row fields; `database_fingerprint` | **Historical evidence** — a direct property of the retained bytes | None; this is what the file contains | Not a limitation to resolve — it is the finding |
| C-9 | `stock_zh_a_sina.py`'s hash is known only as a 2026-09-08 check-time observation; `stock_hist_em.py` is unpinned | `basis_records.json` `check_time_observations`; §1 hash table | **Historical evidence about the record**, not about the rows | No pin binds either module to a retained reference row | Capture-time code pins written alongside each ingested batch |
| C-10 | The index label `none` is agreed by two code paths | `daily_bar_cache.py:927`; `sqlite_store.py:1982` `ELSE 'none'` | **Code semantics** | Per U-7, irrelevant to a stock's basis | — (out of scope by direction) |
| C-11 | The codebase can gate a `qfq` label on independent factor evidence | `daily_bar_cache.py:682-698` | **Code semantics** | Not applied to any of the three sources; no evidence about retained rows | — (it is the model, not the evidence) |

---

## 8. What this settles about Q-3, and what it does not

**Newly established, from these bytes.**

1. **No reference source declares its basis.** In all three stock pipelines the stored label derives
   from a request argument, a hard-coded writer default, or a source-string migration. **The
   reference leg's label has the same evidential character as the vendor leg's** — the construction
   the P1 proposal identified at `akshare_provider.py:114` and set out to close.
2. **Condition 4 cannot be satisfied from the current record**, and now for an identified reason:
   there is no artefact that could carry the needed statement. This is a property of the retained
   schema and code, not of a search that has not gone far enough.
3. **The per-segment binding is empty in every dimension that matters** (§6): arguments, response
   metadata, code version, transformation and ingestion history are all unrecorded. Only a source
   string, a label, a quality flag and a **write** timestamp exist.
4. **The label's observed uniformity is partly a selection effect** of the extract's `ready` filter
   (§5), which narrows an interpretive remark in the accepted study without changing any of its 14
   interval outcomes or seven step comparisons.
5. **One prior unknown is now bounded rather than open-ended.** `akshare.stock_zh_a_daily` and
   `tonghuasun.local.quotes.candle` labels were **not** produced by D-2's migration — that path
   excludes them by its own `WHERE` clause. Only `stock_zh_a_hist` retains the two-origin ambiguity
   (L-6).

**Not established, and not to be read into the above.**

* **No mislabelling is asserted.** Nothing here shows any reference row is wrongly labelled, that
  its upstream series was unadjusted, or that any convention differed from the label.
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
reference basis is recorded but not independently established. That reason is now **sharper**: the
record contains no artefact capable of establishing it, and the label's provenance runs back to our
own request or a default. **The conclusion is unchanged — `vendor_basis` stays `unverified`,
fail-closed rather than disproved.**

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

## 10. Next useful offline task

**Candidate — an unfiltered, column-complete re-extract of the same rows, if and when a read-only
database open is authorized.** This is a **recommendation only**; it needs an authorization that
does not exist and is **not requested here**. Its value is specific and follows directly from §6:

* `daily_bar_cache` carries a **`created_at`** column (`sqlite_store.py:936`) that the retained
  extract **did not select**. `created_at` versus `updated_at` per row would bear directly on L-5
  and L-6 — a row first written long before its `updated_at`, or created at the same instant as
  many others, discriminates between the writer path and a bulk migration stamp.
* Dropping the `quality_status = 'ready'` filter would test C-7 directly: it would show whether
  any `review_only_unadjusted` rows exist for these symbols and spans, which is the difference
  between "the convention was uniform" and "the filter only admitted one label".

Both are **read-only, single-query** questions about rows already in scope. Neither certifies a
basis; both convert an unrecorded link into a recorded observation.

**Available now, with no new authorization, but lower value.** A static trace of the *other*
writers that can reach `daily_bar_cache` — `universe_backfill.py`, `snapshot_builder.py`,
`phase_replay.py` and `market_history.py` all reference `adjustment_mode` — to enumerate every code
path that can set or preserve the label. It would extend §4's inventory and could narrow L-5's
"which writer path" question from the code side. It would remain current-code semantics and would
not bind any retained row.

**Not worth doing.** Further price-relation modelling on the same intervals; the accepted study's
own acceptance says not to keep fitting relation families to the same evidence. And no static audit
can substitute for an upstream artefact that states the convention applied — which is the one
evidence type §7 names for C-1, C-2 and C-3, and which no local file can supply.

**Stop: `proposed for review`.** This audit certifies nothing, adopts nothing, and authorizes
nothing.
