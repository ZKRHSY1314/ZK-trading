# M2b — amount representation audit: the two alias tables, and what actually reaches them

> **Status: `proposed for review`.** Static, existing-file offline analysis under the
> continuing offline authorization. **Nothing is adopted, changed or implemented.** §9 states
> a question for a future policy decision, **not a patch and not a recommendation**.
>
> **Nothing was executed.** No SQLite of any kind, no database, dataset, fixture or
> demo-seed read, no provider/service/strategy import or call, no test run, no
> replay/decoder, no network or capture, no scratch script, no output directory, no agent,
> no repository sweep, no Git action. Everything below is **source text** plus
> **already-retained JSON**, quoted with exact lines.
>
> Task `AMOUNT-REPRESENTATION-20260909`, dispatched by
> `_m2_codex_review/amount_representation_dispatch_20260909.txt`
> (`7e49e5118906ff55e7d6cff721e24f3ecb0aa72f1978e42b75f29fe5799e8732`). Date: 2026-09-09.
> Revision 2 — AR-R1 through AR-R3 of `M2B_AMOUNT_REPRESENTATION_CODEX_REVIEW.md` addressed in
> one consolidated correction (§11); **reported as addressed pending Codex review, not
> marked closed here.** Closes A-2/A-3 of `M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md`
> (`50261775464ba24cf5cedfd3bdc4ce002421f7bcf238ba96cc5d9637c3b3a1ec`), preserved unchanged.
>
> **This is about the trusted volume/amount representation. It is not the turnover policy
> question, which stays open and undecided.**
>
> **P1 open · U-6 deferred · every eligibility false · source capability FAIL including the
> historical `EV6` · both capture authorizations consumed. M2 is not complete.**

---

## 1. The question

`M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md` §6.1 recorded that two modules resolve the same
canonical `amount` column from **different alias sets**, and that one of them is test-pinned:

* `daily_bar_cache.py:901` — `("amount", "turnover")` (benchmark path)
* `daily_bar_cache.py:980-984` — `("amount", "turnover", "成交额")` (stock path)
* `source_comparison.py:22` — `("amount", "成交额")`, with
  `test_turnover_is_not_amount_and_missing_values_are_not_zero` requiring a `turnover`-only
  frame to be flagged, not accepted.

It deferred two static items: **A-2/A-3 — what is the actual reach and consequence?** This
document answers that, and only that.

---

## 2. The two selectors, read exactly

### 2.1 `daily_bar_cache._first_existing_column` — presence, priority, no ambiguity signal

```python
# daily_bar_cache.py:934-945
def _first_existing_column(self, frame, candidates, required=True) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    if required:
        return None
    return None
```

Four properties, all of which matter below:

1. **Presence only.** It tests `candidate in frame.columns`. It never looks at a single
   value, so a column that exists and is entirely null is indistinguishable from one full
   of real numbers.
2. **Alias priority order** decides, not column position.
3. **No ambiguity signal.** If two aliases are both present, the earlier alias silently
   wins and nothing records that the other existed.
4. **The `required` flag is inert** — both branches `return None`. Callers act on the
   `None` themselves: the stock path raises
   `RuntimeError(f"Unsupported daily bar columns: …")` when a *required* column is missing
   (`:985-987`), while `amount_col` is passed `required=False` and a `None` simply yields
   `amount=None`. The behaviour is correct; the flag is dead code and is **not** a defect
   claim.

### 2.2 `source_comparison.normalize_frame` — position, ambiguity recorded, nulls counted

```python
# source_comparison.py:118-127
for name, aliases in ALIASES.items():
    positions = [i for i, column in enumerate(frame.columns) if column in aliases]
    if not positions:
        missing_columns.append(name)
        values = pd.Series([None] * len(frame), dtype=object)
    else:
        if len(positions) > 1:
            ambiguous_columns.append(name)
        values = frame.iloc[:, positions[0]].reset_index(drop=True)
    input_missing[name] = int(values.isna().sum())
```

Differences from §2.1 that are not cosmetic: selection is by **leftmost column position**,
not alias priority; a **second matching alias is recorded** as `ambiguous_columns`; a
**missing column is distinguished from present-but-null** (`missing_columns` versus
`input_missing`); and `turnover` is not an alias at all (`:22`).

Downstream, `_masks` (`:161-184`) marks a row invalid when any of
`NUMERIC = (open, high, low, close, volume, amount)` is non-finite, and `profile_frame`
(`:235-240`) reports `quality_status = "review_required"` when `invalid_rows > 0` **or**
`missing_columns`/`ambiguous_columns`/`adjustment_metadata_conflict` is set. **A NaN amount
therefore invalidates the row**, which `test_window_quality_is_separate_from_older_full_history_defects`
(`test_source_comparison.py:83-93`) pins by setting one `amount` to `None` and asserting
`quality_status == "review_required"`.

