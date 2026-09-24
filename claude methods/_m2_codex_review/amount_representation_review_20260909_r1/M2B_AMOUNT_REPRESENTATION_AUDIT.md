# M2b — amount representation audit: the two alias tables, and what actually reaches them

> **Status: `proposed for review`.** Static, existing-file offline analysis under the
> continuing offline authorization. **Nothing is adopted, changed or implemented.** §9's fix
> is a **proposal only**.
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
> Revision 1. Closes A-2/A-3 of `M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md`
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
`"amount": None` for **every** row (`daily_bar_cache.py:669-679`), so:

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

The same happens on the benchmark path for a different reason: F5 and F6 have no
amount-family column, `amount_col` is `None`, and `_normalize_index_bars` emits
`amount=None` with `quality_status="ready"` (`:998-1010`).

**Finding 3 (bounded, and reachable).** Three of the six inspected concrete paths (F3, F5,
F6) produce `ready` rows with a null `amount`. The selector never sees it because it tests
presence, not values.

---

## 6. Do the two modules disagree on the same input? — three cases

*Hand-worked reasoning examples over column shapes. These are **not** executed tests and
**not** observed vendor payloads.*

| Case | Input shape | `daily_bar_cache` | `source_comparison` | Disagree? | Reachable from an inspected caller? |
|---|---|---|---|---|---|
| **A** | `turnover` present, `amount` absent | selects `turnover` as amount | `missing_columns = ["amount"]` → `review_required` | **yes** | **no.** Only F2 carries `turnover`, and `:110` drops it before return. Pinned by `test_source_comparison.py:74-80` |
| **B** | both `成交额` and `amount` present, 成交额 leftmost | alias priority → `amount` | position → `成交额`, and `ambiguous_columns = ["amount"]` → `review_required` | **yes** | **no.** No inspected frame carries both |
| **C** | `amount` present, all values null (**= F3**) | `amount` selected; every row `amount=NULL`, `quality_status="ready"` | `missing_columns = []`, but every row non-finite in `NUMERIC` → `invalid_rows = n` → `review_required` | **yes** | **YES** — Tencent qfq, third in the default chain |

Case C is not hypothetical in a second sense: **both selectors are actually handed the same
frames.** `backend/scripts/compare_market_sources.py` — the only non-test caller of
`source_comparison` (`:173`, `:191-192`, `:204-205`, `:211-213`) — builds its probe frames
from the very same provider calls: tonghuasun `get_daily_bars` (`:43`),
`AkshareProvider().get_daily_bars` with `_load_tencent_qfq_daily_bars` as its fallback
(`:47`, `:57`), and `get_daily_bars_sina` (`:62`).

**Finding 4.** On the one reachable disagreement (C) the two modules give **opposite
verdicts on identical bytes**: the ingestion path stores `ready`, the comparison path
reports `review_required`. Neither is wrong on its own terms — they are answering different
questions — but the same frame is classified two ways, and only the comparison path says so.

---

## 7. Which layer sees it — related through actual calls only

| Layer | Reached by | What it does with a null-amount row |
|---|---|---|
| `_first_existing_column` | `daily_bar_cache.py:901`, `:982` | **Never sees it.** Presence-only |
| The upsert guard | `_upsert_bars` SQL, `:414-418` | **Protects.** `NOT (existing.quality_status='ready' AND existing.amount IS NOT NULL AND excluded.amount IS NULL)` — a null-amount row **cannot overwrite** a stored ready row that has a real amount. **Limit: it does not block the first insert** where no row exists |
| `source_comparison` | `compare_market_sources.py` only | **Detects.** `invalid_rows`, `missing_values["amount"]`, `review_required` |
| M1 `chk_units` | `staging_gate.py:526` → `acceptance_runner.py:163`, body `:188-208` | **Quarantines.** `verifiable_sql` requires `amount IS NOT NULL AND amount > 0` (`:191-194`), so null-amount rows fall out of `verifiable` into `quarantined` and are never counted `contradicted`. The implied-price test `amount ÷ shares` vs `[low×0.98, high×1.02]` (`:204-205`) is simply not applied to them |
| M2 `U1` | retained `checks.json`, `smoke_checks.py` | **Never sees these rows.** `U1` runs on the smoke's decoded klc research rows, not on `daily_bar_cache` contents. It would fail such a row — it requires positive volume **and** amount — but it is not in this path |
| `backtest/engine._signal_average_price` | `engine.py:543-567` | **Bypasses silently.** `amount = float(signal_context.get("amount") or 0)`; with 0 it takes the typical-price fallback at `:559-567`. Exactly the trade named in the `:157-159` comment |

**Finding 5.** A null `amount` is **quarantined by the M1 unit gate, detected by the
comparison module, blocked from overwriting good data by the upsert guard, and silently
degraded by the backtest**. Nothing rejects it at write time. That is the full inspected
picture; no gate was executed and no historical verdict is reclassified.

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

---

## 9. Bounded findings, and one minimal fix — **proposal only, not implemented**

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
error: a present-but-null `amount` is stored `ready` while the comparison module calls the
same frame `review_required` (§6), and three of six paths produce it (§5).

**Minimal possible fix, described only.** The smallest change consistent with everything
above would be, at the two `daily_bar_cache` call sites, to treat *an amount column with no
usable value in the retained window* the same way an absent one is treated — i.e. record
that fact on the row rather than emitting `ready` with a silent `NULL`. Two narrower
variants exist: drop the inert `required` parameter (§2.1 property 4), and align the
benchmark tuple with the stock tuple. **None of this is implemented, designed in detail,
or recommended for adoption**; each touches production ingestion and would need its own
scope review.

**Future validation condition, stated so a later reviewer can test rather than trust.** Any
such change should be accepted only if it demonstrably (i) leaves F1, F2 and F4 rows
classified exactly as today, (ii) changes only the flag on F3/F5/F6 rows and not their
values, and (iii) leaves the `:414-418` upsert guard's behaviour unchanged. **That
condition is written for a future authorized task; nothing about it is executed now.**

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

**Stop: `proposed for review`.**
