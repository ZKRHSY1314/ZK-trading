# `daily_bar_cache` write-path audit — who can insert, replace, update or delete, and what guards them

> **Revision 2** — status `proposed for review`. Task `CACHE-WRITE-R1-20260909`, correcting
> revision 1 (`1dbfb9af…`) against `M2B_CACHE_WRITE_PATH_CODEX_REVIEW.md` (`150c1517…`) findings
> **CW-R1 … CW-R3**: the generic-SQL helper classification (§7.1), the real `_upsert_bar` /
> `_upsert_bars` callers and the CLI reset default (§4), the `import_runs` record (§4.1), the
> universal evidence-exhaustion claims (§10), and an accurate disclosure of the one fixture byte
> read (§4). The guard and sequencing analysis is preserved. The original assignment was
> `CACHE-WRITE-PATHS-20260909`, from `M2B_REFERENCE_BASIS_LINEAGE_CODEX_REVIEW_R2.md`
> (`c8a36eb0…`), under the user's continuous offline-analysis authorization.
>
> **Static source analysis only.** Files read **as text**. **No SQLite open of any kind, including
> in-memory. No import of any inspected module. No provider, service, decoder, replay, network,
> retrieval or capture. No migration or importer execution. No raw legacy input dataset, credential
> or token file read.** No scratch script, no output directory, no numerical study.
>
> **Scope.** This is a **current-code inventory**. It does **not** establish that any path ran on
> any retained reference row, and it asserts no overwrite, deletion or defect in retained data.
> **P1 open, U-6 deferred, every eligibility result false, source capability FAIL (including the
> retained EV6 disagreements), both capture authorizations consumed.** Not M2 completion.
>
> **Headline, by named group rather than a ratio.** The `ready`/`qfq` predicate lives on **two
> statements only** — the `ON CONFLICT` arms of `_upsert_bar` and `_upsert_bars`. It is
> **structurally absent** from the three migration `UPDATE`s, from `reset_knowledge()`'s
> unqualified `DELETE FROM daily_bar_cache` and from the demo-seed `INSERT OR REPLACE`; and it is
> **inert by sequencing** for rows removed by the two real-row `DELETE`s that run immediately
> before the batch upsert in the same connection. The W-numbering below groups statements of
> different kinds — DDL, guarded `ALTER`s, an indirect wrapper, and W-2a/b/c's several deletes —
> so **it is a map, not a coverage measure**, and no proportion should be read off it.

---

## 1. Search scope, patterns, and hashes

**Searched:** `backend/app` and `backend/scripts`, `*.py`, as text. `backend/tests` is **outside
this scope** — test fixtures do insert into this table, and they are not part of the runtime
inventory. Also read: the table's DDL and the `KNOWLEDGE_TABLES` list in the same store module.

**Patterns used** (case-insensitive, multiline where noted):

* `daily_bar_cache` — 60 matching files repository-wide, narrowed to `app`/`scripts`
* `(INSERT\s+(OR\s+REPLACE\s+)?INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM)\s+daily_bar_cache` (multiline)
* dynamic-SQL sweep: `to_sql`, `f"INSERT`, `f'INSERT`, `f"DELETE`, `f'DELETE`, `f"UPDATE`,
  `f'UPDATE`, `f"REPLACE`, `{table}`, `{table_name}`, `% table`, `DROP TABLE`, `TRUNCATE`
* `DailyBarCacheService`, `refresh_bars`, `refresh_symbols`, `refresh_benchmark_bars`,
  `_refresh_stock_symbol`, `_upsert_bar`, `_upsert_bars`, `reset_knowledge`, `KNOWLEDGE_TABLES`
* `adjustment_mode` (used only to locate candidates — a mention is **not** a writer)

**Files relied upon.** Worktree versus `HEAD` (`73f266d`) recorded; none was modified.