---

## 3. The concrete frames that actually reach these selectors

`settings.daily_bar_source_policy` defaults to `"tonghuasun_first"` (`config.py:35`), whose
order is `tonghuasun.local.quotes.candle → akshare.stock_zh_a_daily → tencent.fqkline.qfq →
akshare.stock_zh_a_hist` (`daily_bar_cache.py:171-175`), loaded by the four lambdas at
`:141-156`. The benchmark path has its own two loaders (`:312-320`). All six were read.

| # | Concrete source | Constructed at | Amount-family columns in the returned frame | Rate column present? |
|---|---|---|---|---|
| F1 | `tonghuasun.local.quotes.candle` | `tonghuasun_provider.py:364-366` — `columns = ["date","open","high","low","close","volume","amount"]` | **`amount`** (from `transaction_amount`, `:410`) | no |
| F2 | `akshare.stock_zh_a_daily` (Sina) | `akshare_provider.py:108-116` | **`amount`**; `turnover` and `outstanding_share` **dropped at `:110`** | **no — removed before return** |
| F3 | `tencent.fqkline.qfq` | `daily_bar_cache.py:669-679` — every row literally `"amount": None` | **`amount`, present and entirely null** | no |
| F4 | `akshare.stock_zh_a_hist` (eastmoney) | `stock_hist_em.py:998-1011` inside `stock_zh_a_hist` (def `:952`) | **`成交额`** | **`换手率`** — in *neither* alias table |
| F5 | `akshare.stock_zh_index_daily` | `index_stock_zh.py:293-316`; retained `R1` replay observed columns `["date","open","high","low","close","volume"]` | **none** | no |
| F6 | `sina.cn.index_kline_daily_fallback` | `daily_bar_cache.py:881-890` — the frame is built with exactly `date, open, high, low, close, volume` | **none** | no |

F5's schema is not inferred from the library alone: the retained `R1` check in
`revision_20260908T082833Z_r2abc_v2/checks.json` (`b6c97eab…`) records the **installed**
index adapter, replayed on the captured `SH000300` body, returning 5,987 rows with exactly
that six-column list — an observed frame schema, not a reading of intent.

---

## 4. Alias reach: which alias can actually bind

| Selector | Alias tuple | F1 | F2 | F3 | F4 | F5 | F6 |
|---|---|---|---|---|---|---|---|
| `daily_bar_cache` stock (`:980-984`) | `amount`, `turnover`, `成交额` | `amount` | `amount` | `amount` (null) | `成交额` | — | — |
| `daily_bar_cache` benchmark (`:901`) | `amount`, `turnover` | — | — | — | — | **no match** | **no match** |
| `source_comparison` (`:22`) | `amount`, `成交额` | `amount` | `amount` | `amount` (null) | `成交额` | n/a | n/a |

**The `turnover` alias never binds on any inspected concrete frame.** On the stock path the
only frame that ever carries a `turnover` column is F2, and `akshare_provider.py:110`
removes it — with the reason stated at `:87-89` — before the frame is returned, and that
frame carries a real `amount` anyway, so `turnover` would lose on priority even if it
survived. On the benchmark path neither F5 nor F6 has any amount-family column at all, so
the `("amount","turnover")` tuple matches nothing.

**Finding 1 (bounded).** On every inspected concrete path the `turnover` alias is
**unreachable**. There is **no active rate-as-amount substitution**, and the Sina drop at
`:110` remains correct. This is a statement about the six inspected frames, not about every
possible frame a generic normalizer could be handed.

**Finding 2.** F4 shows the alias tables are not merely lucky: the one vendor frame that
*does* ship a turnover rate names it **`换手率`**, which is in **neither** table, so it
cannot be selected as `amount` by either module.

---

## 5. Present-but-null: the case a "the amount column is normally there" argument misses

F3 is the case the dispatch warns against dismissing. Tencent's loader writes
`"amount": None` for **every** row (`daily_bar_cache.py:669-679`), and so does the
**delegated** endpoint it falls back to: `_load_tencent_newfqkline_qfq_daily_bars`
(`:779-827`, reached from `:638` and `:655`) builds its rows with `"amount": None` at
`:819`. **Both** read, not assumed. So: on either Tencent branch,

* `_first_existing_column` sees `amount` **present** and selects it (§2.1 property 1); the
  `成交额` alias is never consulted, correctly, since F3 has none.
