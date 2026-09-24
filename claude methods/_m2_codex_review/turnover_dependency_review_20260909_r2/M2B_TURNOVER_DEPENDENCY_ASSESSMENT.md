# M2b — turnover dependency assessment: what actually consumes what

> **Status: `proposed for review`.** Static, existing-file offline analysis under the
> user's continuing offline authorization. **Nothing is adopted.** No policy, threshold,
> metric definition, label, gate or eligibility is changed or proposed for adoption here;
> the used / annotated / withheld options in §8 are stated **as alternatives only**.
>
> **Nothing was executed.** No SQLite open of any kind (including `:memory:`), no provider,
> service, score engine, strategy or database helper imported or called, no network, no
> capture, no replay, no decoder run, no migration or importer run, no dataset, fixture or
> demo-seed file opened, no credential or token file read, no test run, no scratch script,
> no output directory, no Git action. Everything below is read from **current source text**
> and **already-retained JSON/documents**, quoted with exact line references.
>
> Task `TURNOVER-DEPENDENCY-20260909`, dispatched by
> `_m2_codex_review/turnover_dependency_dispatch_20260909.txt`
> (`e2042b58cb2c6549b395d1a69c129ff863a837c1202a7ef7a34b3afd9efab2cd`). Date: 2026-09-09.
> Revision 2 — TD-R1 through TD-R3 of `M2B_TURNOVER_DEPENDENCY_CODEX_REVIEW.md` closed in one
> consolidated correction; see the revision record at §12.
>
> **Standing position, unchanged by this document: P1 open · U-6 deferred · every
> eligibility false · M2b source capability FAIL, including the retained `EV6` · both
> boundary-1b capture authorizations consumed.** Nothing here bears on any of them, and
> §8 states explicitly that excluding turnover would close none of them.

---

## 1. The question this answers

`M2B_NEXT_STAGE_DECISION_MEMO.md` (`536505ea4a29e506dadf3c510eab67dc8d52a84706f2288c85690af64aea0d4a`)
leaves one item open in two places:

* **§2.2, point 3** — *"Whether turnover is used, used with a staleness annotation, or not
  used is a design decision for the next stage. No expiry threshold, metric change or
  discard decision is proposed or made in this memo."*
* **§4, recommended next work, item 2** — *"Decide the downstream policy for turnover given
  §2.2 — used, annotated, or not used — without changing any metric definition here."*

A policy question of that form presupposes that something downstream **consumes** the
measure. This document tests that presupposition instead of assuming it. The result, stated
up front and then evidenced:

> **The M2 smoke work retains no turnover *rate series*: `U4` emits denominator
> diagnostics, not per-session rates (§3.3), and the one place a turnover column is
> actually computed — inside the installed adapter during the `R1` replay — has only its
> *column name* retained, never its values (§3.6). And within the searched trees
> (§7, §11), no file in `backend/` reads any M2 smoke output.** Every live consumer of a
> field spelled `turnover*` that this search reached consumes **one of three other
> quantities**, none of which is the retained-derived measure and two of which are not
> rates at all.

Both halves of that are **bounded claims about what was searched and what is retained**,
not universal negatives; §11 limits 1–2 state the bounds, and §7 restates them at the point
of use. That shape of result still changes the decision, and §8 separates the two
consequences the dispatch asks to be kept apart: consequences for an **as-yet-unwired**
smoke result, and consequences for the **existing quote and legacy** metrics that are wired.

---

## 2. Five different quantities share the name — and only one is at issue

Name identity is not linkage. These are distinguished throughout this document, and the
evidence for each separation is in the section named. **The table describes what the
searches of §11 reached; it is not a claim that the repository contains nothing else.**

| # | Quantity | Spelling in code | Units | Where it lives | § |
|---|---|---|---|---|---|
| **T1** | **Turnover *rate*, retained-derived** — traded volume against an outstanding-share denominator, from the M2 smoke auxiliary series | *no field name — no rate series emitted* | **undefined** — no scaling is ever applied, so it has neither a fraction nor a percent convention | `claude methods/_m2_smoke/` only | §3 |
| **T2** | **Turnover *rate*, adapter-computed** — AkShare's `turnover` column on `stock_zh_a_daily` | `turnover` | **fraction** (not percent) | computed inside the AkShare library — including during the smoke's own `R1` replay (§3.6) — and **dropped at `akshare_provider.py:110`** before it reaches project storage | §4 |
| **T3** | **Turnover *rate*, quote-provided** — the vendor's 换手率 in a market-wide spot snapshot | `turnover_rate` | **percent** *by the consuming code's own convention* (§5.2) — the vendor's unit is not independently verified here | `auto_discovered_candidates`, `potential_search_items`, `agent_learning_samples` | §5 |
| **T4** | **Turnover *amount*** — 成交额, money, not a rate at all | `turnover` (as a column **alias for `amount`**), `turnover_text`, and one comment | **currency** (yuan; one source in 万元) | `daily_bar_cache` column resolution, `trade_records`, `backtest/engine.py` | §6 |
| **T5** | **A share count that is *not* a turnover field** — `total_share_billion`, derived as market cap ÷ price | `total_share_billion`, `float_cap_billion` | 亿股 / 亿元 | `symbol_fundamental_snapshot`, resolved by `FundamentalResolver` | §6.5 |

A sixth candidate — **portfolio turnover** (rebalancing churn, position turnover, turnover
cost) — **was not found by the searches described in §6.4 and §11**, which is a bounded
negative, not a proof of non-existence.

**The memo's open question is about T1 alone.** T2–T5 are pre-existing and are touched by
this document only to say what they are and where they go. T5 in particular is included
because it disproves a broader claim an earlier draft of this document made (§6.5), not
because it is a turnover measure — it is not.

---

## 3. T1 — the retained-derived measure, traced exactly

### 3.1 What is retained, and what is not