| File | SHA-256 | vs `HEAD` |
|---|---|---|
| `backend/app/data/daily_bar_cache.py` | `90ec7bd0038147bd48ef5f9e3a354d720eeed4d05443b0a9a93039e71d7ff533` | unmodified |
| `backend/app/storage/sqlite_store.py` | `35b2e6f9d345c6a3c4b0bf3105b51827704acbebc72ebd649d06d8221394adbe` | **MODIFIED** (135 insertions / 1 deletion uncommitted) |
| `backend/scripts/import_legacy_data.py` | `9253d7345190a325f336d426af8597ab225f97872b7b04680fbb9a5e36457616` | unmodified |
| `backend/app/data/akshare_provider.py` | `375f34adc34adf131e44194002dc96242c45269fd445b693f2eb0bcdc84acccf` | unmodified |
| `backend/app/data/tonghuasun_provider.py` | `3cd5a67c014925454d4896d5abe456430f9e758d06a4babab146a097265310f3` | unmodified |
| `backend/app/config.py` | `1cb7dd7bc7d48593eda083db80d31f1d712323c49df74c4d0d1f57416129e7d7` | unmodified |
| `backend/app/data/universe_backfill.py` | `d49ed1de1267550633c9cd12a428fa3af233ae4920f9891915df41612d10e453` | unmodified |
| `backend/app/learning/phase_replay.py` | `67e0061859fe3b5894d7077f8edc5ff4a83b88b08051fa2fcd645ab8cdab94ce` | unmodified |
| `backend/app/data/market_history.py` | `bd175ffa371dcdbf2fee305791e4448908944d3c28ce97a96dc0d0cf27fb1861` | unmodified |
| `backend/app/data/snapshot_builder.py` | `8e9d4fc5da8875006d7dbcbd36a8af0059e38f750b7cf4ea4c7f9e916b1d7586` | unmodified |
| `backend/app/api/routes.py` | `491c28756550aff0aa5c804c53f8171d9c529c30191daf6747ac6d964a499eb3` | **MODIFIED** (uncommitted) |
| `backend/app/control_plane/service.py` | `48890e08fb23d9b45fee579b9fe9b5bfb331be880d47e8d5e88f2419aacba3ce` | **MODIFIED** (uncommitted) |
| `backend/app/research/offhour.py` | `fadd607da1d449ab5fa71d7ee8337092afa3c165831bc0e1a95c7d1e95fc3534` | unmodified |
| `backend/scripts/compare_market_sources.py` | `a8e08c59d356a53057d2085ea689e6b8c18828616d090e52f8157c653c7738f2` | unmodified |
| `backend/scripts/market_history_refresh_loop.py` | `8699c2d80814d29403f09bb4cf0ef872384c0a3df2d4ae49f4e90fbffd397fad` | **MODIFIED** (uncommitted) |

Four files carry uncommitted user changes and **were left exactly as found**. For
`sqlite_store.py` the three migration `UPDATE`s and the DDL were previously verified
**byte-identical between `HEAD` and the worktree**; for the other three the uncommitted state is
noted but their roles here are indirect-caller classification only.

The prior lineage audit's eight source hashes are unchanged — the six project files and both
AkShare files listed there re-verify.

---

## 2. Schema facts the guard analysis depends on

`sqlite_store.py:922-939` — `CREATE TABLE IF NOT EXISTS daily_bar_cache`:

```sql
    source TEXT NOT NULL,
    adjustment_mode TEXT NOT NULL DEFAULT 'unknown',
    volume_unit TEXT NOT NULL DEFAULT 'unknown',
    quality_status TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, trade_date)
```

* **Two label columns default to `'unknown'`**, so any writer omitting them yields `'unknown'`.
* **`UNIQUE(symbol, trade_date)`** is the conflict target every guarded upsert relies on.
* **Two timestamp columns, two conventions in practice.** The DDL defaults both to SQLite
  `CURRENT_TIMESTAMP`; the service's upserts instead supply `updated_at` from naive local
  `datetime.now().isoformat(timespec="seconds")` (`daily_bar_cache.py:388` for W-1, `:447` for W-2,
  used in the row tuple at `:496`), while
  the demo-seed path supplies `CURRENT_TIMESTAMP` (`import_legacy_data.py:634`). So **`updated_at`
  is not on a single clock across writers**, and `created_at` and `updated_at` are not comparable
  as a difference.

---

## 3. The guard, stated exactly

Both service upserts carry the same two-clause predicate. `daily_bar_cache.py:406-418`
(identically at `:465-477`):

```sql
            WHERE NOT (
                daily_bar_cache.quality_status = 'ready'
                AND daily_bar_cache.adjustment_mode = 'qfq'
                AND (
                    excluded.quality_status != 'ready'
                    OR excluded.adjustment_mode != 'qfq'
                )
            )
              AND NOT (
                  daily_bar_cache.quality_status = 'ready'
                  AND daily_bar_cache.amount IS NOT NULL
                  AND excluded.amount IS NULL
              )
```