* the row builder does `amount=self._float(row.get(amount_col)) if amount_col else None`
  (`:1005`), and `_float` maps `NaN`/`None` to `None` (`:1048-1056`);
* `quality_status` was set to `"ready"` at `:195` and is only downgraded when
  `adjustment_mode != "qfq"` (`:204-205`), which does not apply to a successful qfq load.

**So a Tencent-sourced row is written `quality_status = "ready"` with `amount = NULL`.**
That is not a name collision and not a rate-as-amount error — it is a **representation
gap** carried through a selector that cannot see it. The code says as much in its own
comment at `:157-159`: *"Only the tonghuasun and Sina sources report 成交额; Tencent qfq
never does, so a chain that falls through to Tencent silently trades reported liquidity for
the execution-model proxy."*

**The benchmark path reaches the same shape for a different reason, and it is a different
requirement.** F5 and F6 have no amount-family column, `amount_col` is `None`, and the
**index** row builder — `_normalize_index_bars` at `:917-930`, *not* the stock builder —
emits `amount=None`, and does so alongside its own distinct defaults
`adjustment_mode="none"`, `volume_unit="unknown"`, `quality_status="ready"`. **An index is
not traded, so a missing benchmark amount is not an ingestion defect and nothing here says
it should exist.** Stock and index amount requirements are kept separate throughout this
document.

**Finding 3 (bounded, and conditional on these builders being reached).** Three of the six
inspected concrete paths construct candidate bars carrying `ready` with a null `amount` —
F3 as a **stock**, F5/F6 as **benchmarks**, which is a different case. The selector never
sees it because it tests presence, not values. This describes what the code constructs; it
is **not** an observation that any such row was written or is stored.

---

## 6. Do the two modules disagree on the same input? — three cases

*Hand-worked reasoning examples over column shapes. These are **not** executed tests and
**not** observed vendor payloads.*

| Case | Input shape | `daily_bar_cache` | `source_comparison` | Disagree? | Reachable from an inspected caller? |
|---|---|---|---|---|---|
| **A** | `turnover` present, `amount` absent | selects `turnover` as amount | `missing_columns = ["amount"]` → `review_required` | **yes** | **no.** Only F2 carries `turnover`, and `:110` drops it before return. Pinned by `test_source_comparison.py:74-80` |
| **B** | both `成交额` and `amount` present, 成交额 leftmost | alias priority → `amount` | position → `成交额`, and `ambiguous_columns = ["amount"]` → `review_required` | **yes** | **no.** No inspected frame carries both |
| **C** | `amount` present, all values null (**= F3**) | `amount` selected; every row `amount=NULL`, `quality_status="ready"` | `missing_columns = []`, but every row non-finite in `NUMERIC` → `invalid_rows = n` → `review_required` | **yes** | **YES** — Tencent qfq, third in the default chain |

Case C's *shape* is reachable from a real loader, and both selectors can be handed a frame
of that shape. `backend/scripts/compare_market_sources.py` — the only non-test caller of
`source_comparison` (`:173`, `:191-192`, `:204-205`, `:211-213`) — calls the same loaders:
tonghuasun `get_daily_bars` (`:43`), `AkshareProvider().get_daily_bars` with
`_load_tencent_qfq_daily_bars` as its fallback (`:47`, `:57`), and `get_daily_bars_sina`
(`:62`).

**But the comparison caller does not hand `normalize_frame` what the cache writer sees, and
three differences must be recorded rather than glossed:**

1. **The caller adds unit labels the provider never set.** At `:50` the eastmoney probe
   stamps `source`, `adjustment_mode="qfq"`, **`volume_unit="hand"`** and
   **`amount_unit="yuan"`**; at `:63` the Sina probe stamps `amount_unit="yuan"`. The
   Tencent fallback deliberately stamps **neither** — `frame.attrs.setdefault("source", …)`
   at `:58` with the comment *"No volume unit claim from the name alone; amount is
   absent."* **These are local caller assertions, not new vendor evidence**, and they do
   **not** reach the production cache writer, which sets `volume_unit` from provider attrs
   or its own default (`daily_bar_cache.py:194`, `:203`) and has no `amount_unit` at all.
   So it is wrong to say no unit label reaches comparison — one does, for two of the
   sources, and it is the caller's own.
2. **The frame is serialized and rebuilt.** `:70-73` narrows `attrs` to a four-key
   whitelist and emits `frame.to_json(orient="split", date_format="iso")`; `:188-191` and
   `:201-204` reconstruct a `DataFrame` from `{columns, data}` and re-apply those attrs
   before normalizing. The object compared is a **round-tripped reconstruction**, not the
   provider's object.
