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
> Revision 1.
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

> **The retained M2 smoke work never produces a turnover value, and nothing in
> `backend/app` or `backend/scripts` reads any M2 smoke output.** Every live consumer of a
> field spelled `turnover*` consumes **one of three other quantities**, none of which is the
> retained-derived measure and two of which are not rates at all.

That changes the shape of the decision, and §8 separates the two consequences the dispatch
asks to be kept apart: consequences for an **as-yet-unwired** smoke result, and
consequences for the **existing quote and legacy** metrics that are wired.

---

## 2. Four different quantities share the name — and only one is at issue

Name identity is not linkage. These four are distinguished throughout this document, and
the evidence for each separation is in the section named.

| # | Quantity | Spelling in code | Units | Where it lives | § |
|---|---|---|---|---|---|
| **T1** | **Turnover *rate*, retained-derived** — traded volume against an outstanding-share denominator, from the M2 smoke auxiliary series | *no field name — never materialised* | *no value emitted* | `claude methods/_m2_smoke/` only | §3 |
| **T2** | **Turnover *rate*, adapter-computed** — AkShare's `turnover` column on `stock_zh_a_daily` | `turnover` | **fraction** (not percent) | computed in the AkShare library, **dropped at `akshare_provider.py:110`** | §4 |
| **T3** | **Turnover *rate*, quote-provided** — the vendor's 换手率 in a market-wide spot snapshot | `turnover_rate` | **percent** (vendor convention) | `auto_discovered_candidates`, `potential_search_items`, `agent_learning_samples` | §5 |
| **T4** | **Turnover *amount*** — 成交额, money, not a rate at all | `turnover` (as a column **alias for `amount`**), `turnover_text`, and one comment | **currency** (yuan; one source in 万元) | `daily_bar_cache` column resolution, `trade_records`, `backtest/engine.py` | §6 |

A fifth candidate — **portfolio turnover** (rebalancing churn, position turnover, turnover
cost) — **does not exist anywhere in this repository**. See §6.4 for the exact search that
establishes this and its bound.

**The memo's open question is about T1 alone.** T2, T3 and T4 are pre-existing and are
touched by this document only to say what they are and where they go.

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
3. **No turnover field is emitted, persisted or exported.** The `measured` block written to
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
(§6.1). But it also means **no share count is retained anywhere in production storage**.

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

* **Unit: percent.** Three independent pieces of code evidence: the reason string
  `f"turnover_rate={turnover_rate:.2f}%"` (`auto_discovery.py:239`); the cap
  `min(float(turnover_rate or 0), 30.0)` (`:221`), meaningless as a fraction; and the same
  cap in `scoring.py:186`.
* **Snapshot, not historical.** Each item is stamped
  `"trade_date": date.today().isoformat()` (`auto_discovery.py:149`). There is no series.
* **Coverage excludes Beijing.** `if not code.startswith(("0", "3", "6")): continue`
  (`:129-130`) — so the very instrument class the M2 smoke answered for the first time
  (`BJ920000`) is out of T3's universe entirely.
* **No denominator, no age, no provenance travels with the value.** The vendor supplies a
  number; nothing records what share count produced it, when that count was measured, or
  whether it is float or total. This is the sharpest contrast with T1, which carries
  `denominator_age_days_*` and `invalid_denominator_intervals` by construction.

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
| C4 | `scoring._volume_score` | `scoring.py:184-188` | `auto` dict, else `raw` dict | snapshot | optional | `min(float(turnover or 0), 30.0) * 0.35` → **silently contributes 0** |
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

**Two structural observations, neither of which is a defect claim:**

* **Every single T3 use is optional and None-tolerant.** No code path fails, refuses or
  changes verdict because turnover is missing; the two scoring paths convert absence into a
  **zero contribution that is indistinguishable from a genuinely zero turnover**.
* **T3's largest weight is 10.5 points.** `scoring.py:186-188` caps `turnover_score` at
  `30.0 × 0.35 = 10.5`, inside a `volume_score` capped at 15.0; `auto_discovery.py:221` uses
  `30.0 × 0.5 = 15.0` toward `priority`. These are **existing** weights, reported as read;
  no change to them is proposed.

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

The direct consequence: **a turnover rate is not computable from cached history**, now or
retrospectively, because the denominator was never stored. Any future rate over cached bars
needs a share-count series that does not currently exist in the database — which is exactly
what §4 shows is being discarded at the fetch boundary.

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

---

## 8. Decision impact — used / annotated / withheld, **as alternatives only**

The dispatch requires that consequences for an **unwired smoke result** be kept separate
from consequences for the **existing wired metrics**. They are separated in every row.
**None of these is adopted, recommended for adoption, or partially applied.**