**What it is.** A predicate on the `DO UPDATE` arm of `ON CONFLICT(symbol, trade_date)`. It can
only take effect when (a) a row with that key **is present**, and (b) the statement reaches the
conflict arm. It protects a `ready`+`qfq` row from a weaker-labelled write, and a `ready` row that
has an `amount` from one that would null it.

**What it cannot be.** It is not a table constraint, not a trigger and not a check on `DELETE`. Any
statement that is not this `ON CONFLICT` upsert is unaffected by it, and any row removed before the
upsert runs presents no conflict for it to guard.

---

## 4. Operation and guard matrix

`app` + `scripts` only. "Record" = whether that path durably records an ingestion/migration event.

| # | Path | Trigger / caller | Operation | Columns supplied / defaulted / preserved | `updated_at` clock | Guard | Record |
|---|---|---|---|---|---|---|---|
| **W-1** | `_upsert_bar` `daily_bar_cache.py:387-442` | **`_save_error_bar` at `:539` — its only caller in this file.** Corrected: revision 1 also listed `refresh_benchmark_bars`, which in fact calls `_upsert_bars` at `:366`. So W-1 writes only the `ERROR`-dated sentinel row | `INSERT … ON CONFLICT(symbol,trade_date) DO UPDATE … WHERE …` | 13 supplied; `created_at` **defaulted** on insert and **preserved** on update (absent from both the column list `:391-392` and the `DO UPDATE SET` list `:395-405`) | naive local `datetime.now()` | **applied** (`:406-418`) | none |
| **W-2** | `_upsert_bars` `daily_bar_cache.py:444-523` | **both real-bar paths**: `_refresh_stock_symbol` at `:278` (all three stock sources) **and `refresh_benchmark_bars` at `:366`** (index). So **every real bar write — stock and benchmark — traverses this path and the deletes below** | same INSERT/guard shape (`:449-478`), via `executemany` at `:522` | as W-1 | naive local `datetime.now()` | **applied at `:522`**, but see W-2a/W-2b | none |
| **W-2a** | incomplete-session delete `:507-511` | inside `_upsert_bars`, when `_incomplete_session_date()` returns a date — i.e. **only on a weekday before 15:15 local time**, in which case it returns **today** (`:1042-1046`) | `DELETE … WHERE symbol = ? AND trade_date >= ?` | — | — | **none.** Removes **real dated rows**, with no predicate on label or status. **Bounded reach:** the parameter is today's date, so the range covers today and any future-dated row — not historical sessions | none |
| **W-2b** | fallback-row delete `:512-521` | inside `_upsert_bars`, when every incoming bar is `qfq` | `DELETE … WHERE symbol = ? AND source = 'sina.cn.kline_daily_fallback' AND adjustment_mode = 'unknown'` | — | — | **none** (targeted by source+label, but outside the upsert predicate) | none |
| **W-2c** | ERROR-sentinel deletes `:255-258`, `:344-348`, `:423-427`, `:502-505` | degraded-cache and pre-upsert cleanup | `DELETE … WHERE symbol = ? AND trade_date = 'ERROR'` | — | — | not applicable — **sentinel key only**, cannot reach a real dated row | none |
| **W-3** | `_save_error_bar` `:525-539` | source-exhaustion error handling | the sole caller of W-1; writes an `ERROR`-dated sentinel row (`source='error'`, `quality_status='error'`) | as W-1 | as W-1 | inherits W-1 | none |
| **W-4** | DDL `sqlite_store.py:922-939` | `SQLiteStore.init()` | `CREATE TABLE IF NOT EXISTS` | defines the `'unknown'` and `CURRENT_TIMESTAMP` defaults | — | not applicable | none |
| **W-5** | guarded `ALTER`s `:1961-1969` | `init()` | `ADD COLUMN adjustment_mode / volume_unit … DEFAULT 'unknown'`, inside `try/except sqlite3.OperationalError: pass` | adds columns with `'unknown'` | — | not applicable | none |
| **W-6** | migration `UPDATE` `:1976-1991` | `init()` | sets `adjustment_mode` from the `source` string where it is `'unknown'` | **only `adjustment_mode`**; **neither timestamp touched** | — | **none** | none |
| **W-7** | migration `UPDATE` `:1992-2007` | `init()` | sets `volume_unit` from `source` where it is `'unknown'` | only `volume_unit`; no timestamp | — | **none** | none |
| **W-8** | migration `UPDATE` `:2008-2015` | `init()` | sets `quality_status = 'review_only_unknown_adjustment'` for `sina.cn.kline_daily_fallback` rows currently `ready`/`ok`/`valid` | only `quality_status`; no timestamp | — | **none** | none |
| **W-9** | `reset_knowledge()` `:2032-2035` | `import_legacy_data.py:473-474`, when `reset` is true. **Entry mode decides:** the CLI's `--reset` is `action="store_true"` and `main()` passes `reset=args.reset` explicitly (`:762-772`), so **ordinary CLI invocation does not reset**; only a **direct Python call omitting the argument** inherits the `import_all(reset: bool = True)` default (`:465`). The file's own comment at `:756-761` records that the wipe "has to be asked for by name" | `DELETE FROM daily_bar_cache` — **no `WHERE` clause at all** | removes every row | — | **none** | **none of its own** — see §4.1: `reset_knowledge()` uses its own connection, committed before the import block, so a later `import_runs` row neither covers it transactionally nor records that it ran |
| **W-10** | demo-seed insert `import_legacy_data.py:628-648` | `import_all` → `if demo_seed_path.exists()` (`:502-503`) → `for item in demo_seed.get("demo_daily_bars", [])` (`:624`) | `INSERT OR REPLACE INTO daily_bar_cache(…)` | **11 supplied; `adjustment_mode` and `volume_unit` omitted → `'unknown'`.** `source='demo_seed_fixture'`, `quality_status='demo_fixture'`. `created_at` is **reset**, not preserved — `INSERT OR REPLACE` deletes and re-inserts | **SQLite `CURRENT_TIMESTAMP`** | **fully bypassed** — SQLite conflict resolution, not an `ON CONFLICT … WHERE` arm | **coarse, at run level only** — see §4.1 |