3. **A fourth input exists.** `cached_sample` (`:101-118`, profiled at `:209-213`) opens the
   production database **read-only** (`mode=ro`, `PRAGMA query_only=ON`) and profiles
   **stored cache rows**, not a provider frame — a post-writer input whose contents this
   document has not inspected and makes no claim about. *(Named here for completeness; the
   §4 matrix is bounded to the direct provider probes.)*

**And "same loader" is not "same bytes".** These are separate network invocations at
separate times; nothing here compares two runs' payloads. **Case C is therefore a
same-input reasoning example over a shape a real loader constructs — not an observed
cross-run byte comparison.**

**Finding 4 (conditional).** Given a frame of shape C, the two modules reach **opposite
classifications**: the ingestion builder produces `ready`, the comparison profile reports
`review_required`. Neither is wrong on its own terms — they answer different questions —
but only the comparison path records the condition. **No claim is made that this has
occurred in any run.**

---

## 7. Which layer sees it — related through actual calls only

| Layer | Reached by | What it does with a null-amount row |
|---|---|---|
| `_first_existing_column` | `daily_bar_cache.py:901`, `:982` | **Never sees it.** Presence-only |
| The **batch** conflict guard | the `ON CONFLICT … WHERE` clause of `_upsert_bars`, **`:465-477`** — the statement both the stock writer (`:278`) and the benchmark writer (`:366`) execute | **Conditionally protects an existing conflicting row.** `NOT (daily_bar_cache.quality_status='ready' AND daily_bar_cache.amount IS NOT NULL AND excluded.amount IS NULL)` (`:473-477`) suppresses the **UPDATE** when a stored ready row already has a real amount. **Three limits:** it applies only where a conflicting row exists at that statement, so a **first insert** proceeds; the near-identical clause at `:406-418` belongs to the **single-row `_upsert_bar` helper**, whose only caller is `_save_error_bar` (per the accepted `M2B_CACHE_WRITE_PATH_AUDIT.md`, not reopened here); and it says nothing about **deletes** — see the row below |
| Deletes that precede the same executemany | `:502-521`, inside `_upsert_bars` before `conn.executemany(sql, rows)` at `:521` | **No protection.** Three unconditional `DELETE`s run first: `trade_date='ERROR'`; `trade_date >= incomplete_session` when that is armed; and, when every incoming bar is `qfq`, all rows of that symbol with `source='sina.cn.kline_daily_fallback' AND adjustment_mode='unknown'`. **So the guard above is not a global guarantee that a stored good row cannot be removed or replaced** |
| `source_comparison` | `compare_market_sources.py` only | **Detects.** `invalid_rows`, `missing_values["amount"]`, `review_required` |
| M1 `chk_units` — **stocks only** | `staging_gate.py:526` → `acceptance_runner.py:163`, body `:188-208` | **Quarantines a stock row.** `verifiable_sql` requires `amount IS NOT NULL AND amount > 0` (`:191-194`), so a null-amount **stock** row falls out of `verifiable` into `quarantined` and is never counted `contradicted`; the implied-price test (`:204-205`) is not applied to it |
| M1 `chk_units` — **benchmarks** | same call; `benchmarks=mark_syms` supplied by staging at `:526` | **Never sees them.** `where_stock = "symbol NOT IN (…)"` (`:177-179`) excludes the benchmark list, and the docstring (`:163-173`) states why: *"an index is not traded, so demanding trade-capacity evidence from it would either fail a valid benchmark or invent liquidity."* **F5/F6 rows are therefore outside this gate by design — not quarantined by it, and not a defect** |
| M2 `U1` | retained `checks.json`, `smoke_checks.py` | **Never sees these rows.** `U1` runs on the smoke's decoded klc research rows, not on `daily_bar_cache` contents. It would fail such a row — it requires positive volume **and** amount — but it is not in this path |
| `backtest/engine._signal_average_price` | `engine.py:543-567` | **Bypasses silently.** `amount = float(signal_context.get("amount") or 0)`; with 0 it takes the typical-price fallback at `:559-567`. Exactly the trade named in the `:157-159` comment |

**Finding 5 (bounded, and split by instrument class).** For a **stock** null-amount row:
the M1 unit gate quarantines it, the comparison module detects it, the batch guard
conditionally prevents it from *updating* an existing good row, and the backtest silently
degrades. For a **benchmark** null-amount row the M1 gate does not apply at all, by design.
**Nothing rejects either at write time.**

**Three things this does not establish.** *Write eligibility* (what the SQL clause would
permit), *an attempted write* (that any writer ran), and *durable database contents* (what
is stored) are **distinct**, and this document evidences only the first. **No database was
opened and no row was observed.**