Producer pins (the five frozen producers named in the memo's §1; the two relevant here):

| File | sha256 |
|---|---|
| `claude methods/_m2_smoke/sina_klc_decoder.py` | `c6d736b170c29009ef273ed7705330f2a251545bca720d55c998d0a715f83fc8` |
| `claude methods/_m2_smoke/smoke_checks.py` | `4b062a55fae6f9bd348a7ffdf20073debababffafc71568e2aaaf8181c832bbe` |
| `claude methods/_m2_smoke/smoke_capture.py` | `059d0c43547db0bf520afc9c034dbc5c1638b3beb12c77e35e62ace03f85ad35` |
| `…/revision_20260908T082833Z_r2abc_v2/checks.json` | `b6c97eab21254b837f3bd1768eec22c8a54ec925da82beb0f12810156f42d387` |
| `…/revision_20260908T082833Z_r2abc_v2/PROVENANCE.json` | `204b6501819333d9723547be7e89e14a1d3c19add484d8d0bb07276b9dbecf5e` |

The accepted revision directory `revision_20260908T082833Z_r2abc_v2/` contains exactly
`PROVENANCE.json`, `REPORT.md`, `capture_manifest.json`, `checks.json`, `raw/` (five bodies)
and `reference/reference_extract.json`. **There is no `decoded/` directory** — the
`decoded/<symbol>_outstanding_share.csv` artefact contemplated by
`M2B_REAL_SOURCE_VERIFICATION_REQUEST.md:132` was not produced in this revision. So the
share series exists in retained form only as the **raw JSONP bodies**
(`raw/02_sh600011_getAmountBySymbol.bin`, `raw/05_bj920000_getAmountBySymbol.bin`) and as
**summary statistics inside `checks.json`**.

### 3.2 The denominator: what it is, in what unit, and how it is resolved in time

The auxiliary endpoint returns a series the **vendor labels `amount`**, which is not traded
amount. `sina_klc_decoder.py:354-357`:

```python
#: The vendor reports this series in 万股. `stock_zh_a_sina.py:207` multiplies it by
#: 10,000 to obtain shares and `:208` divides volume by the result to get turnover. It is
#: NEVER traded amount, whatever the vendor calls the JSON field.
OUTSTANDING_SHARE_WAN_TO_SHARES = 10_000
```

**Denominator type, as supported by the retained bytes.** The series is the vendor's
outstanding-share count in **万股** (`wan` shares; ×10,000 → shares). The decoder renames
the field at the boundary — `parse_outstanding_share` (`:400`) emits
`{"date", "outstanding_share_wan", "usable", "unusable_reason"}` at `:479-482` — precisely
so the vendor's `amount` key cannot be mistaken for money downstream
(`M2B_REAL_SOURCE_VERIFICATION_REQUEST.md:92`, G3).

**What the retained bytes do *not* establish about the denominator.** The vendor supplies a
count and a date and nothing else. Whether it is **total** shares, **free-float**
(流通股), or A-share-only is **not declared in the payload and not established here**. The
AkShare column name is `outstanding_share` (`stock_zh_a_sina.py:199`), which is the
adapter's word, not the vendor's. **No corporate-action fact, share-count definition or
replacement value is inferred or invented in this document.**

**Temporal resolution: an explicit step-function rule, with a fail-closed interruption.**

* `share_state_as_of(rows, date)` (`sina_klc_decoder.py:487`) returns the **latest
  observation at or before** the date — *"Never looks forward."*
* `outstanding_share_as_of(rows, date)` (`:502`) returns that state **only if it is
  usable**. Its docstring states the rule that was corrected and validated as R2-ABC-C1:
  *"If that observation is explicitly unusable — the vendor reported zero — there is **no
  usable denominator until a later valid observation supersedes it**: an older positive
  count must not be restored across a newer invalid one. This matches the installed
  adapter's `ffill`, which carries an explicit zero forward as zero
  (`[100, 0, NaN, 200].ffill()` is `[100, 0, 0, 200]`, not `[100, 100, 100, 200]`)."*
* **Never backfills**: a date before the first observation returns `None` rather than
  borrowing a later count (`:514-516`).
* A **negative** count is refused as a decode error (`:476-478`); a **zero** is kept,
  flagged `usable: False`, reported, and withheld as a denominator — *"never dropped and
  never repaired"* (`:420-424`, `:479-482`).
* `invalid_denominator_intervals` (`:524`) reports every span in which an unusable
  observation is in force, `until` being the later valid observation or `None` if the
  series ends unusable.

**This accepted zero-denominator interruption behaviour is preserved exactly as it stands
and is not modified, relaxed or re-specified anywhere in this document.**

### 3.3 What `U4` actually computes — and what it does not

This is the point on which the memo's phrasing is easy to over-read. `smoke_checks.py`
`U4` (`:1179-1219`) does **not** compute a turnover rate. It evaluates a **bound
predicate** and reports **counts and ages**:

```python
# smoke_checks.py:1179-1195
for r in research:
    if r.get("volume") is None:
        continue
    asof = dec.outstanding_share_as_of(share_series, r["date"])
    if asof is None:
        state = dec.share_state_as_of(share_series, r["date"])
        if state is None:
            before_series += 1          # no observation exists yet
        else:
            under_invalid += 1          # an explicit zero is in force
        continue
    aligned.append((r["date"], float(r["volume"]), asof["outstanding_share_wan"]))
    ages.append(dec._age_days(asof, r["date"]))
```
```python
# smoke_checks.py:1197
exceeded = [d for d, vol, wan in aligned if vol > wan * 10000.0]
```

Consequences, each of which matters to the decision in §8:

1. **No ratio is ever formed.** `volume / (outstanding_share_wan × 10,000)` is never
   evaluated. Only the inequality `volume > wan × 10000.0` is.
2. **No percentage scaling exists.** There is no `× 100` anywhere on this path. The design
   intent is stated in the request at `:202`: *"`volume ≤ outstanding_share_wan × 10,000`
   for that same date (turnover cannot exceed 100%)"* — that is the **threshold's meaning**,
   not a computed percentage.
3. **`U4` emits no turnover field.** (For the one place in the smoke where a turnover
   *column* is genuinely computed — inside the adapter, during the `R1` replay — see §3.6;
   only the column name survives there, never a value.) The `measured` block written to
   `checks.json` (`smoke_checks.py:1210-1218`) contains `aligned_rows`,
   `rows_without_applicable_share`, `rows_before_the_first_observation`,
   `rows_under_an_invalid_observation`, `invalid_denominator_intervals`,
   `denominator_age_days_median`, `denominator_age_days_max` and `exceeding` — **no rate**.
4. **Missing-value behaviour is explicit and split two ways, and it is a skip, not a
   default.** A row with `volume is None` is skipped; a row with no usable denominator is
   skipped and counted, separately by reason (`before_series` vs `under_invalid`). Nothing
   is imputed, defaulted to zero, or carried across an invalid observation.
5. **`U4` is `kind="advisory"`** (`:1219`), so it can never contribute a required-check FAIL
   under the Layer-3 precedence in the memo's Annex A.

Where the auxiliary series is absent altogether, `U4` is emitted as ADVISORY *"not computable
without the outstanding-share series"* (`smoke_checks.py:1157-1159`) and `D5` is
INCONCLUSIVE — **missing auxiliary evidence, explicitly not history evidence**
(`:1151`).

### 3.4 The retained observations, and one qualification the memo does not draw

From `checks.json` (`b6c97eab…`), verbatim `measured` values:

| | `sh600011` | `bj920000` |
|---|---|---|
| `aligned_rows` | 728 | 728 |
| `rows_without_applicable_share` | 0 | 0 |
| `rows_before_the_first_observation` | 0 | 0 |
| `rows_under_an_invalid_observation` | 0 | 0 |
| `exceeding` | `[]` | `[]` |
| `denominator_age_days_median` | 1,975 | 173 |
| `denominator_age_days_max` | 2,516 | 511 |
| `invalid_denominator_intervals` | `[]` | `2015-03-06 → 2015-10-27`, `2015-09-15 → 2015-10-27` |
| status | ADVISORY | ADVISORY |

**The qualification.** The research window is `RESEARCH_START, RESEARCH_END =
"2023-09-04", "2026-09-04"` (`smoke_capture.py:125`); `research` is selected by
`smoke_checks.py:1131`. `BJ920000`'s two zero observations are from **2015** — more than
eight years before the window opens. So the interruption rule of §3.2 is **implemented,
tested and reported, but was not exercised on a single one of the 728 retained research
rows**: `rows_under_an_invalid_observation` is 0 for that reason, not because the rule found
nothing to do. The rule's correctness rests on the synthetic C1 cases recorded in the
request (`:1816-1841`), not on the retained window.

**What long carry-in age does and does not show.** Following the memo's §2.2 exactly and
adding nothing: a median of 1,975 and a maximum of 2,516 days for `SH600011` means every
in-window row resolves to the observation of **2019-10-15**, the last entry in the series.
This is a **change-event** series, so the absence of a newer entry is **not** evidence that
the carried count is wrong, and it is **not** evidence that the series is incomplete or
stale at the source. It is a reason for uncertainty. **No expiry threshold is proposed,
implied or needed to state that.** Equally, it cannot be asserted that a future fetch would
return the same 26 entries.

### 3.5 Provenance limits on T1

* The measure is **derived from two different requests** — the klc history body supplies
  `volume`, the auxiliary body supplies the denominator — joined by date at check time.
* **`U4` is ADVISORY, not a PASS.** As the memo says, it *"is not a PASS certifying turnover
  for downstream use"*, and nothing here upgrades it.
* Both retained captures' capability verdict is **FAIL**, capped by the historical `EV6`
  (memo §3.3). Any T1 quantity therefore inherits an input whose **source capability is not
  accepted**.
* **`n = 1`**: one complete observation, at one instant, on one trading day.
* The **denominator definition is undeclared** by the vendor (§3.2).

### 3.6 One place in the smoke *does* compute a turnover column — the `R1` adapter replay

This qualifies §3.3 and must not be collapsed into it. `smoke_checks.adapter_replay`
(`:288-330`) calls **the installed AkShare function itself** on the captured bytes, with
remote connections blocked and both adapter modules' `requests` handle swapped:

```python
# smoke_checks.py:316-322
function = getattr(modules[module_key], func_name)
frame = function(*args)
...
results[label] = {"rows": …, "first_date": …, "last_date": …, "dates": dates,
                  "columns": [str(c) for c in frame.columns]}
```

Because that is AkShare's own `stock_zh_a_daily`, the frame it returns **does** carry the
`turnover` and `outstanding_share` columns computed at `stock_zh_a_sina.py:207-208` (§4).
The retained `R1` result records exactly that and nothing more —
`checks.json` for **both** stocks, verbatim:

```
"rows": 978, "first_date": "2022-08-24", "last_date": "2026-09-04",
"columns": ["date","open","high","low","close","volume","amount",
            "outstanding_share","turnover"]
```

**What this establishes and what it does not.** It establishes that a replay frame with
those columns existed in memory during the replay, and that `R1` PASSed on row count,
window and date sequence. It establishes **nothing** about the individual numeric values in
those two columns: **no per-session rate, and no share count, was retained, checked or
compared.** Nor does it validate them — `R1`'s thresholds are `fabricated_dates: 0`,
`rows > 0`, `dates_returned == rows`, and the declared window.

**And the two computations are different rules.** The adapter's column comes from an outer
merge plus a plain `ffill` (§4); `U4`'s as-of resolution *withholds* a denominator while an
explicit zero is in force (§3.2). **`U4`'s interruption logic must not be attributed to the
adapter's calculation, and the adapter's column must not be read as a validated T1 output.**

---

## 4. T2 — the adapter's own `turnover`, and the exact line where it is discarded

AkShare's `stock_zh_a_daily` computes a turnover rate itself. From the installed library,
read as text (`stock_zh_a_sina.py`, `a3acc94625983ec233b769d36afe742107dd865588ccf3799b582babd72de2b8`):

```python
amount_data_df.columns = ["date", "outstanding_share"]
...
temp_df = pd.merge(data_df, amount_data_df, left_index=True, right_index=True, how="outer")
temp_df.ffill(inplace=True)
temp_df = temp_df.astype(float)
temp_df["outstanding_share"] = temp_df["outstanding_share"] * 10000
temp_df["turnover"] = temp_df["volume"] / temp_df["outstanding_share"]
```

Three properties, all relevant to §8:

* **Unit: a fraction, not a percent.** No `× 100`. T2 and T3 differ by a factor of 100.
* **Temporal rule: a plain `ffill` after an outer merge**, i.e. the adapter carries an
  explicit **zero** forward as zero (which yields a division by zero), while the retained
  smoke rule (§3.2) *withholds* a denominator in that state. The two rules **agree on
  carry-forward and disagree on what a zero means for usability** — the smoke rule is the
  stricter one.
* The `ffill`/`dropna` also has row-count consequences documented at request `:209` (C4):
  a consumer of the adapter path must take `max(first klc date, first outstanding-share
  date)` as its effective first date.

**And the project drops both columns at the boundary.** `backend/app/data/akshare_provider.py`
(`375f34adc34adf131e44194002dc96242c45269fd445b693f2eb0bcdc84acccf`), `:110`:

```python
frame = frame.drop(columns=["turnover", "outstanding_share"], errors="ignore").copy()
```

with the reason stated in the same method's docstring at `:87-89`:

> *"The `turnover` column is a turnover *rate*, not an amount; it is dropped so the bar
> normalizer cannot mistake it for one."*

**This is the single most consequential fact in the whole trace.** The **only share-count
series reachable anywhere in the current code path** arrives attached to the Sina daily
frame — and is deliberately discarded, one line before the frame is handed on. That
deletion is *correct as written*: it prevents a rate from being stored in a currency column
(§6.1). But it also means **this share count — the vendor's own, from the same response as
the bars — is retained nowhere**. A *different*, derived share count does exist in
production storage and is described in §6.5; it is not this one.

Note the asymmetry that explains why this path exists at all: `get_daily_bars_sina`
(`:76-116`) was introduced *because* Sina is the only reachable source carrying 成交额
(`:77-84`), which the Tencent qfq kline omits. The share count is a by-product of that same
response, presently thrown away.

---

## 5. T3 — the quote-provided `turnover_rate`, which is the only wired rate

### 5.1 Read origin

`backend/app/candidates/auto_discovery.py`
(`e1c132d93c269b028afd693c9b0e91eca0e1bf7bb6f065d801bd518b24a2d794`), `:139`:

```python
turnover_rate = self._number(raw, "换手率")   # 换手率
```

`raw` is one row of a **market-wide spot snapshot** (`_extract_items` at `:116`, `:120-121`:
`for _, row in spot.iterrows(): raw = row.to_dict()`), and the snapshot comes from
`_load_spot` (`:164-168`):

* primary — `self.provider.get_a_share_spot()`, which is
  `ak.stock_zh_a_spot_em()` (`akshare_provider.py:50-53`), source string
  `"akshare.stock_zh_a_spot_em"`;
* fallback — `_eastmoney_spot()` (`:170-201`), a direct `urlopen` against
  `https://push2.eastmoney.com/api/qt/clist/get`, whose field map at `:198` assigns
  `"换手率": row.get("f8")`, source string `"eastmoney.push2_fallback"`.

**Both are Eastmoney.** T3 has **no** relationship to the Sina auxiliary endpoint, to the
retained smoke evidence, or to `daily_bar_cache`.

### 5.2 Meaning, unit, temporality, coverage

* **Unit: percent — *by the consuming code's own convention*, which is what the evidence
  actually supports.** Three consistent pieces of local evidence: the reason string
  `f"turnover_rate={turnover_rate:.2f}%"` (`auto_discovery.py:239`); the cap
  `min(float(turnover_rate or 0), 30.0)` (`:221`), which would be inert on a fraction; and
  the same cap in `scoring.py:186`. **These establish what this codebase expects, not an
  independently verified property of the vendor's field.** No vendor documentation was read
  and no payload was fetched, so the unit is an **assumed** convention here, and a vendor
  change to it would be silent.
* **Snapshot, not historical.** Each item is stamped
  `"trade_date": date.today().isoformat()` (`auto_discovery.py:149`). There is no series.
* **Coverage excludes Beijing.** `if not code.startswith(("0", "3", "6")): continue`
  (`:129-130`) — so the very instrument class the M2 smoke answered for the first time
  (`BJ920000`) is out of T3's universe entirely.
* **Denominator provenance: none. General provenance: some, and it must not be described as
  none.** No share count, no measurement date for that count, and no float-vs-total
  distinction travels with the value — that part stands. But the persisting writer
  `auto_discovery._persist` (`:244-272`) stores, in the **same row**, `source` (the vendor
  string, `"akshare.stock_zh_a_spot_em"` or `"eastmoney.push2_fallback"`), `trade_date`
  (the observation date), `reasons_json`, and `raw_json` — **the entire vendor spot row as
  captured**, including its own 换手率 field. The learning path likewise carries
  `source_task_id`, `sample_type` and `decision.source`
  (`learning_extraction.py:254-258`, `:293-299`) and, on the potential-search branch, a
  `signal_date`/`trade_date` (`:260`).
* So the honest comparison with T1 is **dimension by dimension, not a ranking**: T1 carries
  denominator age and validity-interruption state that T3 has no equivalent of; T3 carries
  a retained raw vendor row and a persisted source string that T1's `checks.json` summaries
  do not reproduce per value. **Neither is uniformly better, and this document does not
  rank them.**

### 5.3 Where it is stored

| Table | Column | DDL |
|---|---|---|
| `auto_discovered_candidates` | `turnover_rate REAL` | `sqlite_store.py:198` |
| `potential_search_items` | `turnover_rate REAL` | `sqlite_store.py:646` |
| `agent_learning_samples` | inside `features_json` | `learning_extraction.py:263`, persisted at `:621-628` |

`sqlite_store.py` = `35b2e6f9d345c6a3c4b0bf3105b51827704acbebc72ebd649d06d8221394adbe`
(**modified in the working tree relative to HEAD; the user's own uncommitted work, read
only, untouched**).

### 5.4 Consumers, with required-vs-optional and missing-value behaviour

| # | Consumer | Line | Reads from | Historical / snapshot | Required? | Missing-value behaviour |
|---|---|---|---|---|---|---|
| C1 | `auto_discovery._priority` | `auto_discovery.py:221` | in-memory spot row | snapshot | optional | `min(float(turnover_rate or 0), 30.0) * 0.5` → **silently contributes 0** |
| C2 | `auto_discovery._reasons` | `:238-239` | same | snapshot | optional | `if turnover_rate is not None:` → the reason string is simply omitted |
| C3 | `auto_discovery` persistence | `:76`, `:251`, `:262` | same | snapshot | optional | written as `NULL` |
| C4 | `scoring._volume_score` | `scoring.py:184-188` | `auto` dict, **`or`-fallback to** `raw` dict | snapshot | optional | four distinct cases — see the note below; `or 0` is only the last of them |
| C5 | `offhour_search` enrichment | `offhour_search.py:259` | discovery item | snapshot | optional | explicit `None` at `:285` and `:362` for items with no discovery row |
| C6 | `offhour_search._fallback_items_from_local_evidence` | `:304`, `:323` | **`SELECT … FROM potential_search_items`** | **persisted snapshot, re-read later** | optional | `row.get("turnover_rate")` → `None` |
| C7 | `offhour_search` persistence | `:441`, `:452`, `:471` | enriched item | snapshot | optional | written as `NULL` |
| C8 | `selection_v2` merge | `selection_v2.py:572` (`adc.`), `:613` (`psi.`) | **both tables** | persisted snapshot | optional | absent key |
| C9 | `learning_extraction._samples_from_potential_search` | `learning_extraction.py:263` | result item | snapshot | optional | `None` inside `features_json` |
| C10 | `learning_extraction._samples_from_auto_discovery` | `:304` | result item | snapshot | optional | `None` inside `features_json` |
| C11 | API exposure | `routes.py:5817-5840` | dicts from C5–C7 | snapshot | optional | passes through generically — **no `turnover` token appears anywhere in `backend/app/api/`** |
| C12 | `frontend/src/components/LegacyConsole.vue` | `:12507` | the API response | snapshot | optional | `turnover_rate?: number \| null` — a **type declaration only**; it is the sole occurrence in the file and the value is never rendered |

`routes.py` = `491c28756550aff0aa5c804c53f8171d9c529c30191daf6747ac6d964a499eb3`;
`LegacyConsole.vue` = `36de9d888edcf09d03e896d3c4f49a36df5f3c4cd859217bc4c47f189acc1d40`.

**Three structural observations, none of which is a defect claim:**

* **"Optional" means there is no hard required-field gate — it does not mean no effect.**
  No code path raises, refuses or short-circuits because turnover is missing. But the value
  feeds a score, the score feeds a ranking, and the ranking feeds what is surfaced and
  persisted. **A missing value therefore changes the outcome; it just does so silently
  rather than by failing.** Those are different properties and the earlier phrasing blurred
  them.
* **The `or`-selection in `scoring.py:184` has four distinct cases, and only one of them is
  the `or 0` default.** The line is
  `turnover = self._float(auto.get("turnover_rate") or raw.get("turnover_rate"))`, so:
  1. `auto` holds a **non-zero number** → that value is used, `raw` is never consulted;
  2. `auto` holds **numeric `0`** (or `0.0`) → **`0` is falsy, so the `raw` value is
     selected instead**, and a genuinely-zero turnover in `auto` is replaced by whatever
     `raw` reports, which may be non-zero. This is a real substitution, not a default;
  3. `auto` is absent/`None` and `raw` supplies a value → `raw` is used;
  4. **both** are absent, `None`, or zero → `_float` yields `None` or `0`, and only then
     does `min(float(turnover or 0), 30.0)` at `:186` collapse it to a **zero
     contribution indistinguishable from a genuine zero**.

  Case 2 is the one that most deserves recording: absence and zero are not handled alike,
  and the code's own precedence order decides between two sources. **No change to this is
  proposed.**
* **Two separate weights, and they must not be summed or conflated.**
  `scoring.py:186-188` caps the `turnover_score` component at `30.0 × 0.35 = 10.5` inside a
  `volume_score` itself capped at 15.0, contributing to the potential score.
  Independently, `auto_discovery.py:221` uses `30.0 × 0.5 = 15.0` toward the **separate**
  `priority` value written to `auto_discovered_candidates`. These are different quantities
  computed in different modules for different consumers. Both are **existing** weights,
  reported as read; no change to either is proposed.

**One merge behaviour worth recording.** `selection_v2.py:600` does
`merged.update({k: v for k, v in row.items() if v is not None})`, and the
`potential_search_items` loop (`:610`) runs **after** the `auto_discovered_candidates` loop
(`:569`). A merged record's `turnover_rate` therefore comes from whichever table supplied a
non-`None` value last, and the merged dict records the contributing tables in
`_evidence_sources` (`:596`, `:633`) but **does not record which table supplied any
individual field**. Both are T3, so no unit conflict arises today; the observation is
recorded because it is the mechanism by which a *future* differently-sourced turnover value
would lose its origin silently.

---

## 6. T4 and the name collisions — where "turnover" means money

### 6.1 `daily_bar_cache`: `turnover` is an **alias for the amount column**

`backend/app/data/daily_bar_cache.py`
(`90ec7bd0038147bd48ef5f9e3a354d720eeed4d05443b0a9a93039e71d7ff533`) mentions `turnover`
exactly twice, both times as a **candidate column name for currency**:

```python
# :901  (_normalize_index_bars)
amount_col = self._first_existing_column(raw_bars, ("amount", "turnover"), required=False)
```
```python
# :980-984 (daily bars)
amount_col = self._first_existing_column(
    raw_bars,
    ("amount", "turnover", "成交额"),
    required=False,
)
```

The third alias — 成交额 — settles the intent: this is **traded amount**. This is precisely
the confusion `akshare_provider.py:87-89` says the drop at `:110` exists to prevent: had the
Sina `turnover` **rate** column survived, `_first_existing_column` would have accepted it as
`amount` **only if `amount` were absent**, which on the Sina frame it is not — so the
present code is not exposed. The hazard is real but currently **not reachable**, and it is
recorded as a name-collision observation, not as a defect.

**A second alias table exists, it is stricter, and a test pins it that way.**
`backend/app/data/source_comparison.py`
(`3490c0090928256674e4732989d9d24cc632f312a69202b4e350b5f8f4713c7d`) carries its own
alias map at `:22`:

```python
"amount": ("amount", "成交额"),
```

**`turnover` is not in it**, and `backend/tests/test_source_comparison.py`
(`d38507299c31ad2540ba75764f82d311de05fe96b39cd6c0e181ab3f715ff78a`) `:74-80` asserts that
this is deliberate — the test is literally named
`test_turnover_is_not_amount_and_missing_values_are_not_zero`, and given a frame carrying
`turnover = 8.5` and no `amount` it requires `frame["amount"].isna().all()`,
`missing_columns == ["amount"]` and `quality_status == "review_required"`.

So the repository holds **two alias tables for the same concept that disagree on exactly
this name**: `daily_bar_cache` would accept `turnover` as `amount`; `source_comparison`
refuses it and flags the frame for review. Neither is currently reachable with a `turnover`
column present (§4 deletes it upstream), and **no defect is asserted here**. It is recorded
because it is the concrete, test-pinned expression of the T2-vs-T4 distinction this
document is built on — and because any future decision to preserve a turnover rate would
meet these two tables with opposite behaviour.

Note also that `source_comparison.py` contains **no occurrence of the token `turnover` at
all**; it was reached only through its test. That is the §11 limit-1 search bound
materialising in practice.

### 6.2 `daily_bar_cache` stores no share count at all

The DDL (`sqlite_store.py:922-940`) is `id, symbol, trade_date, open, high, low, close,
volume, amount, source, adjustment_mode, volume_unit, quality_status, created_at,
updated_at, UNIQUE(symbol, trade_date)`. **There is no turnover column and no
outstanding-share / float-share column.**

The direct consequence: **a turnover rate is not computable from `daily_bar_cache` alone**,
now or retrospectively, because no denominator is stored beside the volume. Any rate over
cached bars must join to a share-count series held somewhere else.

**Such a series does exist — but it is a different one, and it is derived.** See §6.5. The
statement that survives is the narrow one: the *vendor's own* share count, the one that
arrives on the same Sina response as the bars, is discarded at the fetch boundary (§4) and
is stored nowhere.

### 6.3 `trade_records.turnover_text` is an **amount**, and the rate-like field next to it has a different name

`sqlite_store.py:88-99` declares `pct_change_text TEXT, turnover_text TEXT,
float_ratio_text TEXT`. The importer fills them from the legacy record's Chinese keys —
`backend/scripts/import_legacy_data.py`
(`9253d7345190a325f336d426af8597ab225f97872b7b04680fbb9a5e36457616`), `:527-529`:

```python
record.get("pct_change_text") or record.get("涨幅"),        # 涨幅
record.get("turnover_text")   or record.get("成交额"),  # 成交额  ← AMOUNT
record.get("float_ratio_text") or record.get("占流通盘"),  # 占流通盘
```

There are **two** insert sites for these columns in that file — `:224-240` and `:513-532` —
and both write the same column list.

So `turnover_text` is **traded amount as free text**, while the nearest thing to a *rate* in
that table is `float_ratio_text` (占流通盘, share of float) under a different name. Those two
`占流通盘` references (`:240`, `:529`) are, per §11's alias search, the **only** occurrences
of `float_share`, 流通股, `hsl` or 占流通 anywhere in `backend/app`, `backend/scripts` or
`backend/tests` — there is no free-float denominator in the codebase either. The
column is consumed once, opaquely, by `backend/app/learning/service.py`
(`e1642cba599e7106d146133c755284168c09162d1fb96efdd949cf8b5e01136d`) `:464`, which copies
`row.get("turnover_text")` into a `features` dict without parsing it.

**No claim is made here about whether this importer path has ever run on any retained row.**

### 6.4 Portfolio turnover does not exist

A repository-wide search of `backend/` for `rebalanc`, `churn`, `position_turnover`,
`portfolio_turnover`, `turnover_cost` and 周转 (excluding `backend/.venv`) returns **no
match**. The only portfolio-adjacent occurrence of the word is a **comment** in
`backend/app/backtest/engine.py`
(`8baacb0125e4923aaa00b057eada94d462972621865fe845266870b1725d8b5a`) `:559`, inside
`_signal_average_price` (`:543-567`):

```python
if amount > 0 and volume > 0:
    return amount / (volume * 100.0)
# No reported turnover: fall back to the bar's typical price.
```

"turnover" there means **成交额** — the docstring at `:549-550` says so: *"It is
amount / shares where the feed reports 成交额; volume is stored in 手"* (hence `× 100`).
This is a **T4 dependency on the amount column**, and it is the reason the Sina daily path
of §4 exists at all. It is **not** a rate and **not** portfolio turnover.

One further T4 sighting for completeness: `backend/app/data/snapshot_builder.py`
(`8e9d4fc5da8875006d7dbcbd36a8af0059e38f750b7cf4ea4c7f9e916b1d7586`) `:312` — *"Tencent
quote field 37 is turnover amount in ten-thousand yuan"* — scaled ×10,000 into an `amount`
field at `:308-313`, consumed at `:225`. Currency, in 万元, not a rate.

### 6.5 T5 — a share count **does** exist in production storage, and the project already has a used / annotated / withheld pattern for it

This section corrects a statement that stood in an earlier draft of §4 and §6.2 of this
document. It contains **no** turnover token, which is why the token search of §11 limit 1
did not reach it. It was named in the reviewer's own verification pin list and then read
directly by the author (§11 disclosure).

`backend/app/data/fundamentals.py`
(`8c9741f391d0f79ce34a4d4224856ff2c11cc96cec537b68653fb106df112466`, 358 lines) derives and
persists a share count. `parse_quote_line` (`:94-122`) reads a **Tencent quote line**
(`SOURCE = "tencent_qt_snapshot"`, `:48`) and computes, at `:119-120`:

```python
# 亿股; market cap is quoted in 亿元 and price in 元.
total_share_billion=total_cap / price if total_cap else None,
```

from field 45 (total market cap) and field 3 (price); field 44 gives `float_cap_billion`,
from which a **float** share count is equally derivable. These are persisted into
`symbol_fundamental_snapshot` (`sqlite_store.py:1637-1651`), whose columns include
`total_share_billion REAL`, `float_cap_billion REAL` and — importantly —
`available_at TEXT NOT NULL`.

**So a denominator exists in the database.** It is not the Sina series (§4), it is not the
retained smoke series (§3), it is **derived from a market-cap quote by division**, and the
module's own docstring (`:10-27`) states the accuracy contract without softening it:

> *"Share counts and book value change over time (placements, buybacks, unlocks, earnings).
> The further back the date, the larger the error, and companies that delisted are absent
> entirely. Every derived value is therefore stamped `method="projected_from_snapshot"` and
> must never be presented as an observed point-in-time fact."*

**And this is the part that bears directly on §8.** For a quantity with structurally the
same defect the memo worries about for turnover — a value carried backwards in time whose
freshness cannot be verified — this project has **already implemented** the middle option,
and it looks like this:

| Mechanism | Where | What it does |
|---|---|---|
| **Off by default** | `backtest/engine.py:81` `allow_projected_fundamentals: bool = False`; `routes.py:6292` the same default on the API model | Projection is opt-in per run, never ambient |
| **As-of cutoff** | `engine.py:500-501` — `as_of=None if self._project_fundamentals else current_date`; resolver `_visible_row` excludes snapshots whose `available_at` is later than the cutoff | A snapshot ingested today cannot leak into an old backtest |
| **Provenance travels with the value** | `fundamentals.py:337-343` returns `method`, `snapshot_as_of`, `snapshot_available_at`, `snapshot_source` alongside the number | The consumer can label or exclude it |
| **The result is labelled** | `engine.py:367` `metrics["fundamental_point_in_time"] = not allow_projected_fundamentals`; `:522` `"fundamental_method"` carried into the signal context | The output says which mode produced it |
| **Fails visible, not silent** | `engine.py:103-112` distinguishes an empty resolver from one with no rows visible at the cutoff | An unusable denominator is reported, not defaulted |

**What this is, and what it is not.** It is an **existing precedent read from source**,
recorded because the memo's used / annotated / withheld question has already been answered
once in this codebase for a structurally similar quantity. It is **not** a proposal to
adopt, extend, reuse or wire that mechanism for turnover; **no** part of it is applied here,
and its existence is **not** evidence that a turnover rate would be sound. Note also the two
substantive differences from T1: this denominator is **derived from a quote by division**
rather than reported by the vendor, and it carries **no** equivalent of the smoke series'
explicit zero-interruption rule (§3.2).

**The hard limits on everything in this subsection.** This is a reading of **code and
schema only**. No database was opened, so this document establishes **none** of the
following, and nothing above should be read as implying any of them:

* that `symbol_fundamental_snapshot` currently holds **any** rows;
* what symbol or date **coverage** it has, historically or at all;
* whether `total_share_billion` is **total or free-float** in any given row, or whether the
  Tencent field-45 market cap it divides is itself total-share based (the module's own
  docstring at `:20-21` warns that A+H total market cap is overstated);
* that it is **equivalent to, a substitute for, or comparable with** the retained smoke
  denominator — it is a different quantity from a different vendor by a different method.

**It is not proposed as a replacement for the retained denominator**, and its ability to
support any turnover computation is **unestablished**.

---

## 7. Is there any smoke-to-production path? — the negative result and its exact bound

**Search performed:** a recursive content search of `backend/app` and `backend/scripts` for
the tokens `_m2_smoke`, `smoke_checks`, `smoke_capture`, `evidence_2026` and
`claude methods`, excluding `backend/.venv`.

**Result: zero matches.** No module in the backend imports, opens, reads, references by
path, or is configured to reach any M2 smoke producer, evidence directory, revision
directory or retained JSON file. The retained work is, at this moment, **entirely unwired**.

**The converse also holds and is worth stating in the same breath.** The smoke producers do
not write into production either: the reference they read is the frozen
`reference/reference_extract.json`, and `replay()` installs `db_guard()` so that opening a
production database during a replay raises
(`M2B_REAL_SOURCE_VERIFICATION_REQUEST.md:282`).

**The search was then widened**, because it was only a few lines of work: the same token set
plus `sina_klc_decoder` across **all** of `backend/`, `scripts/`, `frontend/src` and `docs/`
(excluding `node_modules`, `backend/.venv` and `__pycache__`). **Still zero matches.**

**Bound of this coverage — stated because the dispatch requires it, and because the claim is
a negative.** This establishes that no **literal textual reference** to those paths exists
anywhere outside `claude methods/` itself. It does **not** exhaust every conceivable route:
a path assembled at runtime from configuration or environment, an operator copying a file by
hand, or a future wiring change would not appear in it. **The claim made is: no textual
reference exists in the searched trees. No stronger exhaustion is claimed, and no claim is
made about what has or has not been executed.**

**And the presence of `turnover_rate` in `scoring.py` / `auto_discovery.py` does not
constitute a route.** §5.1 traces those values to an Eastmoney spot snapshot by explicit
assignment. Identical naming is the only thing they share with T1.

### 7.1 The M1/M2 offline contract and gate sources — the trace the dispatch asked for

**Files searched, and the tokens used** (`turnover`, 换手, `outstanding`, `denominator`,
`share count`, 流通):

| File | sha256 | Hits |
|---|---|---|
| `claude methods/M1_THREE_YEAR_DATA_READINESS.md` | `d51ffabc4c67fac9ae51b3ff7e48962e8f1c3b5ce89603b8f44eb9cd5bdb3183` | **2** |
| `claude methods/M1_CLOSURE.md` | `5afb333fc9d76532e61de53a58febc5ff0a0ced2f32eb66c57d28608fe8e4f7e` | 1 (a different denominator) |
| `claude methods/_m1_closure/staging_gate.py` | `7152d773ea9ca9778c0f038cf9caaf7be36119c7d0cc059de80821d53ff35b7f` | **0** |
| `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` | `71e0dc52b8cf93281b1c09f501a62695915ef070a740dc378df2f1637a66007c` | 1 |
| `M1_ACCEPTANCE_CODEX.md`, `M1_GATE_WIRING_CODEX_REVIEW.md`, `M1_KEY_CONTRACT_CODEX_REVIEW.md` | — | 0 / 1 / 0 |

**The gate implementation itself does not consult turnover in any form.**
`staging_gate.py` is 740 lines and contains **no** occurrence of `turnover`, 换手,
`outstanding`, 流通股 or even `volume_unit`. So no M1 eligibility, coverage or staging
decision reads a turnover rate today, and none would be disturbed by any §8 option.

**But the M1 contract does mention turnover twice, and both are decision-relevant:**

* **`M1_THREE_YEAR_DATA_READINESS.md:700` (G-D′)** ties turnover directly to the **volume
  unit**: if `volume_unit` is repaired without the paired `amount` fix, *"any feature
  computing 换手率 as 成交量/流通股 is still inflated 100×"*. That is a **units hazard on the
  exact quotient T1 would form**, already identified in the M1 contract — and it matters
  because the retained smoke measures volume in **share** (`U2` PASS) while
  `daily_bar_cache` stores **手** (`akshare_provider.py:111-112` divides by
  `SHARES_PER_HAND`). Any future turnover rate would have to reconcile those two, and the
  M1 contract already names the failure mode.
* **`:814` (U10)** records an **open** M1 question — 303,562 rows have no basis for
  cross-validating `volume_unit` — and names, as one possible remedy, *"流通股本数据用于
  换手率交叉校验"*: free-float share data used to **cross-check** turnover. **That is a
  verification use, not a metric use**, and it is the only place in the M1/M2 contract text
  where a share-count series is wanted at all.

**Two name collisions to keep separate.** `M1_CLOSURE.md:282` uses "denominator" for the
**listing-aware eligible-session denominator** in `staging_gate.py:205-218` — sessions, not
shares. And `M2B_P1_BASIS_CONTRACT_PROPOSAL.md:998` lists *"decide turnover policy"* among
the things that proposal explicitly does **not** do, which is consistent with §8's closing
statement that turnover is not on P1's critical path.

**Bound.** This is a token search over the named files only, at the hashes given. It does
not claim every M1/M2 document was read in full, and it establishes nothing about runtime
behaviour.

---

## 8. Decision impact — used / annotated / withheld, **as alternatives only**

The dispatch requires that consequences for an **unwired smoke result** be kept separate
from consequences for the **existing wired metrics**. They are separated in every row.
**None of these is adopted, recommended for adoption, or partially applied.**

| | **A — used** | **B — annotated** | **C — withheld** |
|---|---|---|---|
| **What it would mean** | A turnover rate derived from an outstanding-share denominator becomes available to some downstream consumer | The same, but every value carries its denominator date, age, and validity state | No rate derived from the auxiliary series is made available |
| **Effect on the retained smoke result (T1)** | **Nothing usable exists to switch on**: `U4` emits no rate series (§3.3), the only computed turnover column is the adapter's, retained by name only (§3.6), the vendor share series is dropped at the fetch boundary (§4), and `daily_bar_cache` has no column for either (§6.2). **What A actually costs depends entirely on the future design and consumer chosen** — computing at read time from an existing snapshot (§6.5) and persisting a new column are very different amounts of work. **This document does not select a design and therefore does not price A** | The same design-dependence, plus an annotation channel. The content to annotate already exists in `checks.json` (`denominator_age_days_*`, `invalid_denominator_intervals`) but is per-check, not per-value; whether carrying it per value is cheap or expensive **again depends on the design**, and §6.5 shows a mechanism of this shape already exists in the codebase for a different quantity | **No construction, no behavioural change**: this is the current state of the system |
| **Effect on existing quote turnover (T3)** | **None follows automatically** — T3 is a distinct field from a distinct source (§5.1), and no A design that leaves it alone touches it. The two are **not interchangeable**: different sources, different temporality (snapshot vs history), different universe (T3 excludes BJ, §5.2), and **not a common unit** — T3 is percent by local convention while **T1 has no defined unit at all** (§3.3). **Whether an A design would route T1 into today's quote scorer is a design choice this document does not make and cannot assume** | **None follows automatically.** If annotation were extended to T3, the honest statement is that T3 has **no denominator provenance** to annotate, though it does carry source, observation date and a retained raw vendor row (§5.2) | **None** |
| **Effect on amount-based metrics (T4)** | **None.** `_signal_average_price` (§6.4), the `daily_bar_cache` amount column (§6.1) and `trade_records.turnover_text` (§6.3) are currency and are untouched by any rate decision | **None** | **None** |
| **Risk it creates** | Conditional on the design: a rate whose denominator is undeclared (§3.2), from a capture whose capability verdict is **FAIL**, with a carry-in age of median 1,975 days for `SH600011` — **an age, which is not by itself established staleness** (§3.4). If such a value were routed into the existing scorer it would meet the four-case `or`-selection of §5.4, in which absence and zero are handled differently; **whether it would be routed there is not assumed** | Lower **if** the annotation reaches the point of use. Residual risk: an annotation no consumer reads is indistinguishable from A. Whether B costs more than A **depends on the design** — a mode flag plus a provenance passthrough, as in §6.5, is not obviously more work than a new persisted column | Continued reliance on T3. **Not a ranking:** T3 lacks the denominator age and validity-interruption state T1 carries, while carrying a source string, an observation date and a retained raw row that T1's summaries do not reproduce per value (§5.2) |
| **What current bytes support** | Nothing here supports A **as an improvement**; the retained evidence supports only that the series parses, resolves, and passes an advisory bound check on 728 rows | The annotation *content* is supported — it is already measured and retained at check level | Fully supported; it is the status quo and requires no assertion |

**Three things this matrix explicitly does not do.** It proposes **no** expiry threshold,
staleness cutoff, tolerance or calibration; it proposes **no** silent substitution of T1 for
T3 or relabeling of any field; and it performs **no** numerical re-analysis of prices.

**And one inference that must not be drawn.** Choosing **C — withheld** would close
**nothing**: not P1, not U-6, not source capability, not M2. P1 is a labeling and
corroboration contract (memo §2.1); U-6 is deferred on separate grounds; source capability
is capped at FAIL by the historical `EV6`, which no offline decision and no future run can
clear (memo §3.3). Turnover is not on the critical path of any of them.

---

## 9. A recommendation — **proposed, not adopted**

Stated plainly because the dispatch permits it, and marked as an opinion, not a finding.

> **Proposed: C (withheld) for T1 as the standing state, with the §10 A-items done first —
> and one narrow, separately-authorized change considered on its own merits: stop
> *discarding* the share-count series at `akshare_provider.py:110` without also storing it.**

The reasoning, in one paragraph. The used/annotated/withheld framing presupposes a value
that exists and merely needs a policy; §3.3, §3.6 and §7 show that no rate series is
retained and nothing reads the smoke outputs in the searched trees, so "withheld" is not a
decision to *stop* anything — it is an accurate name for where the system already is, and
it costs nothing to keep. What is genuinely lossy is different and smaller: the vendor's
**own** share count arrives on every Sina daily response and is deleted one line later
(§4), so the most direct raw material for any future turnover work is discarded at each
fetch, while `daily_bar_cache` has no column for it (§6.2). Note carefully that the
deletion at `:110` is **correct for its stated purpose** — keeping a rate out of a currency
column — so this is **not** a proposal to remove that line; the observation is that
preserving the *share count* is a separable question from dropping the *rate*.

**Two qualifications this recommendation depends on, both stated rather than assumed.**
First, a share count is **not** absent from the database: `symbol_fundamental_snapshot`
holds a derived `total_share_billion` (§6.5). It is a different quantity — market cap ÷
price, projected, explicitly *"never to be presented as an observed point-in-time fact"* —
and this document has **not** established its current row count, historical coverage,
free-float validity, or any equivalence to the retained denominator, and does **not**
propose it as a replacement for one. But its existence means the choice is not "preserve
this or have nothing". Second, the M1 contract already flags a **100× units hazard** on
exactly the 成交量/流通股 quotient (§7.1), between the smoke's `share` volume unit and
`daily_bar_cache`'s 手 — so any A or B design carries a reconciliation obligation that is
independent of the policy choice.

**No change is made, designed or authorized here.** Any of it would touch production
storage and requires its own scope review; it is named only so the decision the memo asked
for can be taken with the real trade-off in view.

---

## 10. Prioritized remaining evidence and actions for this specific question

**A — possible now from existing files, no new evidence and no policy choice required:**

*Two items originally on this list were small enough to finish inside this task and were
completed rather than deferred: the repository-wide widening of the §7 negative search, and
the discovery of the competing `source_comparison` alias table in §6.1. They are recorded
there, not here.*

1. **Read the retained auxiliary bodies as text** (`raw/02_…bin`, `raw/05_…bin`) to record
   the vendor's own field spelling and the exact entry count directly from the bytes, rather
   than through `checks.json` summaries. No decoding, no execution — the envelope is
   `var KKE_ShareAmount_… = ([...]);` and is readable as text.
2. **Reconcile the two amount-alias tables** (§6.1). `daily_bar_cache` accepts `turnover` as
   `amount`; `source_comparison` refuses it and a test pins the refusal. Deciding which
   behaviour is intended is a static question, but **changing** either one is a production
   edit and is therefore **not** an A-item — only the comparison is.
3. **Trace `_first_existing_column`'s alias tables across every caller** in
   `daily_bar_cache.py`, to establish whether any *other* rate-named column could reach a
   currency column on any provider frame. §6.1 covers the two `amount` call sites; the
   other column resolutions are unchecked.
4. **Classify the remaining `agent_learning_samples` producers** (`learning_extraction.py`
   has seven `_samples_from_*` methods; two were traced here) to bound how much
   provenance-free quote data enters the learning store. Static reading only.

**B — requires evidence this project does not have:**

5. Whether the Sina outstanding-share count is **total, free-float, or A-share-only**. Not
   declared in the payload (§3.2); not derivable from retained bytes; would need vendor
   documentation or an independent reference.
6. Whether `SH600011`'s series is **complete and current** at the source, i.e. whether the
   2019-10-15 entry is genuinely the last change event. **Long carry-in alone establishes
   neither an incorrect share count nor incompleteness** (§3.4). This is not reachable by
   re-fetching a change-event endpoint, exactly as the memo's §4 says.
7. Whether the zero-interruption rule behaves correctly on **real** in-window data. The
   retained window contains no invalid observation (§3.4); the rule is currently evidenced
   by synthetic C1 cases only.
8. **Anything about the contents of `symbol_fundamental_snapshot`** (§6.5): row count,
   symbol and date coverage, whether `total_share_billion` is total or free-float in
   practice, and how it compares with the retained denominator. **All of this needs a
   database read, which is outside this and every current authorization**, and none of it is
   requested here.

**C — a user policy choice, not an evidence question:**

9. The used / annotated / withheld selection itself (§8).
10. Whether preserving a share count at the fetch boundary is worth a scoped production
    change (§9) — which would require its own authorization and its own scope review.
11. If any A or B design is ever pursued: **which volume unit the quotient is formed in**.
    §7.1 shows the M1 contract already identifies a 100× error on exactly this quotient, and
    the retained smoke measures volume in `share` while `daily_bar_cache` stores 手. This is
    a design obligation, not an evidence gap — **no reconciliation is proposed here**.

**Explicitly not requested and not prepared:** no new capture, no database permission, no
live run, no pilot, no backfill, no additional symbols, no endpoint expansion.

---

## 11. Read scope, pins, limits and preservation

**Everything read for this document, and nothing else.** Search commands were confined to
`backend/app`, `backend/scripts`, `backend/.venv/.../akshare/stock/stock_zh_a_sina.py`
(as text), `frontend/src`, `claude methods/*.md` and `claude methods/_m2_smoke/`.

| File | sha256 | Used for |
|---|---|---|
| `claude methods/_m2_codex_review/turnover_dependency_dispatch_20260909.txt` | `e2042b58cb2c6549b395d1a69c129ff863a837c1202a7ef7a34b3afd9efab2cd` | the assignment |
| `claude methods/M2B_NEXT_STAGE_DECISION_MEMO.md` | `536505ea4a29e506dadf3c510eab67dc8d52a84706f2288c85690af64aea0d4a` | §1, §3.4, §8 |
| `claude methods/M2B_REAL_SOURCE_VERIFICATION_REQUEST.md` | `c39726d06aafc4d630c05fe93141e8b99012221571da0eea28789d5fa9033057` | §3.1, §3.3, §4, §7 |
| `claude methods/_m2_smoke/sina_klc_decoder.py` | `c6d736b170c29009ef273ed7705330f2a251545bca720d55c998d0a715f83fc8` | §3.2 |
| `claude methods/_m2_smoke/smoke_checks.py` | `4b062a55fae6f9bd348a7ffdf20073debababffafc71568e2aaaf8181c832bbe` | §3.3 |
| `claude methods/_m2_smoke/smoke_capture.py` | `059d0c43547db0bf520afc9c034dbc5c1638b3beb12c77e35e62ace03f85ad35` | §3.4 (window constants) |
| `…/revision_20260908T082833Z_r2abc_v2/checks.json` | `b6c97eab21254b837f3bd1768eec22c8a54ec925da82beb0f12810156f42d387` | §3.4 |
| `…/revision_20260908T082833Z_r2abc_v2/PROVENANCE.json` | `204b6501819333d9723547be7e89e14a1d3c19add484d8d0bb07276b9dbecf5e` | provenance pin |
| `backend/.venv/…/akshare/stock/stock_zh_a_sina.py` | `a3acc94625983ec233b769d36afe742107dd865588ccf3799b582babd72de2b8` | §4 |
| `backend/app/data/akshare_provider.py` | `375f34adc34adf131e44194002dc96242c45269fd445b693f2eb0bcdc84acccf` | §4, §5.1 |
| `backend/app/data/daily_bar_cache.py` | `90ec7bd0038147bd48ef5f9e3a354d720eeed4d05443b0a9a93039e71d7ff533` | §6.1 |
| `backend/app/data/snapshot_builder.py` | `8e9d4fc5da8875006d7dbcbd36a8af0059e38f750b7cf4ea4c7f9e916b1d7586` | §6.4 |
| `backend/app/storage/sqlite_store.py` | `35b2e6f9d345c6a3c4b0bf3105b51827704acbebc72ebd649d06d8221394adbe` | §5.3, §6.2, §6.3 |
| `backend/app/candidates/auto_discovery.py` | `e1c132d93c269b028afd693c9b0e91eca0e1bf7bb6f065d801bd518b24a2d794` | §5.1, §5.2, §5.4 |
| `backend/app/candidates/offhour_search.py` | `6a77661a26c60882ec33b20e09023d1e75b3711ba6f98dee82297d0e019db22c` | §5.4 |
| `backend/app/candidates/scoring.py` | `1e7dbcd3c25b812910f6fcb7d76a5c8398cad8d70b0a01356283cda7a3c5c912` | §5.4 |
| `backend/app/candidates/selection_v2.py` | `a5d1274e16241817dec54ef8a5312b9ed0385328cb56dfd42bb7236ddb030673` | §5.4 |
| `backend/app/agent_control/learning_extraction.py` | `f6fcf31584fdef33728e1540935d3ce382fd3b3bc107b49f49aa2c83948de7ba` | §5.3, §5.4 |
| `backend/app/learning/service.py` | `e1642cba599e7106d146133c755284168c09162d1fb96efdd949cf8b5e01136d` | §6.3 |
| `backend/app/backtest/engine.py` | `8baacb0125e4923aaa00b057eada94d462972621865fe845266870b1725d8b5a` | §6.4 |
| `backend/app/api/routes.py` | `491c28756550aff0aa5c804c53f8171d9c529c30191daf6747ac6d964a499eb3` | §5.4 (C11) |
| `backend/scripts/import_legacy_data.py` | `9253d7345190a325f336d426af8597ab225f97872b7b04680fbb9a5e36457616` | §6.3 |
| `backend/app/data/fundamentals.py` | `8c9741f391d0f79ce34a4d4224856ff2c11cc96cec537b68653fb106df112466` | §6.5 (T5) |
| `claude methods/M1_THREE_YEAR_DATA_READINESS.md` | `d51ffabc4c67fac9ae51b3ff7e48962e8f1c3b5ce89603b8f44eb9cd5bdb3183` | §7.1 |
| `claude methods/M1_CLOSURE.md` | `5afb333fc9d76532e61de53a58febc5ff0a0ced2f32eb66c57d28608fe8e4f7e` | §7.1 |
| `claude methods/_m1_closure/staging_gate.py` | `7152d773ea9ca9778c0f038cf9caaf7be36119c7d0cc059de80821d53ff35b7f` | §7.1 (bounded negative) |
| `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` | `71e0dc52b8cf93281b1c09f501a62695915ef070a740dc378df2f1637a66007c` | §7.1 |
| `claude methods/M2B_TURNOVER_DEPENDENCY_CODEX_REVIEW.md` | `bf82cf3eedb0ca04fcffee3c583c25868a99c933254041b550d2d78f56d076ff` | the review this revision answers |
| `backend/app/data/source_comparison.py` | `3490c0090928256674e4732989d9d24cc632f312a69202b4e350b5f8f4713c7d` | §6.1 (competing alias table) |
| `backend/tests/test_source_comparison.py` | `d38507299c31ad2540ba75764f82d311de05fe96b39cd6c0e181ab3f715ff78a` | §6.1 (the test pin) |
| `backend/tests/test_strategy_selection_v2.py` | `c1f6458bad3d64caa0d0870c83d9d0affbefb97baf0ebed0e351a06eddd2fa35` | §11 limit 2 |
| `backend/tests/test_backtest_engine.py` | `5d298e447ec46a74c5e79deeb5e14a9c29127704d0274c099a5f56ef6ba99494` | §11 limit 2 |
| `frontend/src/components/LegacyConsole.vue` | `36de9d888edcf09d03e896d3c4f49a36df5f3c4cd859217bc4c47f189acc1d40` | §5.4 (C12) |
| `frontend/src/components/TradingDashboard.vue` | `1bb9d2b1390f1c68735dc7b4118d0d2316a82e397e10587cb691efce87c0e420` | §11 limit 2 (negative: no match) |

`sqlite_store.py`, `routes.py` and several others are **modified in the working tree
relative to HEAD `73f266d`**. Those are the user's and Codex's uncommitted changes; they
were **read only**, and the hashes above pin the working-tree bytes actually read.

**Coverage limits — read as constraints on every claim above.**

1. **Search-token bound, and a demonstrated instance of it failing.** Consumers were found
   by searching for `turnover`, `turnover_rate`, 换手, 换手率, `outstanding_share`, 成交额,
   `float_share`, 流通股, `hsl`, 占流通 and `float_ratio`. A consumer that reaches the value
   through a fully generic mechanism — `SELECT *`, `**kwargs`, `row.items()`, a pandas frame
   passthrough — need not contain any of those tokens. **Two concrete instances found by
   other means prove this limit is real, not hypothetical:** `selection_v2.py:600`, which
   copies every non-`None` column of a row including `turnover_rate` without naming it; and
   `source_comparison.py` (§6.1), which contains **no occurrence of the token `turnover`**
   yet holds a competing alias table for the very column at issue and was reached only via
   its test file. **No claim of exhaustive dependency coverage is made**, and at least one
   such miss was corrected during this task rather than discovered afterwards.
2. **Tree bound, as actually searched.** `backend/app` and `backend/scripts` were searched
   exhaustively for the token set above. `frontend/` (excluding `node_modules`) was then
   searched in full for `turnover|换手`: **exactly one match repository-wide**, the type
   declaration at `LegacyConsole.vue:12507` in §5.4 (C12) — so `TradingDashboard.vue` and
   every other frontend component contain none. `backend/tests` was searched for `turnover`
   and yields three files: `test_source_comparison.py:74` (§6.1), `test_strategy_selection_v2.py:344`
   and `:370` (fixture inserts into `potential_search_items`), and
   `test_backtest_engine.py:664` (a comment on the T4 amount path). **Not** systematically
   searched **for turnover tokens**: `scripts/` (PowerShell), `docs/`, `backend/configs/`,
   and any other configuration.

   **Reconciling this with §7, because the two sections use different token sets over
   different trees, and the difference matters.** §7's negative uses the *smoke-path* token
   set (`_m2_smoke`, `smoke_checks`, `smoke_capture`, `evidence_2026`, `claude methods`,
   `sina_klc_decoder`) and was run over `backend/`, `scripts/`, `frontend/src` and `docs/`.
   This limit-2 list is about the *turnover* token set, which was **not** run over
   `scripts/`, `docs/` or `backend/configs/`. **Neither search was run over the union**, and
   no claim here depends on a search that was not performed. §7.1's M1/M2 contract and gate
   search is a third, separate scope: the named files at the stated hashes only.
3. **Static bound.** This is a reading of code, not an observation of behaviour. **No claim
   is made anywhere that any of these paths has ever executed, on retained rows or on any
   others.** Nothing was run.
4. **`n = 1` bound on T1.** All T1 numbers come from one capture on one trading day.
5. **Strategy code was read to classify dependencies only.** No strategy file, dataset,
   knowledge record or setting was edited.

**Disclosure of how the consumer search was carried out, stated plainly.** For revision 1,
the consumer discovery of §5 and §6 was run **twice**: once by the author directly, and once
in parallel by a set of **read-only search agents** given the same repository and explicit
instructions to write nothing, run nothing, import nothing and open no database. That
parallel pass created **no file in this repository** — its transcripts live in the session
directory outside the project — and it **produced no claim that appears in this document
unverified**: every finding it surfaced was re-checked by the author with a direct search
before use, and several of its reported findings (including claimed matches in
`TradingDashboard.vue` and `backtest/metrics.py`) **did not survive that check and were
discarded**. Its one durable contribution was listing `source_comparison.py` and its test
among candidate files; the §6.1 finding itself came from the author's own `backend/tests`
search for `turnover`, which reached the test, which led back to the module's alias table.
**Revision 2 used no such pass**, per the reviewer's instruction; its corrections rest on
short static traces of the pinned files only.

**And §6.5 exists because the reviewer found it, not because this search did.**
`backend/app/data/fundamentals.py` contains no turnover token and was not reached by any
search described above. It was named in Codex's own verification pin list, and the author
then read it directly and corrected the two over-broad claims it disproves. That is
recorded here rather than presented as an independent discovery.

**Preservation.** No existing file was modified, moved, renamed or deleted. The only write
performed by this task is the creation of this single document. The two documents validated
immediately before it —
`M2B_CACHE_WRITE_PATH_AUDIT.md` (`6fa4439d9c8c19331357018729ccbae9a06e13708de2831f5fca3af596cecd73`)
and `M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md` (`155207ffcee956a5a582bb993ef315a56345c7a854637c007f178ec0bf3ded92`)
— are **unchanged**. Verification evidence accompanies the handoff.

---

## 12. Revision record

**Revision 2 — `M2B_TURNOVER_DEPENDENCY_CODEX_REVIEW.md`
(`bf82cf3eedb0ca04fcffee3c583c25868a99c933254041b550d2d78f56d076ff`), TD-R1 to TD-R3, one
consolidated correction.** The reviewed revision-1 bytes were
`58f776853cae5e4d70091eef510ebdc0d62729d9ef07116d4921937c3b6c5aca`.

| # | Finding | Resolution |
|---|---|---|
| **TD-R1** | The headline and §4, §6.2, §8, §9 conflated `U4`'s output with the whole smoke replay, and `daily_bar_cache` with all production storage. `smoke_checks.py:288-330` calls the installed AkShare function, whose frame carries `outstanding_share` and `turnover` (`stock_zh_a_sina.py:207-208`); retained `R1` for both stocks records 978 rows and those column names. Separately, `fundamentals.py:121` derives `total_share_billion` and `sqlite_store.py:1645` stores it, so "no share count retained anywhere in production storage" was unsupported. T1 was also implicitly given T2's fraction units, and "a new store and writer are required" was asserted as fact | **New §3.6** states the `R1` replay precisely: a turnover column **is** computed inside the adapter, its **name** is retained for both stocks (columns list quoted verbatim from `checks.json`), **no value** is retained, checked or compared, and `U4`'s as-of interruption logic is **not** attributable to the adapter's `ffill` calculation. §3.3 consequence 3 rescoped to `U4`. The headline restated as "retains no turnover *rate series*". **New §6.5** documents T5 — the derived `total_share_billion` route, its units, `available_at`, provenance passthrough and opt-in `allow_projected_fundamentals` mechanism — with an explicit list of what it does **not** establish (no rows, coverage, free-float validity or equivalence; no database opened; not proposed as a replacement). §4 and §6.2 narrowed to the vendor's own share count and to `daily_bar_cache` respectively. §2 now records T1's unit as **undefined**, and §8/§9 make every construction-cost and consumer-routing statement **conditional on a design not selected here** |
| **TD-R2** | §5.2, §5.4, §8 and §10 overstated provenance absence and understated default effects. `auto_discovery.py:244-272` persists `source`, `trade_date`, `reasons_json` and `raw_json` beside `turnover_rate`; `learning_extraction.py:254-258`/`:293-299` retain task and source metadata. Percent units rest on local formatting, not vendor verification. `scoring.py:184`'s `or` can let a numeric zero select a non-zero fallback before `or 0` ever applies. "Optional" was read as "no effect". The 10.5 component and the separate priority contribution were run together | §5.2 rewritten: unit attributed to **the consuming code's own convention**, explicitly not an independently verified vendor property; denominator provenance still absent, but the persisted `source` / observation date / raw vendor row now recorded, with a **dimension-by-dimension** comparison replacing the withdrawn "weaker on every axis". §5.4 now enumerates the `or`-selection's **four cases**, naming case 2 (numeric zero in `auto` selects `raw`) as a substitution rather than a default; states that optional means **no hard gate, not no effect** on score, ranking or persisted outcome; and separates the 10.5 `turnover_score` cap from the independent 15.0 `priority` contribution. §8's rows made conditional throughout, with "strictly more work", the percent-vs-fraction comparison and the assumption that T1 would enter today's scorer all withdrawn |
| **TD-R3** | The headline and quantity table asserted universal negatives that only the later coverage limits qualified, and the requested M1/M2 contract/gate inspection was missing | The bounds are now **in** the headline and §2 (both marked as bounded claims about what was searched). **New §7.1** gives the M1/M2 trace: files, hashes, tokens and results — `staging_gate.py` (740 lines) contains **no** turnover, 换手, `outstanding`, 流通股 or `volume_unit` token, so no M1 gate consults turnover; `M1_THREE_YEAR_DATA_READINESS.md:700` ties turnover to a **100× volume-unit hazard** on the 成交量/流通股 quotient; `:814` (U10) wants share data for **cross-validation**, not as a metric; `M1_CLOSURE.md:282`'s "denominator" is the listing-aware **session** denominator; and `M2B_P1_BASIS_CONTRACT_PROPOSAL.md:998` excludes deciding turnover policy from P1. §11 limit 2 now reconciles the **three different scopes** (turnover tokens, smoke-path tokens, named M1/M2 files) so no claim rests on a search that was not run |

No workflow, sweep, numerical study, scratch script or output directory was used for this
revision; the corrections rest on short static traces of the files pinned in §11.

**Stop: `proposed for review`.**