**W-9's reach, established from the list itself.** `daily_bar_cache` is entry 46 of the 71-name
`KNOWLEDGE_TABLES` (`sqlite_store.py:1728-1800`), which `reset_knowledge` iterates:

```python
    def reset_knowledge(self) -> None:
        with self.connect() as conn:
            for table in KNOWLEDGE_TABLES:
                conn.execute(f"DELETE FROM {table}")
```

The importer's own comment at `:756` and its warning text at `:767` describe this as deleting all
71 knowledge tables "including `daily_bar_cache`", consistent with the list.

### 4.1 One coarse durable record does exist — at run level, not row level

Revision 1's matrix said every path records nothing. **That was inaccurate for a successful
importer run.** `import_legacy_data.py:744-750`, inside the `with store.connect() as conn:` block
opened at `:480`:

```python
        status = "success" if has_legacy else "demo_only"
        conn.execute(
            """
            INSERT INTO import_runs(source_dir, status, summary_json)
            VALUES (?, ?, ?)
            """,
            (str(legacy_dir) if has_legacy else "demo_seed", status, dump_json(summary)),
        )
```

Its DDL (`sqlite_store.py:27-33`) is `id, source_dir, status, summary_json, created_at DEFAULT
CURRENT_TIMESTAMP`.

**What that record carries:** a timestamp, the resolved legacy directory or the literal
`"demo_seed"`, a two-valued status (`success` / `demo_only`), and `summary` — the per-table
**import counts** accumulated through `import_all`.

**What it omits, and why it does not close L-5 or L-6:**

* **No `reset` flag.** Nothing in the row says whether W-9 ran. And `reset_knowledge()` opens its
  **own** connection (`sqlite_store.py:2033`) and commits at `:473-474`, **before** the import
  block begins at `:480` — so the record is in a different transaction. A run that wiped the table
  and then failed before `:744` would leave the deletion committed with **no `import_runs` row at
  all**.
* **No cache-row provenance.** No symbols, dates or affected keys; and the demo-bar loop
  (`:624-648`) increments no `summary` key, so a run that wrote cache rows and one that wrote none
  are **indistinguishable** in this record.