---

## 8. Units — what is established, and what is not

| Quantity | Value seen | Basis | Established? |
|---|---|---|---|
| F1 volume | divided by `SHARES_PER_HAND = 100` at `tonghuasun_provider.py:257-259`, tagged `volume_unit="hand"` | the module's own 2026-09-03 comment reports a median ratio of exactly 100 over 2,260 overlapping days on 40 symbols | **empirically argued in-repo**, against cached hands — not a vendor declaration |
| F2 volume | divided by 100 at `akshare_provider.py:111-112`, tagged `"hand"` | the docstring at `:86-88` states Sina reports 股 | code assertion; consistent with retained `U2` (`share`) for the Sina klc series |
| F3 volume | **no conversion**; `volume_unit` stays the `"hand"` default (`:194`) | nothing verifies it | **not established.** A default is not a measurement |
| F4 volume | no conversion; default `"hand"` | eastmoney 成交量 is conventionally 手 | **not established here** |
| F1/F2/F4 amount | stored as returned; no currency conversion anywhere on these paths | — | **currency unit not declared by any of them**; `daily_bar_cache` has no `amount_unit` column |
| Quote amount elsewhere | `snapshot_builder.py:308-313` scales Tencent quote field 37 by 10,000 (万元 → 元) | a local comment | a **different** path; noted only to show 万元-vs-元 exists in the codebase and is handled separately |

**Finding 6.** `source_comparison` reads `volume_unit`/`amount_unit` from `frame.attrs`
(`:213`, `_METADATA` at `:28-35`) and normalises them through `_unit` (`:64-77`), defaulting
to `"unknown"`. `daily_bar_cache` **stores** `volume_unit` but has **no `amount_unit`
column** at all. So a currency-unit disagreement between sources could not be recorded in
the cache even if it were detected. **No conversion is proposed and no unit is invented
here; unestablished units stay unestablished.**

### 8.1 What the retained M2 unit/currency evidence actually covers — `U1`, `U2`, `U3`

Read from `smoke_checks.py` (`4b062a55…`) and the retained `checks.json` (`b6c97eab…`); no
replay, decoder or recomputation.

| Check | Code | Applies to | Retained result | What it does **not** establish |
|---|---|---|---|---|
| `U1` |  `smoke_checks.py:1221-1228` | stocks | PASS ×2 — every research row has positive volume **and** amount | anything about `daily_bar_cache` rows; it reads decoded klc rows |
| `U2` | `:1231-1240`, delegating to `provenance.derive_unit` (`_m2_pilot/provenance.py:100-132`, `21197f57…`; imported as `prov` at `smoke_checks.py:52`) | **stocks only** | PASS ×2, windowed unit `share`, one-sided agreement between amount and the price band; 978 usable windowed rows, 5,935 (SH) / 1,393 (BJ) all-rows | a **vendor declaration** of the unit — it is derived from the payload's own amount/price relation |
| `U3` | `:1299-1316`, stock-only branch (`if klass == "stock"`) | **stocks only** | PASS ×2 — *"amount ratio ~ 1.00 on 10 sessions (yuan, no 10k scaling)"*, all ten ratios exactly `1.0`, tolerance `0.01`; `INCONCLUSIVE` where no session carries an amount on both sides | an independent currency **declaration**. It is a **consistency** result between the live Sina klc series and the cached reference on ten sessions where **both** sides had a positive amount |

**Three boundaries follow, and each matters to §7.**

* **`sh000300` has neither `U2` nor `U3`** in the retained results — the index is outside
  both, matching `chk_units`'s benchmark exclusion (§7). Index currency and volume units
  are therefore **unaddressed by M2 evidence**, which is consistent with F5/F6 carrying no
  amount at all.
* **`U3`'s scope is ten sessions per stock**, on one capture, on the **Sina klc** series
  only. It **cannot certify** the Tencent path (F3), the eastmoney path (F4), the
  tonghuasun path (F1), the index paths, or anything in `daily_bar_cache`.
* **A caller-added `amount_unit="yuan"` label (§6) is not this evidence.** The retained
  `U3` string contains the word *yuan* because the check's own text says so; the label in
  `compare_market_sources.py:50`/`:63` is a separate local assertion. **Neither is an
  upstream vendor declaration**, and this document does not treat either as one.

---

## 9. Bounded findings, and what a change would have to touch — **a question, not a patch**

**Where the inspected paths are protected.** On all six concrete frames the `turnover`
alias cannot bind (§4); the one vendor rate column is named `换手率` and matches neither
table; the Sina drop at `:110` is correct and should stay. **Within that scope there is no
active rate-as-amount bug**, and none is claimed.