| | **A — used** | **B — annotated** | **C — withheld** |
|---|---|---|---|
| **What it would mean** | A turnover rate derived from an outstanding-share denominator becomes available to some downstream consumer | The same, but every value carries its denominator date, age, and validity state | No rate derived from the auxiliary series is made available |
| **Effect on the retained smoke result (T1)** | **Requires work that does not exist**: no rate is computed today (§3.3), no share count is stored (§6.2), and the share series is dropped at the fetch boundary (§4). "Using" it is not a switch — it is a new field, a new store, and a new writer | Same construction cost **plus** an annotation channel. The annotation content already exists in `checks.json` (`denominator_age_days_*`, `invalid_denominator_intervals`) and would have to be carried per value, which no current storage or transport does | **Zero construction cost, and zero behavioural change**: this is the current state of the system |
| **Effect on existing quote turnover (T3)** | **None.** T3 is Eastmoney 换手率 in percent from a spot snapshot (§5.1); nothing in A touches it. Note the two are **not interchangeable** — different sources, different units (percent vs fraction), snapshot vs history, and T3 excludes BJ (§5.2) | **None**, unless the annotation were extended to T3 — for which there is **nothing to annotate**: T3 carries no denominator, no age and no provenance at all (§5.2) | **None** |
| **Effect on amount-based metrics (T4)** | **None.** `_signal_average_price` (§6.4), the `daily_bar_cache` amount column (§6.1) and `trade_records.turnover_text` (§6.3) are currency and are untouched by any rate decision | **None** | **None** |
| **Risk it creates** | A rate whose denominator is undeclared (§3.2), sourced from a capture whose capability verdict is **FAIL**, carried forward a median of 1,975 days for `SH600011`, entering a scorer that **cannot distinguish a missing value from zero** (`or 0`, §5.4) | Lower — the staleness is visible at the point of use. Residual risk: an annotation that no consumer reads is indistinguishable from A. Building an annotation channel is **strictly more** work than A, not less | Continued reliance on T3, whose provenance is **weaker** than T1's on every axis measured: no denominator, no age, no validity interruption, no BJ coverage |
| **What current bytes support** | Nothing here supports A **as an improvement**; the retained evidence supports only that the series parses, resolves and passes an advisory bound check on 728 rows | The annotation *content* is fully supported — it is already measured and retained | Fully supported; it is the status quo and requires no assertion |

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

The reasoning, in one paragraph. The used/annotated/withheld framing implicitly assumes a
value that exists and merely needs a policy; §3.3 and §7 show that it does not exist and is
not wired, so "withheld" is not a decision to *stop* anything — it is an accurate name for
where the system already is, and it costs nothing to keep. What is genuinely lossy is
different and smaller: the **denominator** arrives on every Sina daily response and is
deleted one line later (§4), so the raw material for *any* future turnover work — annotated
or not — is being thrown away on every fetch while `daily_bar_cache` has nowhere to put it
(§6.2). Note carefully that the deletion at `:110` is **correct for its stated purpose** —
keeping a rate out of a currency column — so this is **not** a proposal to remove that
line; it is an observation that preserving the *share count* is a separable question from
dropping the *rate*. **That change is not made, not designed and not authorized here**; it
requires its own scope review, would touch production storage, and is named only so the
decision the memo asked for can be taken with the real trade-off in view.

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

**C — a user policy choice, not an evidence question:**

8. The used / annotated / withheld selection itself (§8).
9. Whether preserving a share count at the fetch boundary is worth a scoped production
   change (§9) — which would require its own authorization and its own scope review.

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
   searched: `scripts/` (PowerShell), `docs/`, `backend/configs/`, and any other
   configuration.
3. **Static bound.** This is a reading of code, not an observation of behaviour. **No claim
   is made anywhere that any of these paths has ever executed, on retained rows or on any
   others.** Nothing was run.
4. **`n = 1` bound on T1.** All T1 numbers come from one capture on one trading day.
5. **Strategy code was read to classify dependencies only.** No strategy file, dataset,
   knowledge record or setting was edited.

**Preservation.** No existing file was modified, moved, renamed or deleted. The only write
performed by this task is the creation of this single document. The two documents validated
immediately before it —
`M2B_CACHE_WRITE_PATH_AUDIT.md` (`6fa4439d9c8c19331357018729ccbae9a06e13708de2831f5fca3af596cecd73`)
and `M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md` (`155207ffcee956a5a582bb993ef315a56345c7a854637c007f178ec0bf3ded92`)
— are **unchanged**. Verification evidence accompanies the handoff.

**Stop: `proposed for review`.**