* **No invocation or code pin, and no source-response metadata** — none of the fields the lineage
  audit's L-1 to L-4 name.

So this is a **coarse run event, not per-row historical binding**. It does not show W-10 wrote any
row, does not evidence migration execution, and leaves L-5 and L-6 open.

**W-10's activation predicates, and exactly what was observed.** The code requires all of:
`demo_seed_path.exists()` (`:502-503`); `read_json` parsing successfully (`:504`);
`demo_seed.get("demo_daily_bars", [])` yielding at least one item (`:624`); and that item's `bars`
yielding at least one record (`:626`). Only then does the statement at `:628-648` execute.

**Disclosure of the operation actually used, corrected.** Revision 1 said the fixture's "contents
were not read and no dataset was opened". **That was wrong as written.** From this session's
command history, two operations were run against
`backend/configs/demo_seed.json`: `ls -l`, giving existence, a 2,531-byte size and an mtime; and
**`grep -c 'demo_daily_bars'`, which opened and read the file's bytes** and returned the line count
`1`. No content was printed and no symbol, date or price was seen or reported — but a byte read did
occur, outside the assignment's source-only scope. **That limited departure is recorded here
plainly; this correction does not retroactively authorize it**, and the fixture has **not** been
re-opened for this round.

**What that operation can and cannot support.** It was a **textual line match**, not a parsed-JSON
structure test. It shows the literal string `demo_daily_bars` occurs on one line of that file. It
does **not** establish that the string is a JSON key rather than other text, that the array is
non-empty, that any inner `bars` list is non-empty, or that the earlier import steps succeed — so
it does **not** establish that any `INSERT` executes. Revision 1's "contains a `demo_daily_bars`
key" overstates it. **No inference of an actual W-10 write is drawn.**

**The private legacy corpus was never touched.** `settings.legacy_data_dir` — the importer's other
input — was not listed, opened or read at any point.

---

## 5. Two guard limitations, stated conditionally

**(a) Sequencing makes the guard inert for deleted-then-reinserted rows.** Inside one connection
block `_upsert_bars` executes, in order: the ERROR-sentinel delete (`:502-505`), the
incomplete-session delete when armed (`:507-511`), the fallback-row delete when armed
(`:512-521`), then the guarded `executemany` (`:522`). **If** a row lies in the deleted range, it is
removed unconditionally, and a replacement carrying any label then inserts cleanly because no
conflicting row remains for the `WHERE NOT (…)` arm to inspect. So the `ready`/`qfq` protection is
**structurally unavailable** on that path — not overridden, simply not reached.

**How far (a) reaches, from the arming condition itself.** `_incomplete_session_date()` is four
lines (`:1042-1046`):

```python
    def _incomplete_session_date(self) -> str | None:
        now = datetime.now().astimezone()
        if now.weekday() < 5 and (now.hour, now.minute) < (15, 15):
            return now.date().isoformat()
        return None
```

So W-2a is armed **only** during a weekday before 15:15 local, and the date it supplies is
**today**. Its `trade_date >= ?` range therefore covers **today and any future-dated row, never a
prior session**. That makes W-2a a narrow intraday cleanup rather than a wide-reach deletion — a
meaningful bound on §5(a), and the reason the guard's inertness there does not extend to historical
dates. W-2b remains bounded by its own `source` and label predicates. **Neither observation says
anything about what happened to any retained row.**

**(b) `INSERT OR REPLACE` never enters the guarded arm.** W-10 uses SQLite's replace conflict
resolution, which deletes the conflicting row and inserts the new one. **If** it were to run
against a key already present, the outcome would be a row with `adjustment_mode='unknown'`,
`volume_unit='unknown'`, `source='demo_seed_fixture'`, `quality_status='demo_fixture'` and a reset
`created_at`. A further conditional consequence, traced for completeness: such a row would **not**
be repaired by W-6, because `'demo_seed_fixture'` is absent from W-6's `WHERE` source list, so it
would remain `'unknown'`; and `quality_status='demo_fixture'` is not `'ready'`, so the retained
reference extract's filter would exclude it.

**Neither (a) nor (b) is a claim about retained data.** No path above is shown to have run against
any retained reference row, and no overwrite, deletion or defect in the retained rows is asserted.

---

## 6. Correct classification of the modules the review named