**What remains unresolved is a generic-input contract, not a live defect.** Cases A and B
(§6) are genuine divergences that no inspected caller can currently produce. They are
properties of the alias tables, and they would become reachable only if some future frame
carried `turnover` without `amount`, or both amount spellings at once. Nothing here
predicts that.

**The one reachable divergence is C**, and it is a representation gap rather than a naming
error: a present-but-null `amount` yields a `ready` bar while the comparison module profiles
the same shape as `review_required` (§6). Three of six paths construct that shape (§5) —
F3 as a stock, F5/F6 as benchmarks, which is a **different requirement** and not a defect.

**A correction to an earlier draft's proposal, because it did not follow the actual flow.**
That draft suggested "treat an all-null amount column like an absent one". **In the
inspected builders they are already treated identically** — `amount=self._float(...) if
amount_col else None` (`:1005`, `:925`) produces `None` either way, and both emit `ready`.
**That equivalence therefore changes nothing**, and it is withdrawn.

**What a change would actually have to touch, traced rather than asserted.** The flag is
not decided in the normalizer. `_refresh_stock_symbol` **overwrites every normalized bar's
status after the fact**:

```python
# daily_bar_cache.py:213-214
for bar in normalized:
    bar.quality_status = quality_status
```

where `quality_status` is the loop-level value from `:195`/`:204-205`. So marking a bar
inside `_normalize_bars` would be **erased**; any real change would have to alter what the
loop computes, on the stock path, at that point. The benchmark path has no equivalent
overwrite — `_normalize_index_bars` sets `quality_status="ready"` directly (`:917-930`) —
so the two paths would need separate treatment, and **the index has no amount requirement
to begin with**.

**Therefore the proposal is reduced to a question, not a patch.** *If* a future policy
decided that a stock bar with no usable amount should be distinguishable in the cache, the
smallest place to express it is the `:195`/`:204-205` computation that `:213-214`
propagates — **not** the alias selector and **not** the normalizer. **Nothing is
implemented, designed, adopted or recommended**; no new quality label or rule is introduced
by this document; and any such change is **conditional on a future policy decision and a
separate production authorization**.

**Future validation requirement, corrected.** An earlier draft asserted such a change would
leave the upsert guard's behaviour unchanged. **That is not established and is withdrawn**:
the batch guard at `:465-477` tests `daily_bar_cache.quality_status = 'ready'` on **both**
sides of a conflict, so **changing a flag can change guard outcomes** — a bar no longer
marked `ready` would stop suppressing an incoming update, and could itself be updated where
it previously could not. A coherent requirement is therefore: any chosen semantics must be
accompanied by an explicit statement of its intended effect on the `:465-477` clause and on
the pre-`executemany` deletes at `:502-521`, and be validated against that stated intent —
**not** by assuming the write path is unaffected. **That is written for a future authorized
task; nothing about it is executed, and no threshold or label is set here.**

*(Two unrelated cleanups noticed in passing — the inert `required` parameter of §2.1, and
the benchmark/stock alias tuples differing — are **not** fixes for a missing amount and are
**not** proposed. They are recorded as observations only.)*

**Remaining decisions and evidence, kept separate from this audit.** Whether a null
`amount` *should* be a quality flag is a policy question and is **not decided here**.
Whether an `amount_unit` column is wanted is a schema question and is **not proposed**.
And the turnover used/annotated/withheld question stays exactly where
`M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md` §8 left it — **nothing in this document bears on
it**, and none of P1, U-6, source capability or M2 is advanced by it.

---

## 10. Read scope, pins, limits, preservation

**Everything relied upon, at the bytes read.**