| Module | Role for **this** table | Basis |
|---|---|---|
| `universe_backfill.py` | **indirect writer + reader.** No direct write SQL | constructs `DailyBarCacheService` (`:16`, `:61`) and calls `refresh_symbols` (`:822`, `:834`); reads via `SELECT` at `:628`, `:739`, `:791` |
| `learning/phase_replay.py` | **read-only consumer** | `FROM daily_bar_cache` at `:169`. The string `"daily_bar_cache.qfq"` at `:142` is a provenance **label**, not SQL |
| `snapshot_builder.py` | **neither writer nor reader of this table** | contains **no** `daily_bar_cache` reference. Its `"akshare.stock_zh_a_hist"` at `:93` is a source string — precisely the kind of mention that does not make a writer |
| `market_history.py` | **different tables — out of scope** | defines the separate `daily_bars` / history schema; its `adjustment_mode` occurrences (`:91`, `:111`, `:129`, `:140`, `:156`, `:182`) belong to those tables, not this cache |
| `compare_market_sources.py` | **reader** | `SELECT` at `:113`, `:122`; builds a store-less `DailyBarCacheService` via `object.__new__` (`:55`) to reach loader helpers, so it does not traverse the upsert path |
| `market_history_refresh_loop.py` | **indirect writer + reader** | calls `cache_service.refresh_symbols` (`:482`); reads under a table whitelist (`:114`, `:118`, `:368`) |

**Other indirect refresh callers** (each reaching W-1/W-2 through the service, none writing
directly): `api/routes.py:5651-5653` (`refresh_bars`), `control_plane/service.py:1196-1219`
(`refresh_symbols`), `research/offhour.py:2372` (`refresh_bars`) and `:2462`
(`refresh_benchmark_bars`).

---

## 7. Limits of this inventory

1. **Completeness is not provable by text search, and there are three generic execution
   surfaces, not one.** Revision 1 called `fetch_all` and `fetch_one` read-only. **They are not.**
   `sqlite_store.py:2044-2051` passes the caller's SQL straight to `conn.execute(sql, params)` on
   the writable connection returned by `connect()`, with **no SELECT check and no `query_only`
   pragma**; calling `.fetchall()` / `.fetchone()` afterwards constrains nothing about the
   statement already executed. So the surfaces are `connect()` (`:2022`, **268 call sites across 50
   files** in `app`/`scripts`) **plus** those two helpers. Every call site inspected here uses the
   helpers for `SELECT`s, which is a fact about **usage**, not a **capability** boundary — they are
   not a safety guarantee and must not be cited as one. The dynamic-SQL sweep found no
   table-name-interpolated write other than W-9's `KNOWLEDGE_TABLES` loop, so the inventory is
   complete **for the patterns listed in §1** — not provably complete in general, and this audit
   does not enumerate every caller of any surface.
2. **Current code only.** Every row of §4 describes the inspected files as they now stand. Nothing
   here binds a path to a historical row, and four of the relied-upon files differ from `HEAD`
   today — a standing reminder that present contents are not a record of what executed.
3. **No trigger or constraint scan beyond the DDL read here**; no database was opened, so no
   deployed schema, trigger or index state is verified.
4. **`backend/tests` excluded** by the task's scope. Test fixtures do insert into this table.
5. **W-10's fixture: byte-read, textually, once.** `ls -l` plus one `grep -c` line count, as
   disclosed in §4. Its structure was never parsed and no content was printed, so which symbols or
   dates it names — and whether the relevant collections are non-empty — is unknown here.

---

## 8. What this adds to L-5 / L-6, and what it still cannot establish

**Adds.**

* **L-5 gains a bounded candidate set, and one coarse record.** The lineage audit could name no
  writer inventory; the current paths are now mapped with their triggers, columns, clocks and guard
  status. On records, revision 1 said uniformly "nothing" — **corrected**: a successful importer run
  does insert an `import_runs` row (§4.1). But that row is **run-level**: no `reset` flag, no
  affected cache keys, no invocation or code pin, no response metadata, and it cannot distinguish a
  run that wrote cache rows from one that wrote none. **No path records row-level provenance**, which
  is why L-5 stays open.
* **L-6 gains two label-setting paths beyond those already known.** W-10 can set both label columns
  to `'unknown'` by omission while bypassing the guard, and W-9 can remove rows outright. So the
  candidate origins for any given stored label are broader than the writer-default-versus-W-6 pair
  the lineage audit described — which **widens** the ambiguity rather than narrowing it.
* **A concrete reason the guard cannot be relied on as a historical invariant, with its reach
  measured.** §5(a) and §5(b) show two structural routes by which a `ready`+`qfq` row's protection
  is simply not reached. So "the guard exists" does not license "a `ready`+`qfq` row can only have
  been replaced by another `ready`+`qfq` row". The reaches differ sharply, and both are now bounded
  from the code: W-2a can only touch **today and later** dates (armed only on a weekday before
  15:15), W-2b only `sina.cn.kline_daily_fallback` rows still labelled `'unknown'`, while **W-9 and
  W-10 carry no date bound at all**.
* **A second clock convention.** W-10 writes `updated_at` from SQLite `CURRENT_TIMESTAMP` while
  W-1/W-2 write naive local time — reinforcing, from a new direction, why `updated_at` cannot be
  read as a uniform timeline.

**Still cannot establish.**

* **Which path produced or touched any retained row.** No path is shown to have run; no assertion
  is made in either direction.
* **Whether W-6, W-9 or W-10 ever executed against this database.** The importer's `reset` default
  and the fixture's presence are *activation conditions*, not execution evidence.
* **Anything about upstream response semantics or the true price convention.** This audit reads
  writers, not data sources; the lineage audit's C-1…C-3 resolving-evidence types are unchanged.
* **The reference basis (Q-3 / condition 4).** Unchanged and still unsatisfied. Certification stays
  withheld — **fail-closed, not disproved.**

---

## 9. Preservation

**Created:** `claude methods/M2B_CACHE_WRITE_PATH_AUDIT.md`. **Also written, within the authorized
scope:** the two scoped sentences in `claude methods/M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md`
(§10's ordinary-rewrite inference and its "existing local files" phrasing), whose new hash is
reported in the handoff. **Nothing else was created or modified.**

Verified after the audit: all fifteen source files in §1 are byte-identical to their pre-audit
state, including the four with uncommitted user changes; the accepted G1 delivery is **46/46
byte-identical** to the frozen `_m2_codex_review/g1_review_20260909_r3_doc1/reviewed_delivery`; the
five accepted G3 r2 pins, the retained reference extract, the basis module and its tests, both
`basis_eval_*` outputs, the five smoke producers and `closure_r2abc_v2.py` all match; the retained
study `65fbe917…`, the readiness assessment `de130cf0…`, the P1 proposal `71e0dc52…`, goal
`f8b699e5…`, request `c39726d0…`, all G1/G3/U-6 acceptance and review documents including
`c8a36eb0…`, all reviewer snapshots and the coordination state are unchanged. No SQLite open of any
kind, no module import, no provider, network, capture, replay, decoder, migration or importer
execution. Git was not staged, committed or pushed.

---

## 10. Remaining existing-file evidence — and the honest answer

**This search has not identified a further concrete existing-file source that would resolve the
historical binding, and the artefacts reviewed here lack the required link.** That is the bounded
conclusion; it is **not** a proof that no such file exists — §7(1) states that completeness is not
provable by text search, and neither this audit nor the lineage audit exhausted the local tree.
Nor does it imply the wider M2 workflow should stop. The one question this audit might have deferred
— what arms W-2a, the single unguarded real-row deletion on the refresh path — was four lines long,
so it is answered in §5(a) rather than proposed as work.

**Named, not requested: what would actually close L-5.** **Row- or batch-level** ingestion
provenance — statement identity, writer, arguments and code version, bound to the affected keys and
written at the time. `import_runs` (§4.1) shows the codebase already writes a coarse run event, so
the gap is specifically the **row-level** binding: that record names no cache key, no `reset` state
and no code pin, and cannot be reconstructed from the existing columns. It is absent from the
artefacts inspected here and must **not** be presumed absent from every uninspected local file.
Producing it is a change to what future ingestion writes. **No database access, re-extract, upstream
query or new data is requested.**

**Not worth doing.** Another documentation rewrite of either audit; further price-relation families
over the same intervals; or an exhaustive enumeration of the 268 raw-connection call sites, which
would consume the whole surface without producing evidence about retained rows.

**Stop: `proposed for review`.** This audit certifies nothing, adopts nothing and authorizes nothing.