| File | sha256 | Used for |
|---|---|---|
| `claude methods/_m2_codex_review/amount_representation_dispatch_20260909.txt` | `7e49e5118906ff55e7d6cff721e24f3ecb0aa72f1978e42b75f29fe5799e8732` | the assignment |
| `claude methods/M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md` | `50261775464ba24cf5cedfd3bdc4ce002421f7bcf238ba96cc5d9637c3b3a1ec` | §1 (A-2/A-3) |
| `backend/app/data/daily_bar_cache.py` | `90ec7bd0038147bd48ef5f9e3a354d720eeed4d05443b0a9a93039e71d7ff533` | §2.1, §3, §5, §6, §7 |
| `backend/app/data/source_comparison.py` | `3490c0090928256674e4732989d9d24cc632f312a69202b4e350b5f8f4713c7d` | §2.2, §6, §8 |
| `backend/tests/test_source_comparison.py` | `d38507299c31ad2540ba75764f82d311de05fe96b39cd6c0e181ab3f715ff78a` | §2.2, §6 (read as source; **not run**) |
| `backend/app/data/akshare_provider.py` | `375f34adc34adf131e44194002dc96242c45269fd445b693f2eb0bcdc84acccf` | F2, §8 |
| `backend/app/data/tonghuasun_provider.py` | `3cd5a67c014925454d4896d5abe456430f9e758d06a4babab146a097265310f3` | F1, §8 |
| `backend/app/config.py` | `1cb7dd7bc7d48593eda083db80d31f1d712323c49df74c4d0d1f57416129e7d7` | the default policy |
| `backend/app/backtest/engine.py` | `8baacb0125e4923aaa00b057eada94d462972621865fe845266870b1725d8b5a` | §7 |
| `backend/app/data/snapshot_builder.py` | `8e9d4fc5da8875006d7dbcbd36a8af0059e38f750b7cf4ea4c7f9e916b1d7586` | §8 (万元 note) |
| `backend/scripts/compare_market_sources.py` | `a8e08c59d356a53057d2085ea689e6b8c18828616d090e52f8157c653c7738f2` | §6 (the only non-test caller) |
| `claude methods/_m1_closure/staging_gate.py` | `7152d773ea9ca9778c0f038cf9caaf7be36119c7d0cc059de80821d53ff35b7f` | §7 (the call at `:526`) |
| `claude methods/_m1_closure/acceptance_runner.py` | `59b67c18ed714f9e074d20d8ac8d9d68e0258ed259cd07c0ec60a36e45c5e9ad` | §7 (`chk_units`) |
| `claude methods/_m2_pilot/provenance.py` | `21197f57e7d594045d2842003b538a7d5cd82da5a5dfc426bdffea855eb17f63` | §8.1 (`derive_unit`, imported by `smoke_checks.py:52`) |
| `claude methods/M2B_AMOUNT_REPRESENTATION_CODEX_REVIEW.md` | `ff720564eda8cb2e3fff8a1d452d64965ec99f171ae68bdb7ea7eabf6dd21cc4` | the review this revision answers |
| `…/revision_20260908T082833Z_r2abc_v2/checks.json` | `b6c97eab21254b837f3bd1768eec22c8a54ec925da82beb0f12810156f42d387` | F5's observed columns |
| `backend/.venv/…/akshare/stock/stock_zh_a_sina.py` | `a3acc94625983ec233b769d36afe742107dd865588ccf3799b582babd72de2b8` | F2 |
| `backend/.venv/…/akshare/stock_feature/stock_hist_em.py` | `749a94a192bcd79ee76867fb8dfc7c563613cf08afb1dd72ca5a97c471bcd3d8` | F4 (`stock_zh_a_hist` only) |
| `backend/.venv/…/akshare/index/index_stock_zh.py` | `91416fa4f522c977ee536ded8d2e96307e4849c52e1a27301f229754927b9c1b` | F5 (`stock_zh_index_daily` only) |

The three installed-library files were read **narrowly**, only at the functions named, to
settle concrete frame schemas. **No full library scan was performed.** No dataset, fixture,
demo seed or private file was opened. `sqlite_store.py`, `routes.py` and other working-tree
files carry the user's and Codex's uncommitted changes; nothing was modified.

**Limits.**

1. **Six concrete frames.** §4's reachability finding covers the four stock loaders of
   `tonghuasun_first` and the two benchmark loaders. Other `source_policy` values select
   subsets of the same four (`:163-186`); no other provider was inspected, and a frame
   shape reached some other way is outside this scope.
2. **Static only.** Nothing was run. **No claim is made that any of these paths has ever
   executed, nor about what any table currently contains** — no database was opened.
3. **Column schemas, not vendor semantics.** A column name, a local comment or a default
   value is not independent verification of what a vendor reports. §8 marks each unit
   accordingly; F3's and F4's volume units are recorded as **not established**.
4. **The synthetic tables in §6 are reasoning examples** over column shapes — not executed
   tests, not observed payloads.
5. **`compare_market_sources.py` was read for its calls only**; it was not run, and no claim
   is made that it has been.

**Preservation.** No existing file was modified, moved, renamed or deleted; the only write
is this document. `M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md` (`50261775…`),
`M2B_CACHE_WRITE_PATH_AUDIT.md` (`6fa4439d…`), `M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md`
(`155207ff…`) and every Codex review are unchanged. Verification accompanies the handoff.

---

## 11. Revision record

**Revision 2 — `M2B_AMOUNT_REPRESENTATION_CODEX_REVIEW.md`
(`ff720564eda8cb2e3fff8a1d452d64965ec99f171ae68bdb7ea7eabf6dd21cc4`), AR-R1 to AR-R3, one
consolidated correction.** The reviewed revision-1 bytes were
`dbd902254b7098796471fed6ad5a518143bb661e627e7bcb76c6d06b4bfccf82`. The alias-selection
findings (§2), the bounded rate-alias reach (§4) and the Tencent present-but-null
construction are preserved. **Findings are reported as addressed pending review, not marked
closed here.**

| # | Finding | Correction made |
|---|---|---|
| **AR-R1** | §7 treated F3/F5/F6 alike as quarantined by `chk_units`, cited `:414-418` as the `_upsert_bars` guard, and cited the stock builder `:998-1010` for the index path | §7 now splits **stocks from benchmarks**: `chk_units` excludes the staging-supplied benchmark list (`acceptance_runner.py:177-179`, docstring `:163-173` — *"an index is not traded…"*), so F5/F6 are **outside that gate by design and their missing amount is not a defect**. The guard citation is corrected to the **batch** clause at **`:465-477`** (amount clause `:473-477`), the statement both real writers execute, with `:406-418` identified as the single-row `_upsert_bar` helper. A new row records the three unconditional **deletes at `:502-521`** that precede the same `executemany`, so no global "stored good rows cannot be removed" guarantee is implied; the accepted `M2B_CACHE_WRITE_PATH_AUDIT.md` is referenced, not reopened. §5's index citation is corrected to **`:917-930`**, with its distinct `adjustment_mode="none"` / `volume_unit="unknown"` defaults noted. A closing paragraph separates **write eligibility**, **an attempted write** and **durable contents**, and states that no database was opened |
| **AR-R2** | The producer-to-comparison trace omitted caller-added metadata, serialization, the `cached_sample` input and the delegated Tencent return, and the requested `U1`/`U2`/`U3` scope was missing | §6 now records that `compare_market_sources.py:50` stamps `volume_unit="hand"` **and** `amount_unit="yuan"` on the eastmoney probe and `:63` stamps `amount_unit="yuan"` on Sina, while the Tencent fallback deliberately stamps neither (`:58`) — **local caller assertions, not vendor proof, and they never reach the cache writer**; that `:70-73` serializes a four-key attrs whitelist plus `to_json(orient="split")` and `:188-191`/`:201-204` rebuild the frame, so the compared object is a **round-tripped reconstruction**; and that `cached_sample` (`:101-118`, profiled `:209-213`) is a **fourth** input reading stored rows read-only. Case C is restated as a **same-input reasoning example over a reachable shape** — *same loader is not same bytes* — and Finding 4 is marked conditional. §5 adds the **delegated** `_load_tencent_newfqkline_qfq_daily_bars` (`:779-827` from `:638`/`:655`), read and confirmed to build `"amount": None` at `:819`. New **§8.1** gives the `U1`/`U2`/`U3` scope from `smoke_checks.py` and the retained JSON: `U2` (`:1231-1240`) delegates to `provenance.derive_unit` (`_m2_pilot/provenance.py:100-132`, now pinned); `U3` (`:1299-1316`) is **stock-only**, PASS on **ten sessions** per stock, all ratios `1.0`, tolerance `0.01`; `sh000300` has **neither**, so index units are unaddressed; and the retained Sina checks **cannot certify** the Tencent, eastmoney, tonghuasun, index or cache paths |
| **AR-R3** | §9's proposal did not follow the actual quality-status flow: absent and all-null already both yield `None`/`ready`; `_refresh_stock_symbol` overwrites the flag at `:213-214`; and "guard behaviour unchanged" was asserted rather than analysed | The "treat all-null like absent" proposal is **withdrawn** — the builders already produce `None`/`ready` either way (`:1005`, `:925`), so the equivalence changes nothing. §9 now quotes `:213-214` and states that any change would have to alter what the `:195`/`:204-205` loop computes, **not** the selector or the normalizer, and that the benchmark path has no such overwrite and **no amount requirement**. The proposal is reduced to a **question conditional on a future policy decision and separate production authorization**; no rule or quality label is adopted. The validation condition is rewritten: **a flag change can change guard outcomes**, because `:465-477` tests `quality_status='ready'` on both sides, so any chosen semantics must state its intended effect on that clause **and** on the `:502-521` deletes and be validated against that intent. The two unrelated cleanups are demoted to observations and explicitly **not proposed** |

No agent, sweep, scratch script, output directory, new study, test, import, runtime call,
database access or Git action was used for this revision; the corrections rest on the short
static reads the review indicated, all pinned in §10.

**Stop: `proposed for review`.**
