# M2b — Bounded three-symbol real-source verification request

Status: **boundary 1a technically VALIDATED by Codex for the offline scope** (`M2B_1A_ACCEPTANCE_CODEX.md`, 2026-09-08; Sections 12-15). Validation covers the offline engineering path only: it is a reviewer's technical verdict on this bounded stage, not user authorization for live work and not a claim that M2 is complete. Boundary 1b remains **`proposed`, unauthorized and not executed** **`proposed`, unauthorized and not executed**. Stated precisely, because an earlier version of this line asserted both at once: the offline code of boundary 1a exists under `claude methods/_m2_smoke/` and its tests pass, and **nothing has been fetched, no request has been issued, no `tmp/` or evidence directory has ever been created, no service was started, and nothing was staged, committed or pushed.** This document authorizes no call, download, production change, service, commit, push or promotion; boundary 1b requires the user's separate instruction.

Prepared by Claude on 2026-09-07 in response to `M2A_ACCEPTANCE_CODEX.md` ("Next stage: prepare bounded real-source verification"), then revised the same day after an adversarial multi-lens review of the draft (technical accuracy, safety/protocol, acceptance rigor, documentation consistency, one skeptic per finding, one completeness critic); the corrections are folded in below rather than listed separately. Baseline at preparation: branch `codex/control-plane-refactor`, HEAD `73f266d`, index empty, no `staging/` or `tmp/` directory, no backend service or refresh loop running; `test_m2a.py` **79 cases, 0 unexpected, exit 0** reconfirmed locally on 2026-09-07; production database metadata identical to the acceptance table (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B).

M1 and M2a stay technically `validated` and are not reopened. M2a validated the **offline** runner on synthetic envelopes; **the live Sina decoder and the live transport have never been exercised and are not validated**. This request is the smallest step that can change that. It is deliberately not the 52-symbol pilot, and nothing in it leads to training.

## 1. Purpose and non-purpose

Purpose — answer, with five captured real responses, the questions M2a could not answer offline:

| # | Open question (`Qn` = item n of the numbered list "Unresolved live-data questions" in `M2A_OFFLINE_PILOT_RUNNER.md`; the same labels are used in Sections 6 and 7) | How this smoke answers it |
|---|---|---|
| Q1 | Does the live raw response carry `amount` for a stock? | Decode the real `klc_kl.js` payload and check the `amount` key on every row (D2, U1) |
| Q3 | Does the adapter's post-processing drop legitimate sessions? Two mechanisms: `drop_duplicates` on OHLCVA (`stock_zh_a_sina.py:221-223`) and the outer merge with the outstanding-share series followed by `ffill`/`dropna` (`:202-205`, `:228`) | Replay the installed adapter offline on the captured bodies and diff its output against the raw decode (R1); measure both mechanisms on the raw decode (C4) |
| Q4 | Is the observed URL set stable and exactly the raw path? | Compare served URLs with the adapter-derived expected set (S1); confirm no factor endpoint was touched (B1) |
| Q5 | Do index responses match the assumed shape? | Decode the real index payload and record its key set and decoder branch (D2, benchmark column); replay `stock_zh_index_daily` on it (R1) |
| new | Does Sina serve BJ history under the `92xxxx` code before 2024-08-12? | Earliest decoded date for `bj920000`, or the documented non-service outcome (C2) |
| new | Does the vendor JS decode routine work on real bodies? | The captured bodies are the validation sample the decoder lacks (D1, S2, R1) |

Scope note: the smoke proposed in the M2a document covered questions 1, 4 and 5 only. This request additionally answers question 3 and the two new questions because the same five bodies answer them at no extra request cost. Q2 (real vendor limits) stays out: it is **not** a goal and is not measured; five paced requests say nothing about a quota.

Not a purpose: collecting the pilot, populating any durable store, running the M1 gate, stamping a basis label, measuring throughput, or proving anything about the other 49 symbols, the corpus, feature readiness, models or strategy.

## 2. Symbol selection — from the unchanged approved manifest

Manifest: `claude methods/_m1_closure/pilot_symbols.csv`, sha256 `97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe`. Eligible-session counts come from the pinned calendar (`backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json`, sha256 `f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656`, re-hashed 2026-09-07): research 2023-09-04..2026-09-04 = **728** sessions; warm-up 2022-08-24..2023-09-01 = **250** sessions.

| Role | Manifest symbol | Adapter symbol | Name | Stratum | Eligible research / warm-up | Rationale |
|---|---|---|---|---|---|---|
| Ordinary stock | `SH600011` | `sh600011` | 华能国际 | `ordinary_control` | 728 / 250 | Listed 2001-12-06, so the whole 978-session window is owed. Local cache (read-only probe 2026-09-07): 538 ready rows 2024-06-21..2026-09-04 with **0 null `amount`** (sources `akshare.stock_zh_a_hist`, `akshare.stock_zh_a_daily`, `tonghuasun.local.quotes.candle`; basis `qfq`; unit `hand`), which gives a non-null local reference for the amount/volume semantics checks. SH main board, liquid, annual dividend payer. |
| BJ stock | `BJ920000` | `bj920000` | 安徽凤凰 | `bj_code_history` | 728 / 250 | Earliest BJ listing in the manifest (2020-12-23). Local history begins exactly **2024-08-13**, the `92xxxx` code boundary (501 rows, 0 null `amount`). One request settles whether Sina serves pre-boundary history under the new code for **this security** — the manifest's "mapping unknown" note. (Outcome, 2026-09-08: it does; see Section 22. That result is specific to `BJ920000` and does **not** decide the expected keys of the other six `bj_code_history` symbols, which were never contacted.) |
| Benchmark | `SH000300` | `sh000300` | 沪深300 | `benchmark` | 728 / 250 (benchmark contract) | Primary research benchmark; exercises the **separate** index adapter path and its distinct URL (Section 3). Local rows: 538, 2024-06-19..2026-09-02, source `akshare.stock_zh_index_daily`, basis `none`, `amount` null, unit `unknown`. |

Not selected, with reason: `SZ000002` has 507 of 538 local rows with null `amount`, which weakens the semantics cross-check; `SH000001` is interchangeable with `SH000300` for the index path, and `SH000300` was already named in the M2a proposal. Stocks in the `suspected_unit_switch` stratum are excluded on purpose: the STAR-board unit hypothesis is a pilot question, not a capability check.

**Job order:** `sh600011`, then `sh000300`, then `bj920000`. The two capability jobs run first so that the consecutive-failure stop (Section 3) can never skip them; the BJ job is the one whose non-service is itself an informative outcome (C2).

## 3. Endpoints and request budget — reconfirmed from the installed adapter, not inferred

Installed adapter: akshare **1.18.64** at `backend/.venv/Lib/site-packages/akshare/`. It must be the same version at run time (pre-flight F3).

| # | Adapter symbol | Exact URL | Adapter reference | What it returns |
|---|---|---|---|---|
| 1 | `sh600011` | `https://finance.sina.com.cn/realstock/company/sh600011/hisdata_klc2/klc_kl.js` | `stock/stock_zh_a_sina.py:177`; `stock/cons.py` `zh_sina_a_stock_hist_url` | JS-encoded daily history. After the vendor routine (its `_3466`/`O` branch, the only branch that emits `amount`): `date, open, high, low, close, volume, amount` per row; `prevclose` is an **optional per-record** key (`cons.py:649`), and `postVol`/`postAmt` appear only when the payload flags them. |
| 2 | `sh600011` | `https://stock.finance.sina.com.cn/stock/api/jsonp.php/var%20KKE_ShareAmount_sh600011=/StockService.getAmountBySymbol?_=20&symbol=sh600011` | `stock_zh_a_sina.py:196-208`; `cons.py` `zh_sina_a_stock_amount_url` | JSONP `[[date, value], …]`. The adapter names the value **`outstanding_share`** (万股, multiplied by 10,000 at `:207`), uses it for `turnover` (`:208`) and returns it as a column, which the project adapter then drops (`akshare_provider.py:110`). **It is not traded amount.** |
| 3 | `sh000300` | `https://finance.sina.com.cn/realstock/company/sh000300/hisdata/klc_kl.js?d=2020_2_4` | `index/index_stock_zh.py:302-303` (`params={"d": "2020_2_4"}`); `index/cons.py` `zh_sina_index_stock_hist_url` | Same JS encoding and routine. The adapter reads `date, open, high, low, close, volume` (`:310-315`). Which decoder branch the header selects, and whether an `amount` key is present, are recorded, not assumed. |
| 4 | `bj920000` | `https://finance.sina.com.cn/realstock/company/bj920000/hisdata_klc2/klc_kl.js` | as #1 | as #1 |
| 5 | `bj920000` | `https://stock.finance.sina.com.cn/stock/api/jsonp.php/var%20KKE_ShareAmount_bj920000=/StockService.getAmountBySymbol?_=20&symbol=bj920000` | as #2 | as #2 |

Production calls the same two functions, but the stock path with `adjust="qfq"`: `backend/app/data/daily_bar_cache.py:150` calls `get_daily_bars_sina(code, adjust="qfq")` → `akshare_provider.py:106` → `stock_zh_a_daily`, which additionally fetches `qfq.js` (`stock_zh_a_sina.py:270`) and **divides** the klc OHLC by that factor (`:293-296`). (It is the **hfq** branch that multiplies, `:254-257`. An earlier draft of this sentence said qfq multiplies; that was wrong, and B2 in Section 6 reads all three properties out of the installed source rather than restating them.) The smoke uses `adjust=""`, so it reproduces two of production's three stock GETs and the raw branch (`:219-232`). `daily_bar_cache.py:859-862` calls `stock_zh_index_daily` with the mapped lowercase benchmark symbol. Production's *fallback* index endpoint (`quotes.sina.cn … CN_MarketDataService.getKLineData`, `:864-877`) is a different service and is **out of scope**.

Budget:

| Layer | Stocks (2) | Benchmark (1) | Total |
|---|---|---|---|
| Symbol jobs | 2 | 1 | **3** |
| Provider calls (`stock_zh_a_daily(adjust="")`, `stock_zh_index_daily`) | 2 | 1 | **3** |
| HTTP attempts, no retries | 2 × 2 = 4 | 1 | **5** |
| Hard ceiling (≤ 3 attempts per request) | 12 | 3 | **15** |

Neither stock URL takes a date parameter (`stock_zh_a_daily` slices client-side at `:220`); the index URL carries only the adapter's fixed `d=2020_2_4` query (`index_stock_zh.py:302`), whose semantics are unknown and which the smoke does not vary — whether it bounds the served history is answered by C3, not assumed. Research and warm-up therefore come from the same single fetch per symbol at no extra cost. Never called: `qfq.js` / `hfq.js` factor endpoints, spot quotes, the calendar endpoint, the production fallback index endpoint, any Tonghuashun, Eastmoney or Tencent endpoint.

**Execution controls.** Enforced by the unchanged M2a `PacedTransport` (validated offline, not edited): per-attempt pacing, attempt counting, the 15-attempt ceiling, finite timeouts, redirect refusal, bounded explicit retries, and the sticky 403/429 abort. Enforced by P-A around and INSIDE the transport (new code, covered by P-D tests): an end-to-end 15-minute deadline that also covers body consumption, retry backoff and decoding (see the two rows below and Section 12/S1), response-size and total-byte budgets, bounded JS decoding, and the 2-consecutive-failed-jobs stop. P-A injects `time.monotonic` as the transport clock and `time.sleep` as the sleeper, passes the constant `source="sina"` to every `get_with_retries` call, and records `started_at` (monotonic and UTC) for every attempt.

| Control | Value |
|---|---|
| Concurrency | 1 in-flight request; jobs run sequentially in the Section 2 job order |
| Resource limits | ≤ 8 MiB per response and ≤ 32 MiB for the run, enforced while the body is still arriving; ≤ 4,000,000 payload characters, ≤ 20,000 decoded rows, and a finite JS budget (`timeout_sec` 20 s, `max_memory` 256 MiB) so a corrupt body cannot spin past the deadline |
| Pacing | ≥ 1.5 s between consecutive attempts. The transport paces per `source` key (`transport.py:129-140`); all five requests use the single key `sina`, which is what makes the interval apply across both hosts |
| Timeouts | connect 10 s, read 30 s, on every attempt. The read timeout bounds the gap between socket reads, not the attempt, so it is not a run bound. P-A therefore requests with `stream=True` and consumes the body itself in 64 KiB chunks, checking the deadline and the byte budget after every chunk — with the library default (`stream=False`) `requests` finishes reading `r.content` before `session.get` returns (`requests/sessions.py:826-827`), so no outer check could regain control from a response that keeps trickling |
| Redirects | `allow_redirects=False`; any 3xx is a failed attempt and is never followed |
| Library retries | `requests.Session` adapters must report `max_retries.total == 0` (the requests 2.34.2 default — verified 2026-09-07); asserted at construction by `assert_no_hidden_retries` |
| Explicit retries | ≤ 3 attempts per request, backoff 2 s / 8 s; only on timeout or connection error (after the P-A exception mapping, Section 4) or HTTP 500/502/503/504 (`RETRYABLE_STATUS`); never on other 5xx, 4xx, 3xx, an empty/HTML body, **or a TLS/certificate failure**. `requests.exceptions.SSLError` inherits `ConnectionError`, so catching the broad parent made a certificate failure look transient and retried it three times; it is now caught first and raised as a type the transport treats as non-retryable, because repeating it cannot make an unauthenticated channel authentic |
| Failed job | a job fails when any of its requests exhausts its 3 attempts, raises a non-retryable error, **or returns a body the shared outcome table classifies as unusable** (empty, markup, undecodable, zero rows). The payload is classified BEFORE the job's dependent request is issued, by the same table the checker uses, so P-A does not issue that request and the two can never disagree about it. A failed capability job is a run FAIL under Section 6; the consecutive-job stop only prevents further requests |
| Stop conditions | any **403 or 429** aborts the whole run immediately and stays aborted, **latched from the response headers before any body is read** — status handling used to happen only after full body consumption, so a stop whose body then timed out was reported as a retryable timeout with the abort latch still empty; the 15-attempt ceiling aborts; **2 consecutive failed jobs** abort (tighter than the pilot's 20); the **15-minute end-to-end deadline** aborts. That deadline is checked before every attempt, after every body chunk, before every backoff sleep and around each job (a supervised worker, so a call blocked before its first chunk or a decoder that will not return is bounded too). It raises a `RunAborted` subclass, so the unchanged M2a transport latches it and every later call is refused. **Bounded shutdown allowance: deadline + 45 s.** Honest limit: Python cannot safely kill a thread, and the runner terminates no process — its own or anyone else's; an abandoned worker is a daemon, the session is closed and the interpreter does not wait for it |
| Request headers | identical to a bare `requests.get(url)` as the adapter issues it (default `python-requests` User-Agent, no cookies); recorded verbatim |
| Proxy and TLS | the shell environment sets `HTTP_PROXY`/`HTTPS_PROXY=http://127.0.0.1:7892` (loopback) and `NO_PROXY=localhost,127.0.0.1,::1,.local`; `requests` honours these by default (`trust_env=True`), which is how production akshare calls behave. Mode is fixed at proxy-on (production parity) and the effective proxy is recorded per request (`requests.utils.get_environ_proxies`). The address is loopback, not a credential. All five URLs are `https`, so with pre-flight F7 (trust store pinned, no CA override) each body is authenticated to the vendor end-to-end and the proxy sees only the CONNECT tunnel. Reachability with versus without the proxy is not a goal |
| Timing window (**operator condition — not machine-checked**) | outside continuous trading (before 09:15 or after 15:30 Asia/Shanghai) so the payload cannot contain a partial current-session bar. **No pre-flight check reads the clock**: F1–F8 contain no timing gate and the `--plan` output prints no time, so a green pre-flight does **not** establish timing-window compliance. The operator must verify the Asia/Shanghai wall clock immediately before arming and record it in `REPORT.md`; any row dated after 2026-09-04 is recorded and excluded from the window checks. The local stack must not be running (pre-flight F8): the market-history refresh loop runs on a 14,400 s interval with a 15:15 session-finalization step (`market_history_refresh_loop.py:39-40`), i.e. it can write inside this window |

## 4. Adapter/decoder prerequisites — what must exist before execution, and what stays unknown

**What exists, validated offline and unchanged:** `transport.PacedTransport` (pacing / counting / ceiling / retries / abort), `provenance.derive_unit` (the VWAP-band unit test), the M2a path-safety helpers, the pinned manifest and calendar.

**What does not exist, and why the validated runner cannot be used as-is:**

| ID | Gap | Evidence | Consequence for the smoke |
|---|---|---|---|
| G1 | No decoder for the real payload. `decoder.decode` accepts only the synthetic `m2a.market.v1` JSON envelope and raises on `sina.klc_kl.js` (registered KNOWN-UNSUPPORTED). | `_m2_pilot/decoder.py` | Real bodies would be rejected by design. The smoke needs its own minimal decoder (P-B). |
| G2 | The live transport refuses to run. | `transport.LiveTransport` raises unless armed, then raises "not implemented" | The smoke needs a bounded live callable injected into `PacedTransport` (P-A). |
| G3 | The M2a merge treats request #2 as an **amount** series. The adapter shows it is **outstanding shares**; `amount` comes from the `klc_kl.js` payload itself. | `_m2_pilot/decoder.merge_stock_responses`; `stock_zh_a_sina.py:196-218` | The smoke takes `amount` from the klc payload and labels request #2 `outstanding_share_wan`. It is never labelled amount. |
| G4 | The M2a index template is `…/hisdata_klc2/klc_kl.js` with no query; the adapter uses `…/hisdata/klc_kl.js?d=2020_2_4`. | `_m2_pilot/provenance.py` `INDEX_HIST`; `index_stock_zh.py:302-303` | With the M2a template a real index job would be `unknown` → rejected (fail-closed, but a false negative). The smoke derives the expected URLs from the installed adapter constants at run time. |
| G5 | `expected_urls()` formats the uppercase manifest symbol; the adapter lowercases (`bj920000`). | `_m2_pilot/provenance.expected_urls`; `backend/app/data/akshare_provider.py:96-106` | Same treatment as G4. |
| G6 | The vendor routine is present but unvalidated on real data. `hk_js_decode` (`akshare/stock/cons.py:239`; 17,802 characters; sha256 `39a599c94dde4df1c2eb0882d4bff9560160cfd52ead0797cebb04b3122c2f52`) loads in `py_mini_racer` (mini-racer 0.14.1) offline. It dispatches on a 12-bit header to six decoders (`cons.py:261-266`). Only branch `_3466`/`O` emits `amount` (`cons.py:661-662`), plus `postVol`/`postAmt` when flagged; in that branch `prevclose` is a per-record key present only when the record carries a `p` field (`cons.py:649`). Branches `_200`/`C` and `_136`/`_` set `prevclose` on element 0 but emit no OHLCVA (`cons.py:408`, `:462`); branch `_1479`/`D` emits `date/open/high/low/close/volume` with neither `amount` nor `prevclose`. akshare itself treats `prevclose` as optional (`stock_zh_a_sina.py:186-189`). | offline read of the routine, 2026-09-07 | Whether it decodes today's real bodies, and which branch each body selects, is exactly what the smoke tests. Synthetic envelopes establish nothing about it. `prevclose` is a decode-format observation, not basis evidence (Section 6, B3). |
| G7 | M2a `provenance.derive` corroborates the observed URL path with a **basis declared by the response** (`provenance.py:165-174`); the real Sina payload declares no basis, so under the validated code every real series would be `unknown` by construction. | `_m2_pilot/provenance.py`; `cons.py` routine emits no basis key | Closing P1 needs a defined corroboration substitute and a code change outside M2a: derive the basis from the adapter code path (raw branch, no factor URL — Section 6 B1/B2) instead of a response field. Section 6 names which smoke outputs are candidate P1 evidence. Not designed here. |

G3–G5 and G7 are **live-path findings outside M2a's validated offline scope**. They are recorded as prerequisites for later live work, not as a reason to reopen M2a: no M2a test fails because of them, and the validated code is not edited by this request.

**Code deliverables that must exist and pass offline before boundary 1b** (all under `claude methods/_m2_smoke/`, never staged). There are **five** files, not four: the outcome table moved into a shared `smoke_outcomes.py`, because *capture* needs it too — it is what decides whether a job's dependent request is issued, and leaving it in the checker alone was what let a run of five HTTP 200s contradict its own checker. P-A also owns one bounded `run_pipeline` (capture → decode → checks → report → retention), which is what the armed CLI actually runs:

- **P-A `smoke_capture.py`** — two modes. The **default `--plan` mode writes nothing, opens no database and contacts no host**: it prints the five URLs derived from the installed constants in job order, the pre-flight results F1–F8, the proxy / TLS environment block, the frozen-reference plan and the intended output root; its output is pasted into the 1a review and into the 1b authorization request, so the user authorizes exactly the URLs the code will issue. (F4 does start the JS engine to prove the pinned routine evaluates; that engine's asyncio self-pipe is a *local* socket pair, which is why every guard in this milestone is connection-level rather than a blanket `socket.socket` block — a blanket block would break the adapter replay for a reason unrelated to the vendor.) The **armed mode** (`--i-authorize-live-calls <run_id>`) is the only path that contacts the vendor. It builds a `requests.Session` (retries 0, `trust_env` as production), wraps it in the unchanged `PacedTransport(ceiling=15, min_interval=1.5, connect 10, read 30, session=…)`, and captures the five bodies. The injected callable is a thin adapter, not `session.get` itself: (a) it calls `session.get(url, timeout=timeout, allow_redirects=allow_redirects, stream=True)`; (b) it maps `requests.exceptions.SSLError` **first** to a non-retryable `TlsFailure` (it inherits `ConnectionError`, so the broad parent would otherwise have made a certificate failure look transient and retried it), then `requests.exceptions.Timeout` (before `ConnectionError`, because `ConnectTimeout` inherits from both) to the builtin `TimeoutError`, then `requests.exceptions.ConnectionError` (including `ProxyError`, since the loopback proxy is the production mode) to the builtin `ConnectionError`, chained with `from exc`, and lets every other exception propagate unchanged — those stay non-retryable per `transport.py:172-175`; a known **403/429 is returned straight from the response headers without reading the body**, so a body failure can never downgrade a stop the run already knows about, and any other non-200 still yields a size-capped body for evidence; (c) it consumes the body itself in bounded chunks under the deadline and returns a `CapturedResponse` exposing `.status`, because `PacedTransport.get` reads `.status` (`transport.py:177`) and a `requests.Response` only has `.status_code`; (d) it keeps the bytes, `r.encoding`, `r.apparent_encoding` and the SHA-256 of `r.text` for the capture; (e) it records `started_at` (monotonic and UTC) per attempt, passes `source="sina"`, records the transport's OWN classification of each failed attempt (so no check ever has to parse an error message), and enforces the end-to-end deadline and the consecutive-job stop. Armed mode refuses if the output directory or the evidence directory exists, if the output root is outside `tmp/`, or if either aliases a protected path; it re-runs the pre-flight before the first request and writes `capture_manifest.json` after every attempt so an abort still leaves evidence. It also provides the Section 8 cleanup and the two guards the rest of the milestone relies on: `no_remote_connections` and `db_guard`.
- **P-B `sina_klc_decoder.py`** — pure, no I/O, no clock, no state. Turns the captured bytes into text with `bytes.decode(encoding, errors="strict")` using the recorded `response.encoding` (falling back to `utf-8` only when the response declared none), failing closed on a decode error; extracts the payload **two independent ways** — the adapter's own `text.split("=")[1].split(";")[0].replace('"', "")` (`stock_zh_a_sina.py:181`) and a strict `var NAME = "…";` parse — and refuses unless they agree, because the adapter's positional extraction would silently truncate at an unexpected `=`; reads the **12-bit branch header itself** from the first two base64 characters (`u[0] = index(p0) | index(p1) << 6`, matching `cons.py`'s `w([12, 6])`), so the decoder branch is observed rather than guessed from which keys came back; verifies the pinned `hk_js_decode` hash **before** evaluating it in `py_mini_racer` under finite time and memory budgets; and returns the rows with their **named** keys (no positional renaming) together with the JS variable name and the branch. A second function parses request #2/#5's JSONP into `[(date, outstanding_share_wan)]`. Fails closed on HTML, empty body, a body not starting with `var`, a JS evaluation error, zero rows, more rows than the cap, duplicate or unparseable dates, a date carrying a time-of-day or a non-UTC offset, and non-numeric or non-finite fields.
- **P-C `smoke_checks.py`** — implements Section 6 and writes `checks.json` / `REPORT.md`. It consumes **only retained evidence**: the captured `raw/*.bin`, the capture manifest and the frozen `reference/reference_extract.json`. It never opens `trading_local.sqlite3` itself and never opens `market_history.sqlite3` at all; `replay()` installs `db_guard()`, so "replay does not open production" is enforced at run time rather than promised. It asserts that **P-B's bytes-to-text step** reproduces the SHA-256 of the `response.text` captured at run time — the comparison is text against text, not records against a string — so a `errors="replace"` substitution inside `requests` becomes a visible FAIL. It holds the single **outcome table** (Section 6) that turns transport and payload states into request, job and run results. Its **R1 adapter replay** patches `requests` in both adapter modules (`akshare.stock.stock_zh_a_sina`, `akshare.index.index_stock_zh`) to serve the captured bytes for the exact URL (honouring the `params` argument) and to raise for any other URL, blocks every non-loopback connection for the duration, then calls `ak.stock_zh_a_daily("sh600011", adjust="")`, `ak.stock_zh_a_daily("bj920000", adjust="")` and `ak.stock_zh_index_daily("sh000300")` and records what the installed adapter actually returns. `checks.json` separates a **deterministic block** (hashed, compared byte for byte on replay) from `run_meta` (run timestamps and durations, intentionally variable and excluded from that comparison).
- **P-D `test_m2_smoke.py`** — offline tests with every non-loopback connection blocked for the whole process: `--plan` writes nothing, creates nothing and opens no database; arming refusal; path-safety refusals including a pre-existing evidence directory and an output root outside `tmp/`; pacing / ceiling / abort through fake responses; the exception mapping (`ReadTimeout`, `ConnectTimeout`, `ConnectionError`, `SSLError`); the response adaptation (a fake 200 with `status_code` is recorded `ok`, not "unexpected status 0"); **S1** — a continuously trickling response, an oversized response, a blocked in-flight call, a stuck decoder, retry/backoff near the deadline, deadline stickiness through the unchanged transport, and a real aborted capture that leaves partial evidence and issues no further request; the consecutive-job stop; HTML / empty / JS-error / decode-error / duplicate-date / non-numeric rejection; the routine-hash pin; the independently derived branch header; the outstanding-share label; expected-URL derivation from the installed constants and proof that the M2a templates are *not* reused; **S2** — the nine outcome cases, each with one deterministic result consistent with the request-count check, plus proof that no transport or decode failure can produce a vendor-absence finding and that a failure class is never inferred from message text; check decidability on synthetic rows including U2 windowed versus all rows, the I2 one-step rule, date-aligned U4 and code-derived B2; **S3** — a frozen synthetic reference, a mock cache that then moves, a replay that reproduces the deterministic block byte for byte, and a proof that no database was opened during it; the R1 patching harness (only captured URLs, params honoured, remote connections refused, both modules restored); header/proxy redaction; and cleanup. **What these tests cannot do:** validate the vendor decode, or the adapter replay, on a real body. There is no real sample, and inventing one would be the R1 defect again. That gap closes only by executing the smoke.

**Pre-flight (F1–F8)**, printed by `--plan` and re-run by armed mode before the first request; any failure aborts before any call. **F1–F8 check machine state only — none of them reads a clock.** The Section 3 timing restriction is an operator condition verified and recorded by a human immediately before arming; a green pre-flight says nothing about it. F8 must be passed by the stack already being stopped, never by stopping a service to make it pass:

- F1 record branch, HEAD and a hash of `git status --short`.
- F2 fingerprint every protected path (Section 5), hash the manifest, the calendar, `_m1_closure/*.py` and `_m2_pilot/*.py`, and **freeze a minimal read-only reference extract**: for each of the three symbols, every `ready` `daily_bar_cache` row inside 2022-08-24..2026-09-04 with only the fields the checks consume (`trade_date, close, volume, amount, source, adjustment_mode, volume_unit, quality_status, updated_at`), plus the selection SQL, the symbols, the window, the thresholds and the calendar and database hashes, written to `reference/reference_extract.json` and hashed. Every check then reads that file and nothing else, so a later cache refresh cannot change a replayed result while the response hashes are identical. `--plan` does **not** open the database: it prints the SQL and marks this step PLANNED. A summary of the cache tail is not sufficient and is no longer what is retained.
- F3 `akshare.__version__ == "1.18.64"` and the three URL constants equal the pinned strings.
- F4 `sha256(hk_js_decode) == 39a599c9…` and the routine evaluates in `py_mini_racer`.
- F5 session adapters report `max_retries.total == 0`.
- F6 the output root and the evidence directory do not exist; the output root is inside `tmp/`.
- F7 TLS trust pinned: `session.verify is True`, `session.cert is None`; for each of the five URLs `session.merge_environment_settings(url, {}, None, None, None)["verify"] is True` (this is where `requests` would substitute `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` under `trust_env=True`); `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `SSL_CERT_FILE` and `SSL_CERT_DIR` are unset; `requests.utils.DEFAULT_CA_BUNDLE_PATH == certifi.where()` and that path is inside `backend/.venv/`. The certifi version and the bundle's SHA-256 are recorded in the environment block (2026-09-07: certifi 2026.6.17, `bbc7e9c01d7551bb8a159b5dedd989b8ee3ce105aff522b68eb1b01bf854cab0`, 234,354 B; no override set).
- F8 the local stack is not running: no process executing `backend/scripts/*_loop.py`, `scripts/run_stack.ps1` / `ensure_stack.ps1` workers, or an API/frontend listener, and the pid recorded in `backend/logs/market_history_refresh_heartbeat.json` (if the file exists) is not alive; the process inventory is recorded. If anything is running, abort before any request and report — stopping a service is the user's action, not the smoke's. (On 2026-09-07 at preparation time nothing of the kind was running.)

## 5. Output paths, protected inputs and provenance

**Temporary output root — the only location written while requests are in flight:** `D:\codex-A股交易\tmp\m2b_smoke_<run_id>\`, with `run_id = YYYYMMDDTHHMMSSZ` (UTC). `tmp/` is ignored by `.gitignore:37` and does not exist today. During the run the script creates exactly this tree and nothing else:

```text
tmp/m2b_smoke_<run_id>/
  plan.txt                       the --plan output the user authorized, verbatim
  capture_manifest.json          one record per attempt + environment block
  raw/01_sh600011_klc_kl.js.bin
  raw/02_sh600011_getAmountBySymbol.bin
  raw/03_sh000300_klc_kl.js.bin
  raw/04_bj920000_klc_kl.js.bin
  raw/05_bj920000_getAmountBySymbol.bin
  reference/reference_extract.json  the frozen read-only cache rows the checks consume (S3)
  decoded/<symbol>_bars.csv, decoded/<symbol>_outstanding_share.csv, decoded/<symbol>_adapter_replay.csv
  checks.json, REPORT.md
  protected_before.json, protected_after.json
```

At cleanup (Section 8) the evidence subset is moved to **`claude methods/_m2_smoke/evidence_<run_id>/`** — the second and last directory the smoke writes. It is durable and untracked; it is *not* covered by `.gitignore`, so its exclusion from Git relies on the hygiene rule that Claude/Codex files are never staged. Whether the raw bodies are retained there or reduced to hashes is the user's choice at authorization (Section 8).

**The captured artefact** is `response.content` — the bytes after `requests` has removed any transfer `Content-Encoding` (it gunzips transparently, so this is not necessarily the wire body) — written verbatim to `raw/*.bin`; its SHA-256 is the body hash used everywhere. `Content-Encoding`, `response.encoding` and `response.apparent_encoding` are recorded so the bytes-to-text step of P-B is reproducible and comparable with the adapter's `r.text`.

**Protected inputs — opened read-only or not at all; fingerprinted before and after:** `trading_local.sqlite3` (rollback-journal mode, no sidecars) and `market_history.sqlite3` with its `-wal` file (size + mtime_ns; these three form the **invalidation set**, matching the acceptance baseline), `_m1_closure/pilot_symbols.csv`, the pinned `calendar.json`, every `.py` in `_m1_closure/` and `_m2_pilot/`, and `backend/app/` (SHA-256 for the small files). The `market_history.sqlite3-shm` file is recorded (presence, size, mtime_ns) but does not invalidate the run: it is the WAL shared-memory index, which read-only connections rewrite on open and close. A changed invalidation-set fingerprint after the run invalidates the run regardless of the checks; F8 exists so that such a change can only mean interference, not a scheduled refresh.

**Never written:** any SQLite database, `staging/`, `CURRENT.json`, `_m1_closure/`, `_m2_pilot/`, backend runtime code, datasets, strategy or knowledge files. `market_history.sqlite3` is never opened. The M1 gate is not run (it expects the 50+2 manifest and would fail M1/M3 on three symbols by design), `PilotRunner` is not used, and no basis label is stamped anywhere.

**Provenance recorded per attempt:** requested URL, served URL (must be identical), HTTP status, `Content-Type`, `Content-Encoding`, `Content-Length`, `Date` and `Server` headers, byte length, **SHA-256 of the captured bytes**, `response.encoding`, `started_at` (monotonic and UTC), seconds waited for pacing, attempt index, effective proxy, request headers. Environment block: akshare / requests / urllib3 / mini-racer / certifi versions, the `hk_js_decode` hash, the CA-bundle hash, calendar and manifest hashes, HEAD, the `git status --short` hash, the F8 process inventory, the F2 reference-row summary, and run mode `live_smoke` (never `offline_synthetic_fixture`). Authorization, cookie, proxy-authorization and other credential-bearing header names are recorded with their values redacted, and any userinfo in a proxy URL is stripped, even though the expected request environment is credential-free today — a future header must not leak by default. Body hashes are repeated in `REPORT.md` so the sample can be verified later. The served-URL and body-hash provenance is meaningful only together with F7.

## 6. Pass/fail checks

**Verdicts.** Three verdicts are reported: a **run status** (`completed` or `aborted`, with the reason), a **per-job verdict** for each of the three jobs, and a **capability verdict** with four possible values:

| Capability verdict | When | What it authorizes |
|---|---|---|
| `PASS` | the run completed and all three jobs PASS every required check | nothing beyond the five captured responses |
| `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` | the two capability jobs PASS and the BJ job ended in the documented `vendor_explicit_absence_at_path` outcome (C2) | **nothing**; it is deliberately not an unqualified all-three PASS and does not authorize the 52-symbol pilot |
| `INCONCLUSIVE` | any required check or job outcome is inconclusive — a transport fault, an undecodable payload, an unusable reference, or a deadline/pre-flight abort | nothing |
| `FAIL` | any job or run-level check failed, or the vendor stopped the run (403/429) | nothing |

**The single outcome table.** Every `(transport state, payload state)` pair maps, in one exhaustive table in `smoke_checks.py`, to a request result, a job result, an evidence class, whether the job's remaining requests are skipped, and whether the run aborts. Two properties follow by construction and are regression-tested: an exhausted 5xx, a timeout, a TLS failure, a refused redirect, an empty body, markup and a decoder error are `FAILED` or `INCONCLUSIVE_*` evidence and can never become a positive capability finding; and the only route to "the vendor does not serve this path" is an explicit HTTP **404/410**. The request-count check reads the same table, so a skipped request is always skipped *because the table said so*, and a request skipped with no upstream trigger fails T3. An unlisted state pair fails closed. Any FAIL or UNKNOWN on a required check fails that job; "partial" is not a verdict. Advisory items are recorded and never waived into a pass. The verdicts concern the live path and the decoder, not corpus readiness.

**Capture envelope — required, run-level (`EV0`, `EV3`, `EV4`, `EV5`, `EV6`)**
- EV0 the capture certifies itself valid: `run_valid` true, an empty `invalidating_changes` list, `protected_after` fingerprints present, deadline provenance present, and at least one request record. Missing evidence or an explicit invalidation is never a PASS; both used to be recorded and then ignored.
- EV3 the frozen reference content hash is **recomputed** from the retained rows and must equal both the extract's own declaration and the `reference_extract_sha256` the capture manifest binds. The recomputed hash is what enters the deterministic block, so altering retained rows changes the replay hash instead of leaving it identical.
- EV4 the approved pins hold: calendar SHA-256, akshare version and the `hk_js_decode` hash recorded by the run. An absent pin is INCONCLUSIVE (missing provenance); a disagreeing pin is FAIL.
- EV5 the frozen selection/threshold contract — symbols, window, expected basis and every tolerance — is compared against the constants the running checks actually apply, so it is verified rather than merely described.
- EV6 the payload state capture recorded for a body must equal the state its retained bytes classify as now.

**Transport — required, per attempt**
- T1 status 200; served URL equals requested URL; no 3xx.
- T2 body non-empty and not markup (`<!doctype`, `<html`, `<?xml`); `Content-Type` recorded, not gated.
- T3 PASS iff total attempts ≤ 15; **every request that was issued** ended in exactly one HTTP 200 (expected on a clean run: 5 issued, 0 retries — a retry is recorded with its cause and is not by itself a FAIL); every request recorded as `skipped` carries an explicit **scope** — a `job_local` skip must be downstream of a request the outcome table skipped the rest of *that job* for, while a `run_global` skip is explained by the run abort itself and needs no such trigger — and no request was issued after a trigger; every attempt carries the source key `sina`; and for consecutive attempts `started_at[k+1] − started_at[k] ≥ 1.5 s` on the **actual post-pacing wire start of every attempt, retries included**. The request-level timestamp used before was taken *before* `get_with_retries` performed the pacing wait, so a correctly paced run of 0.0/1.5/3.0/4.5/6.0 s was recorded as 0.0/0.0/1.5/3.0/4.5 and failed its own pacing check with a 0.000 s gap; a manifest without a wire start for every attempt cannot validate pacing at all and fails. (The transport's `waited` field is the sleep it inserted, not a timestamp, and is 0.0 on a normally paced run.) A ceiling, key, spacing or count-consistency violation fails the run. A job whose requests were not all issued never PASSes, whatever the reason.

**Source schema — required, per symbol**
- S1 the observed URL set equals the expected set derived from the installed adapter constants: two URLs for each stock, one for the index; any extra or missing URL is FAIL.
- S2 the body decodes with the **pinned** routine. If decoding required altering the routine, the vendor format changed: FAIL.

**Decode — required, per symbol**
- D1 the klc body matches `^\s*var\s+\w+\s*=\s*"` and the routine returns ≥ 1 row; the JS variable name is recorded (if it embeds a symbol, that symbol must be the requested one).
- D2 keys: stock rows carry `date, open, high, low, close, volume, amount` (a stock row without `amount` is FAIL — this is Q1); index rows carry `date, open, high, low, close, volume` (`amount` recorded if present, not required — Q5); the full observed key set and the decoder branch selected by the header are written to the report (a stock body that carries `amount` was decoded by branch `O`).
- D3 dates parse as real calendar dates, are unique and strictly increasing; every date inside 2022-08-24..2026-09-04 is on the pinned calendar (an off-calendar date is FAIL: either an invalid date or a calendar mismatch that the M1 gate would reject); dates outside the window are listed.
- D4 all price / volume / amount values are finite numbers; for every research-window row with `volume > 0`, `low ≤ min(open, close)` and `max(open, close) ≤ high`; any violation is FAIL and is listed. Zero-volume rows are U1's domain.
- D5 requests #2 and #5 parse as a non-empty `[[date, value], …]` list with positive values and are labelled `outstanding_share_wan` in every output. Treating them as amount is a plan violation, not a data finding.

**Adapter replay — required, per symbol (offline, every remote connection blocked, on the captured bytes)**
- R1 the installed adapter, called exactly as production and the pilot would call it (`stock_zh_a_daily(symbol, adjust="")`, `stock_zh_index_daily(symbol)`) with `requests.get` patched to serve the captured bytes for the exact URL, returns without raising and requests no URL other than the captured ones (a request for any other URL, e.g. `qfq.js`, is FAIL). Recorded: the adapter's row count, first and last date, and the rows present in the raw decode but absent from the adapter output — this is the measured answer to Q3, not a proxy. The R1 dates must be a subset of the raw-decode dates; any date the adapter emits that the raw decode does not carry is FAIL (a fabricated row).

**Identity — required; production cache read-only**
- I1 the URL symbol equals the requested adapter symbol.
- I2 the payload carries no symbol, so corroboration is required. Reference = `trading_local.sqlite3` table `daily_bar_cache`, rows with `quality_status = 'ready'` and `adjustment_mode = 'qfq'` (stocks) or `'none'` (`SH000300`), read once at F2; `market_history.sqlite3` is not the reference. On the ten most recent sessions common to the decoded series and the reference, `close_live / close_local` must equal 1.000 within `max(0.1%, 0.01 / close_local)` for all three symbols: the cached `qfq` tail is re-anchored at every refresh, so raw must equal `qfq` there, and the index cache is on basis `none`. If the ten ratios are not all within tolerance but contain exactly one step, split at the step: the post-step segment (≥ 3 sessions) must satisfy the tolerance and the step date is recorded as a candidate ex-date for B3/B4; any other pattern is FAIL. The source of every overlap row is written to `checks.json`.
- I3 on the same sessions (or the post-step segment) `volume_live / volume_local ≈ 100 ± 1%` for stocks — the cache stores 手 = 股 / 100 (`akshare_provider.py:111-112`), so this also corroborates the unit — and `≈ 1.0 ± 1%` for the index (same source).

**Raw-basis evidence — B1 and B2 required (code-derived); B3 and B4 advisory**
- B1 the transport log shows no `qfq.js` / `hfq.js` request.
- B2 (required, derived from the adapter code, not measured live) the decoded stock OHLC are the klc series exactly as the routine returns them, with no factor applied: the adapter produces `hfq` only by fetching `hfq.js` (`stock_zh_a_sina.py:234`) and **multiplying** open/high/close/low by that factor (`:254-257`), and `qfq` only by fetching `qfq.js` (`:270`) and **dividing** by that factor (`:293-296`) — an earlier draft of this document said qfq multiplies, which is wrong — while `adjust=""` returns the klc series untouched (`:219-232`). P-C reads these three properties out of the installed source text rather than restating them, so B2 is checkable. Together with B1 this is the raw-basis evidence for these five responses.
- B3 (advisory) record which decoded elements, if any, carry `prevclose`; for each such element `k > 0` compare `prevclose_k` with `close_(k-1)` and list every mismatch date as a candidate corporate-action marker. Presence or absence is a decode-format observation and is never a FAIL.
- B4 (advisory) over the local overlap, `close_live / close_local` is piecewise constant with steps at corporate-action dates; ≥ 1 step for `SH600011` is evidence that the live series is unadjusted relative to the cached `qfq` series. Limit: the cached series mixes sources fetched at different times, so this is evidence, not proof.
- **Candidate P1 evidence, stated now so the user can decide P1 on the report:** the exact raw URL set with no factor endpoint (S1, B1), the code derivation (B2), the adapter replay with `adjust=""` (R1), and the ratio behaviour against the anchored `qfq` reference (I2, B4). Not P1 evidence: `prevclose` (B3). **The smoke produces basis evidence; it does not assign `none`. That remains prerequisite P1 of the M2 request (see G7).**

**OHLCV / amount semantics and units — required, stocks only**
- U1 `volume > 0` and `amount > 0` on every research-window row; any zero row inside the research window is FAIL for stocks and is listed (suspended sessions are normally absent from the payload, so a zero row is unexplained).
- U2 the unit is derived with the unchanged M2a `provenance.derive_unit` (VWAP band 0.98–1.02, ≥ 95% one-sided, ≤ 5% for the other candidate). The required verdict is computed on the decoded rows dated 2022-08-24..2026-09-04 (rows after 2026-09-04 excluded per Section 3); it must be `share` or `hand`, and `unknown` is FAIL. The same statistic over all decoded rows (what the validated M2a runner feeds to `derive`) is reported as advisory with its `usable_rows` and both consistency scores; a divergence between the two verdicts is a finding for the stage-2 request, not a smoke FAIL. Expected: `share` on both (Sina reports 股; the project adapter divides by 100).
- U3 currency: on the I2 sessions (or post-step segment) with non-null cached amount, `amount_live / amount_local = 1.00 ± 1%` → 元 with no 万元 scaling; otherwise FAIL.
- U4 (advisory) **date-aligned**: on every date carried by both the klc series and the share series, `volume ≤ outstanding_share_wan × 10,000` for that same date (turnover cannot exceed 100%). Comparing one unspecified share observation with the maximum volume over the whole window would not be a comparison of like with like.

**Date coverage — C1 and C3 required; C2 and C4 are findings**
- Corroboration span (used by C1–C3) = the sessions present for the symbol in the F2 reference rows with `volume > 0`, as read at run time (on 2026-09-07: `SH600011` 538 sessions 2024-06-21..2026-09-04; `BJ920000` 501 sessions 2024-08-13..2026-09-04; `SH000300` 538 sessions 2024-06-19..2026-09-02). Every such session must appear in the decoded live series; a locally present session missing live is a vendor or decoder gap → FAIL, listed by date. A live row with zero volume on such a session is handled by U1, not here.
- C1 `SH600011`: first decoded date ≤ 2022-08-24 and last decoded date ≥ the reference tail date (else FAIL: the source cannot serve the window or is stale); corroboration span complete. Sessions present in 2023-09-04..2026-09-04 versus 728 expected, and in 2022-08-24..2023-09-01 versus 250, are counted and missing sessions **listed**; before the corroboration span begins the smoke cannot distinguish a suspension from a vendor gap, so a pre-span shortfall is a finding for the pilot's expected keys, not a smoke FAIL.
- C2 `BJ920000`: the outcome is classified `pre_boundary_history_served` (earliest decoded date ≤ 2024-08-12), `post_boundary_only` (earliest ≥ 2024-08-13), or `vendor_explicit_absence_at_path` — and **only** an explicit HTTP 404/410 on request #4 produces that third value, with the raw status recorded. A non-200 that is not 404/410, an exhausted 5xx, a timeout, a TLS failure, an empty body, markup and an undecodable payload are `INCONCLUSIVE_*` or `FAILED` evidence instead: none of them distinguishes unsupported history from a temporary upstream error, a bad hop, a wrong URL or a decoder defect, so none of them is allowed to look like an answer. **The cause of an explicit absence is recorded as `not established`**: five responses cannot show whether a `92xxxx` code mapping, a retired path or something else is behind it, and the classification name no longer asserts one. The first two classifications are PASS for the job when the other required checks pass, with the corroboration span complete as in C1; the third is a **finding**, reported for the revised M2 request and for a manual follow-up of the URL form, and it caps the capability verdict at `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE`, which authorizes nothing. If `post_boundary_only` or an explicit absence, the 52-symbol pilot as pinned would fail M1/M3 for the seven `bj_code_history` symbols; that becomes a manifest / expected-key decision for the user in the revised M2 request. The population is not changed here.
- C3 `SH000300`: first decoded date ≤ 2022-08-24 and last ≥ the reference tail date; corroboration span complete; sessions versus 728 / 250 listed as in C1.
- C4 (finding) adapter post-processing losses, measured on the raw decode and cross-checked against R1 for both stocks: (i) the count of window rows whose `(open, high, low, close, volume, amount)` equals another row's — what `stock_zh_a_sina.py:221-223` would silently drop, expected 0 for liquid stocks; (ii) the first date and row count of the request-#2/#5 series and the number of klc rows dated before it — the adapter's outer merge, `ffill` and `dropna` (`:202-205`, `:228`) drop those rows, so any consumer of the adapter path must use `max(first klc date, first outstanding-share date)` as the effective first date; (iii) the number of outstanding-share dates absent from the klc dates — the adapter's `ffill` fabricates a price row there, later removed only if it duplicates the previous OHLCVA.

**Benchmark handling, separate by construction:** no outstanding-share request, no amount requirement, no unit gate (the unit stays `unknown` unless an `amount` key is present, in which case U2 runs as evidence only), identity by ratio 1.000 against the cached `none` rows, and no liquidity claim of any kind.

## 7. Report

`REPORT.md` contains, in this order: baseline (HEAD, status hash, run_id, start / end UTC, timing-window compliance, F8 process inventory); the verbatim `--plan` output that was authorized; the environment block; the five-attempt table with hashes; the three verdicts; the check table (id, symbol, PASS / FAIL / advisory / finding, measured value, threshold); the answers to Q1, Q3, Q4, Q5 and the two new questions with measured values; the decoder branch per body; the adapter-replay summary per symbol; the BJ outcome classification; the missing-session lists; protected-input fingerprints before and after; the abort reason if any; and the cleanup record. It makes no statement about readiness, corpus coverage, models or strategy.

## 8. Cleanup and recovery

- **Normal completion (any verdict):** performed by `run_pipeline` itself, on an explicitly declared finalization allowance (120 s) separate from the run deadline, because evidence must still be written after the run budget is spent. Write the SHA-256 manifest of the output tree into `REPORT.md`; move `plan.txt`, `raw/`, `capture_manifest.json`, `checks.json`, `REPORT.md` and `decoded/` to `claude methods/_m2_smoke/evidence_<run_id>/`; delete `tmp/m2b_smoke_<run_id>/`. The five raw bodies (expected well under 2 MB) are the captured responses produced by the capture/decoder workflow the acceptance asks to prepare, and the only real-payload sample the decoder and the adapter replay can be validated against. Retaining them is a **Claude proposal the user accepts or declines at 1b**: default retain, never staged, never sent to any external service; alternative: delete `raw/` after review and keep only the SHA-256 hashes already in `REPORT.md`.
- **Abort (403 / 429, ceiling, consecutive failures, wall-clock, pre-flight):** keep whatever was captured, write `REPORT.md` with run status `aborted` and the reason, move the partial tree to the evidence directory exactly as on normal completion, delete the temporary root, and do not retry. A **403 / 429** additionally blocks any 52-symbol request until the user reconsiders the vendor-limit question.
- **Rollback:** delete the two directories above (boundary 1b) or `claude methods/_m2_smoke/` entirely (boundary 1a). Nothing else is changed by the smoke: no service, no database write, no runtime edit, no pointer. If the invalidation-set fingerprint (both main database files and `market_history.sqlite3-wal`) or any other protected fingerprint differs after the run, the run is declared invalid regardless of the checks; a `-shm` change alone is reported, not invalidating.
- **Reviewer reproduction:** with every non-loopback connection blocked, `smoke_checks.replay(<evidence_dir>)` re-runs P-B, P-C and R1 on the retained `raw/*.bin` plus the frozen `reference/reference_extract.json`. It must reproduce the **deterministic block** of `checks.json` and the body hashes byte for byte; run timestamps and durations live in `run_meta` and are deliberately excluded from that comparison. `db_guard()` is installed for the duration, so the replay cannot open a production database even if the code tried — which is what makes the result independent of a cache that has moved on since the capture. This is the command Codex re-runs when reviewing the 1b report.

## 9. Authorization boundaries — preparing is not executing

| Boundary | Content | Status |
|---|---|---|
| **0 — this document** | Preparing the request. | Done. **Authorizes nothing.** No call, download, code, directory, service, commit, push or promotion has occurred. |
| **1a — offline smoke code** | Write P-A..P-D under `claude methods/_m2_smoke/` with tests that block every remote connection; stop at `ready_for_review` with the `--plan` output attached. Independent Codex review of P-A..P-D is the protocol's step-5 default; only the user may waive it. | **Technically VALIDATED by Codex, 2026-09-08** (`M2B_1A_ACCEPTANCE_CODEX.md`; Sections 12-15). `test_m2_smoke.py` 132 cases, 0 unexpected, exit 0; the independent R1–R4 closure probes pass; `--plan` F1–F8 all PASS. Validation covers the **offline engineering path only** — it is not user authorization for live work and does not complete M2. |
| **1b — execute the five requests** | Run P-A once in armed mode **outside continuous trading** (before 09:15 or after 15:30 Asia/Shanghai — an operator condition, verified and recorded by hand, not by any pre-flight), with a fresh passing pre-flight and every reviewed limit of Section 3 unchanged; produce `REPORT.md`; perform the Section 8 cleanup (which writes `claude methods/_m2_smoke/evidence_<run_id>/` and, by default, retains the five raw bodies there). The report stops at `ready_for_review`; Codex reviews it (reproduction in Section 8) before any status above that. **Executed once on 2026-09-08** (run_id `20260908T021722Z`, Section 16): capability **FAIL**, 2 of 5 requests issued, evidence retained locally. The authorization was for exactly one run and is now spent; any further run needs a new one. Historical precondition text follows. The technical preconditions were met — `test_m2_smoke.py` exits 0, `--plan` shows F1–F8 green, and Codex validated 1a on 2026-09-08 with no blocking item. What remains is **the user's explicit, separate instruction**, which must also state the evidence-retention choice (Section 8): whether the captured raw bodies and the frozen reference extract are retained locally under the evidence directory. Passing this review is not that instruction. The `--i-authorize-live-calls` flag is a control, not a permission: it is set only when the user has said "run the smoke". |
| **2 — 52-symbol pilot** | Staging collection of the approved 50 + 2. | Later and separate. Requires a capability PASS, the G3–G5/G7 corrections implemented and tested, the P1 basis-label decision taken on the evidence named in Section 6, and a revised M2 request (rev. 3) whose expected keys reflect the C2 and C4/R1 results. Not requested. |

A capability FAIL escalates to nothing; it produces findings. A capability PASS proves only that five specific responses were captured, decoded, replayed through the adapter and checked as stated.

## 10. Expected outcomes, stated before the run

- `SH600011`: decode expected to succeed via branch `O`; `amount` expected present; unit expected `share`; the adapter replay expected to return without raising; every corroboration-span session expected present live; earlier coverage complete or with listed gaps.
- `SH000300`: the URL is the one the adapter really uses, not the M2a template; decode expected to succeed with the same routine; decoder branch and `amount` presence unknown and recorded; whether `d=2020_2_4` bounds the history is answered by C3.
- `BJ920000`: decode expected to succeed; earliest date **unknown** — any of the three C2 outcomes is useful and none is padded around.
- Vendor limits, the other 49 symbols, strict point-in-time evidence, corpus units, the basis label and anything about strategy: **not established by this smoke**, pass or fail.

## 11. Handoff record (collaboration template, Section 6 of `CODEX_CLAUDE_COLLABORATION.md`)

```text
task_id / title:        M2B — bounded three-symbol real-source verification request
status / owner / reviewer: 1a VALIDATED (offline scope, 2026-09-08), 1b proposed / Claude / Codex — reviews this request, then P-A..P-D at 1a
                        (protocol default, user may waive), then the 1b REPORT.md before any status above ready_for_review
goal / non-goals:       Sections 1 and 10; not the 52-symbol pilot, not training, not promotion
user authorization:     none for execution; this document is preparation (boundary 0)
baseline:               codex/control-plane-refactor @ 73f266d, index empty, 2026-09-07; unrelated dirty
                        files in backend/ and scripts/ untouched; no tmp/, staging/ or _m2_smoke/
write_scope (0):        claude methods/M2B_REAL_SOURCE_VERIFICATION_REQUEST.md,
                        claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md (ledger, Sections 12-15 headers/banners, Section 15)
write_scope (1a, if authorized): claude methods/_m2_smoke/*.py only (five files: P-A, P-B,
                        P-C, P-D and the shared outcome table)
write_scope (1b, if authorized): tmp/m2b_smoke_<run_id>/ during the run; claude methods/_m2_smoke/evidence_<run_id>/ at cleanup
read_only_scope:        everything else — trading_local.sqlite3 table daily_bar_cache via mode=ro + query_only,
                        _m1_closure/, _m2_pilot/, backend/app/, the installed akshare package; market_history.sqlite3 never opened
data impact:            none at 0 and 1a; at 1b read-only production access plus the two directories above
safety:                 review_only / live_trading_disabled; no account, credential, order or service capability
acceptance:             Section 6, all required checks decidable from the captured bytes plus the F2 reference rows
independent review:     1a validated by Codex 2026-09-08 (M2B_1A_ACCEPTANCE_CODEX.md), offline
                        scope only; 1b reviewer reproduction defined in Section 8
rollback:               1a: delete claude methods/_m2_smoke/; 1b: delete the two directories; nothing else changes
next step:              the user decides whether to authorize 1b, including the local
                        evidence-retention choice. Nothing runs until then
```


## 12. Boundary 1a implementation record (2026-09-07, responding to `M2B_PLAN_CODEX_REVIEW.md`)

> Superseded in part by Section 13. The S1/S2/S3 intent below stands; the mechanisms it describes were exercised in helpers rather than on the real call chains, and the review of that delivery (`M2B_1A_CODEX_REVIEW.md`) reproduced eight integration defects. Read Section 13 for what the code now does.

> Status: `ready_for_review`. Offline only. **Boundary 1b was not executed**: no network call, no download, no real collection, no production or runtime change, no service operation, no Git staging/commit/push, no training, no promotion. Validated M1 and M2a are imported unmodified and still pass; the reviewer's artefacts were not touched.

### The three requirements

| ID | What the review found | What was implemented |
|---|---|---|
| **S1** | The 15-minute limit was checked only before each request, so it was not a hard runtime limit. A response that keeps sending small chunks inside every read timeout stays alive past it, and with `stream=False` `requests` finishes reading `r.content` before `session.get` returns, so the outer check can never regain control. Decoding was unbounded. | An end-to-end `Deadline` on an injected monotonic clock covers **body consumption, retries, backoff and decoding**. Bodies are requested with `stream=True` and consumed by `read_body_streamed` in 64 KiB chunks, with the deadline and a byte budget checked after every chunk — that is what actually stops a trickle. `supervise` runs each job in a daemon worker and stops waiting at the deadline, covering a call blocked before its first chunk and a decoder that will not return. `DeadlineExceeded` subclasses the unchanged M2a `RunAborted`, so the transport latches it and refuses every later call. Resource limits: ≤ 8 MiB per response, ≤ 32 MiB per run, ≤ 4,000,000 payload characters, ≤ 20,000 rows, JS `timeout_sec` 20 s and `max_memory` 256 MiB. **Documented bounded shutdown allowance: deadline + 45 s**, with the honest limit stated in the code and in Section 3 — Python cannot safely kill a thread, and this runner terminates no process, its own or anyone else's. |
| **S2** | C2 mapped any non-200, empty body or undecodable response to `not_served_under_92_code`, called it decisive and let it reach capability PASS, while T3 demanded five HTTP 200s and the failed-job rule skipped a request — conflicting outcomes for one BJ failure. | One exhaustive `OUTCOME_TABLE` keyed by `(transport state, payload state)` decides the request result, the job result, the evidence class, whether the job's remaining requests are skipped and whether the run aborts. Exhausted 5xx, timeouts, TLS failures, refused redirects, empty bodies, markup and decoder errors are `FAILED` or `INCONCLUSIVE_*`; **only an explicit HTTP 404/410** yields `vendor_explicit_absence_at_path`, whose **cause is recorded as `not established`**. 403/429 remain unconditional aborts. T3 reads the same table, so the request count and the outcomes always agree, and a request skipped without an upstream trigger fails. The capability verdict gained `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE`, which is not an unqualified all-three PASS and authorizes nothing — the 52-symbol pilot least of all. |
| **S3** | Checks depended on live cache rows while retention kept only the raw bodies and a summary of the local reference, so a replay against a refreshed cache could change identity/unit/coverage results with identical response hashes. | F2 now freezes `reference/reference_extract.json`: for each symbol every `ready` row in the window with only the consumed fields, plus the SQL, symbols, window, thresholds and the calendar and database hashes. Every check reads that file; `replay()` installs `db_guard()`, so opening a production database during a replay raises rather than being trusted not to happen. `checks.json` separates a hashed **deterministic block** from `run_meta`, so run timestamps cannot make an unchanged result look changed. The reference is **qualified, not assumed**: a mixed-basis overlap, a zero denominator, no non-null amount on both sides or fewer than three usable overlapping sessions produce an explicit `INCONCLUSIVE` with a stated reason — never a repaired number, and never a change to production data. |

### The four minor clarifications

1. P-C compares the **bytes-to-text step** against the SHA-256 of the captured `response.text` (text against text). P-B decodes strictly, so a `errors="replace"` substitution inside `requests` is a visible FAIL rather than a silent corruption.
2. B2 now records that the **hfq branch multiplies** by its factor (`stock_zh_a_sina.py:254-257`) and the **qfq branch divides** by its factor (`:293-296`); the earlier general wording was wrong. P-C reads all three properties out of the installed source, so B2 is checkable rather than remembered. Basis evidence stays tied to the raw branch; `prevclose` remains advisory and is never used to infer a label.
3. U4 is **date-aligned**: `volume ≤ outstanding_share_wan × 10,000` on dates carried by both series. Still advisory.
4. Credential-bearing header names (`authorization`, `cookie`, `proxy-authorization`, …) are recorded with redacted values and proxy URLs are stripped of userinfo, even though the expected environment is credential-free today.

### Exact commands and actual results

```bash
cd "claude methods/_m2_smoke"
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2_smoke.py      # exit 0, 79 cases, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 smoke_capture.py --plan   # exit 0, F1-F8 all PASS, writes nothing

cd "../_m1_closure"                                                     # accepted M1, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py       # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py   # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py   # exit 0, 67 checks

cd "../_m2_pilot"                                                       # accepted M2a, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py           # exit 0, 79 cases, 0 unexpected
```

**Files added** (all new, all under `claude methods/_m2_smoke/`): `smoke_capture.py` (P-A), `sina_klc_decoder.py` (P-B), `smoke_checks.py` (P-C), `test_m2_smoke.py` (P-D). **Files edited:** this document and the progress ledger. Nothing in `_m1_closure/`, `_m2_pilot/` or `_m2_codex_review/` was modified: `pilot_runner.py` is still `943a8c3f…`, `test_m2a.py` still `5ec05456…`.

### One design decision that differs from the plan's wording, and why

The plan and the review both say the tests block `socket.socket`. A blanket block cannot be used here: `py_mini_racer` — the engine the vendor routine runs in, and therefore the engine the **R1 adapter replay** starts — creates an asyncio self-pipe through `socket.socketpair()` on Windows. Blocking the class would have made the adapter replay fail at boundary 1b for a reason that has nothing to do with the vendor, and would have hidden that defect behind a green test suite. The guard is therefore **connection-level**: `no_remote_connections` refuses every `connect`, `connect_ex`, `create_connection` and `getaddrinfo` for a non-loopback host, in the test suite and inside `adapter_replay`. A test proves that a remote host is refused, that a remote name will not resolve, and that the engine still starts.

### A defect this work found in its own first draft

The first version of the outcome mapping classified a failed attempt by searching the error message for `"transient"`. `"non-transient"` contains `"transient"`, so a **TLS failure was classified as a retryable network fault** — exactly the confusion S2 exists to prevent. Failure class is now taken from the unchanged M2a transport's own per-attempt classification, no check parses a message, and a regression covers it.

### What 1a does not establish

Passing these tests proves nothing about live connectivity, vendor behaviour, the real payload format, source semantics, a three-year corpus, the basis label, feature readiness or training. The vendor decode and the adapter replay have still never seen a real body; that gap closes only by executing boundary 1b, which is not authorized and has not been run.


## 13. Boundary 1a closure (2026-09-07, responding to `M2B_1A_CODEX_REVIEW.md`)

> Status: `ready_for_review`. Offline only. **Boundary 1b was not executed**: no network call, no download, no real collection, no production or runtime change, no service operation, no Git staging/commit/push, no training, no promotion. Accepted M1 and M2a code is imported unmodified and still passes; the reviewer's report and `_m2_codex_review/review_m2b_1a.py` were not touched.

The previous delivery passed 79 helper tests and still contained five integration defects, because the tests exercised helpers rather than the real call chains. That is the finding, and the regressions added here all drive `SmokeRun -> TimedTransport -> PacedTransport -> LiveSinaTransport`, `run_checks`, or `run_pipeline` end to end.

### B1 - one bounded capture -> decode -> check -> report -> retention path

`capture()` supervised only the download; decoding, the checks and the installed-adapter replay ran afterwards with no active deadline, and the armed CLI called capture alone and printed a status line.

* `SmokeRun.run_pipeline` is now the single armed entry point: capture, decode, checks, `checks.json`, `REPORT.md`, then the Section 8 retention. **One** `Deadline` starts at the top and is handed into `capture()` and then into `run_checks()`, so phases cannot silently reset the budget. The end-to-end regression proves this by exhausting the budget during capture and observing the checks refuse at `checks-start` on the *same* deadline object.
* **Finalization has its own explicitly declared allowance** (`FINALIZE_BUDGET_SEC` = 120 s), because evidence must still be written after the run budget is spent. A separate offline `replay()` states a fresh budget (`REPLAY_BUDGET_SEC` = 600 s) - it is a different run, and the only place a fresh deadline is legitimate.
* `run_checks` derives its deadline from the capture manifest when none is handed in, and **refuses to decode, check or replay at all** when that budget is already spent. The decode of each body and the installed-adapter replay are both supervised, so the bound holds where the blocking actually happens.
* The installed adapter builds its own JS engine with no timeout. `adapter_replay` now swaps `py_mini_racer` in both adapter modules for a shim whose `MiniRacer` carries P-B's own `timeout_sec` and `max_memory`, so the replay inherits the decoder's limits without editing the vendor package.
* **Cancellation and late writes:** the manifest is flushed after **every attempt** (its docstring previously claimed this while flushing per job), and once the capture is finalized `SmokeRun.cancelled` is set - every later `_record`/`_flush` raises. A regression starts a capture, finalizes it, then proves both late paths are refused and the manifest bytes on disk are unchanged.
* Honest limit, unchanged and restated: Python cannot safely kill a thread, and this runner terminates no process, its own or anyone else's. An abandoned worker is a daemon; the run stops, evidence is already on disk, and the process exits without waiting for it.

### B2 - the outcome table now controls capture, not only the report

Capture treated every HTTP 200 as success, so HTML for all three KLC requests still produced wire indices `[1, 2, 3, 4, 5]`, status `completed`, and a checker that then complained requests 2 and 5 were issued after their own skip triggers.

* The table moved to `smoke_outcomes.py` and is imported by **both** sides. `classify_payload` runs in capture, on the response just received, **before** the job's dependent request is issued.
* A payload the table classifies as unusable skips the job's remaining requests and marks the job failed, which feeds the consecutive-failed-job stop. Reproduced result after the fix: HTML on requests 1 and 3 issues `[1, 3]` only, aborts with "2 consecutive failed jobs", and never calls the BJ job.
* Skips carry an explicit **scope**. `job_local` requires an upstream trigger in that job; `run_global` is explained by the run abort. T3 checks both, so an aborted run no longer reports its untouched jobs as contradictions, and a skip with neither justification still fails.
* `EV6` compares capture's recorded payload state with the state the retained bytes classify as now, so the two cannot drift apart silently.

### B3 - TLS stays non-retryable, and 403/429 latch at the headers

* `requests.exceptions.SSLError` inherits `ConnectionError`; catching the broad parent mapped a certificate failure onto the builtin `ConnectionError`, which the unchanged M2a transport correctly treats as transient - so one certificate failure became three attempts, all classified `transient`. `SSLError` is now caught first and raised as `TlsFailure`, a type the transport treats as non-retryable, and the table gives it its own `tls_failure` state. Reproduced result after the fix: **1 call, `retryable=False`, classification `error`**.
* Status handling happened only after full body consumption, so a 403/429 whose body then timed out was reported as a retryable timeout with `aborted_reason` still NULL. The stop status is now **latched from the response headers with no body read at all**. Reproduced result after the fix, for both 403 and 429: **1 call, `RunAborted`, abort latch set**.
* A failed non-200 attempt now retains bounded evidence: the live adapter keeps its last `CapturedResponse`, and the runner writes a size-capped body (256 KiB) plus the headers under `raw/failed_*`, so a failed attempt is no longer evidence-free. A body error there can never mask the status.

### B4 - pacing is measured on actual wire attempts

`started_mono` was taken before `get_with_retries` performed the pacing wait, and retries had no timestamp at all: a correctly paced run of `0.0, 1.5, 3.0, 4.5, 6.0` was recorded as `0.0, 0.0, 1.5, 3.0, 4.5` and failed its own T3 with a 0.000 s gap.

A `TimedTransport` wrapper now sits between `PacedTransport` and whatever callable is injected - live or fake - and stamps the start of **every** attempt, retries included, immediately around the call and therefore after the pacing sleep. T3 validates pacing from those stamps, and a manifest that does not carry one per attempt cannot validate pacing and fails. Reproduced result after the fix: recorded starts equal the actual wire starts, and T3 PASSes; a genuinely unpaced attempt still fails.

### B5 - evidence provenance is now a gate

Three reviewer scenarios returned PASS on evidence that should never have been accepted.

| Gate | What it now enforces | Reviewer scenario |
|---|---|---|
| `EV0` | `run_valid` true, empty `invalidating_changes`, `protected_after` present, deadline provenance present, request records present | an explicitly invalidated capture returned PASS; it is now FAIL |
| `EV3` | the frozen reference hash is **recomputed** from the retained rows and must equal both its own declaration and the manifest's binding; the recomputed value is what enters the deterministic block | a capture hash of 64 zeroes and an extract hash of 64 `f`s returned PASS; it is now FAIL |
| `EV4` | approved calendar SHA-256, akshare version and `hk_js_decode` hash; absent is INCONCLUSIVE, disagreeing is FAIL | the calendar hash was recorded but never compared |
| `EV5` | the frozen symbols/window/basis/threshold contract is compared against the constants the checks apply | the contract was descriptive and unused |
| reference quality | `volume_unit` and `source` are qualified before any fixed ratio is interpreted; a mixed or uninterpretable unit is INCONCLUSIVE with a stated reason | changing every unit to `unknown` returned PASS with an **identical** deterministic hash; it is now INCONCLUSIVE with a **different** hash |

The corruption regressions run through both the initial checks and the retained-evidence `replay()`, and the replay still opens no production database (`db_guard`).

### Additional hardening

* **The offline guard no longer trusts loopback.** This machine routes external HTTP(S) through `http://127.0.0.1:7892`, so "non-loopback only" left a tunnel to the vendor open. `no_remote_connections` now refuses (i) any non-loopback host, (ii) any **configured proxy endpoint**, read from the environment and matched by address without ever contacting it, and (iii) `requests.Session.request` itself, so no genuine HTTP call can begin. The JS engine's own loopback self-pipe still works, which is why the guard remains connection-level rather than a blanket `socket.socket` block. The test suite enters this guard at import.
* **The status line contradicted itself** ("1a implemented" beside "no code has been written"). Corrected at the top of this document and in the ledger.
* **`--plan` reference extraction stays PLANNED by design**, and says so: it is not evidence that live reference extraction has been exercised. Live connectivity, vendor format and semantics remain unverified until boundary 1b is separately authorized.

### Exact commands and actual results

```bash
cd "claude methods/_m2_smoke"
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2_smoke.py       # exit 0, 104 cases, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 smoke_capture.py --plan  # exit 0, F1-F8 all PASS, writes nothing

cd ../..
./backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_codex_review/review_m2b_1a.py"
# exit 1 - the reviewer probe, UNMODIFIED, can no longer reproduce its first defect:
#   AssertionError: {'tls_actual_adapter': {'calls': 1, 'retryable': False,
#                    'attempt_classifications': ['error']}}

cd "claude methods/_m1_closure"                                           # accepted M1, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 67 checks
cd ../_m2_pilot                                                           # accepted M2a, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py             # exit 0, 79 cases, 0 unexpected
```

Because the reviewer probe halts at its first assertion, each of its eight scenarios was also walked through the same integration path in a scratch driver (not added to the repository) to confirm all eight are closed:

| # | Reviewer scenario | Was | Now |
|---|---|---|---|
| 1 | TLS through the real adapter | 3 calls, retryable, all `transient` | 1 call, non-retryable, `error` |
| 2 | 403/429 with a failing body | 3 calls each, retryable, latch NULL | 1 call each, `RunAborted`, latch set |
| 3 | pacing timestamps | recorded `0.0, 0.0, 1.5, 3.0, 4.5`, T3 FAIL | recorded = actual `0.0, 1.5, 3.0, 4.5, 6.0`, T3 PASS |
| 4 | HTML payloads through capture | indices `[1..5]`, `completed`, T3 FAIL | indices `[1, 3]`, `aborted` on 2 consecutive failed jobs, T3 PASS, capability FAIL |
| 5 | explicitly invalidated capture | PASS | EV0 FAIL, capability FAIL |
| 6 | mismatched reference hashes | PASS | EV3 FAIL, capability FAIL |
| 7 | altered units and timestamps | PASS, identical deterministic hash | INCONCLUSIVE, different hash, I3 INCONCLUSIVE |
| 8 | expired deadline at the real check path | entered the replay and blocked | never enters the replay; `DeadlineExceeded` immediately |

### Files

Five source files under `claude methods/_m2_smoke/`, one of them new:

| File | SHA-256 |
|---|---|
| `smoke_capture.py` | `24e1378948efba580f60a18c33149f53b0f36e6acf372b14ce7560500c1e5e44` |
| `smoke_checks.py` | `df8172c1e52ab9a3417e70b9ba52dc5691dec4b51354bbcaa1781749614310c9` |
| `smoke_outcomes.py` (new) | `b9bbdcdbb02e073fa9bd2525af76c31bea8c9a355ba61bd5d3ab240fa40e0049` |
| `sina_klc_decoder.py` (unchanged) | `6599285a2cdd5828e4d87698d01cd39012b2724cf5b76ae1ec6861891c6f1858` |
| `test_m2_smoke.py` | `0cbc4e31551c9401fff18df3b8520f61be9adc9c8c4fcb6295f7fcdb7612b7a7` |

Accepted M2a hashes still match their acceptance pins (`pilot_runner.py` `943a8c3f...`, `test_m2a.py` `5ec05456...`); `acceptance.py` and `transport.py` are untouched, as are `_m1_closure/` and `_m2_codex_review/`. Production metadata is unchanged (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B). No `tmp/`, no `staging/`, no `evidence_*` directory. HEAD `73f266d`; index empty.

### What 1a still does not establish

The vendor decode and the adapter replay have never seen a real body. There is no real sample, and inventing one would repeat the M2a R1 defect. Nothing here says anything about live connectivity, vendor behaviour, the real payload format, source semantics, a three-year corpus, the basis label, feature readiness or training. The capability verdict `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` remains deliberately not an unqualified PASS and authorizes nothing. Boundary 1b is not authorized and has not been run.

## 14. Boundary 1a closure round 3 (2026-09-07, responding to `M2B_1A_CLOSURE_CODEX_REVIEW.md`): R1-R4

> Status: `ready_for_review`. Offline only. **Boundary 1b was not executed**: no network call, no download, no real collection, no production or runtime change, no service operation, no Git staging/commit/push, no training, no promotion. Accepted M1 and M2a code is imported unmodified and still passes; the reviewer's reports, `_m2_codex_review/review_m2b_1a.py` and `_m2_codex_review/review_m2b_1a_closure.py` were not touched and not adapted to pass. The eight scenarios the round-2 review verified closed remain closed.

Scope: exactly the four findings. No accepted stage was reopened and no reviewed row of the outcome table was weakened. Every fix below was then attacked by an independent offline self-review, which reproduced further holes in the first draft of this closure; those are fixed here too and are called out where they apply.

### R1 - every evidence mutation is owned, and abandonment is a refusal, not a note

The boolean `cancelled` guarded two manifest helpers while the raw body was written by a bare `Path.write_bytes`; a worker paused inside that write woke after the aborted manifest was finalized and created a raw file no record bound.

* **`EvidenceStore`** (`smoke_capture.py`) owns the tree. Workers never write into it: a body is **staged** into a sibling `<out_root>.pending/` (outside the tree, no lock held) and then **published** in one critical section that moves the staged file in, appends the request record and rewrites the manifest.
* Publication is **transactional**. The self-review found that the duplicate-record guard, raised inside the publication, would have left the body in the tree with no record - the very orphan R1 forbids. A failing record half now moves the body back to the staging area and pops it from `published`, so publication is all-or-nothing.
* **Abandonment is a store-level refusal, not only an owner-side record.** The self-review reproduced the remaining window on three paths: the seal came *after* the owner had written its abandonment records and fingerprinted the protected inputs, so a worker released in between still published a body and appended a **second** record for the same request - and the checker's index map silently kept the later one. `close_unissued` now calls `refuse_workers()` as the first statement **inside** the critical section that writes those records, so every worker publication, mutation and wire call is refused from that instant. `_record` refuses a second terminal record for one request and `_skip_rest` is idempotent.
* A late call that never reaches the wire is still **logged** as `refused_before_wire`, because the unchanged M2a transport counts the `RunAborted` it receives as an attempt; without that entry the retained records would contradict the transport's own count and read as truncated evidence.
* The **seal** takes the same lock: the final manifest write and `sealed=True` are one critical section, bounded by `SEAL_TIMEOUT_SEC`. A forced seal (lock held past the bound) lets exactly the one in-flight publication complete as a unit, and the run is reported `unsealed`: partial, not retained, nothing more written.
* Post-seal writes are **owner-only**, and the guard is now on the publication rather than only at entry (see R2).

Regressions (all through the real supervised worker): a worker paused at `EvidenceStore.publish` released **after** capture returns; the same for a failed-response body; a worker released **before** the seal at `EvidenceStore.stage`, at `SmokeRun._classify` and at `TimedTransport.__call__`, each asserting the refusal was already in force, no body published, exactly five request records with no duplicate index, and the whole-tree hash listing unchanged; a publication whose record half fails leaving no orphan; and the checker rejecting a manifest that carries a duplicated request index.

### R2 - finalization is bounded, and an abandoned step cannot touch the tree

The 120 s allowance was checked once before an unbounded synchronous cleanup, and an overrun that returned was reported `done`/`PASS`.

* `run_pipeline` runs finalization **step by step** (`plan`, `checks`, `report`, `retain`), each supervised under its own deadline. A step that outlives it is **abandoned**; a step that returns late is an **overrun**. The self-review found the two were conflated when a *later* step could not start: that case now reports `overrun` and names the step that did not run, reserving `abandoned` for a worker the supervisor actually left behind.
* **The token is not enough on its own.** `owner_write` validated the token once and then wrote through a `.part` file **inside** the tree, so a worker abandoned mid-write still landed it. Owner writes now stage outside the tree and perform the move into it as a **guarded** operation: the lock is taken and the token re-checked immediately before `os.replace`. Retention's rename and the staging-directory removal go through the same guard. The honest residue is stated: a worker blocked inside one guarded operation completes exactly that one, and nothing after it is authorized.
* Deleting **inside** the tree is gone. With `keep_raw=False` the raw directory is **detached** by one guarded rename into the staging area and removed there, so an abandoned step cannot keep deleting retained bodies.
* Retention is **one rename**, with the cross-device fallback removed: `shutil.move` is a copy plus a delete, which could duplicate the tree across both reported locations. A cross-device retention now fails with the tree intact and unmoved, and pre-flight **F6 refuses to arm when the output root and the evidence directory are on different volumes**.
* `exit_code_for(record)` is 0 only for a completed run, a PASS or BJ-qualified PASS, **and** `finalize.status == "complete"`.
* Allowances, stated as the code enforces them: the run deadline (900 s), the in-flight read grace (45 s) and finalization (120 s) are measured on the injected clock; the **lock/seal waits (`SEAL_TIMEOUT_SEC` = 30 s) are wall-clock waits on a real lock**, not clock-driven, and the finalization deadline now starts the moment capture returns so the post-capture waits are charged to it. Documented worst case: 900 + 45 + 120 s of deadline-governed work, plus at most one 30 s lock wait on the degraded path.

Regressions: an overrun that returns (`status=overrun`, `remaining_sec < 0`, exit 1, evidence complete); a middle step returning late (`status=overrun`, `step=retain`, `report` in `steps_done`, no abandonment wording); a blocked retention rename (`status=abandoned`, both locations listed, tree byte-identical after release); a blocked owner write, asserting the steps after it never ran and the tree was neither reported nor retained; a cross-device rename failing with the tree intact; `keep_raw=False` dropping the bodies while keeping their hashes and leaving no staging directory; and a worker holding the lock past the seal timeout yielding `unsealed`.

### R3 - every issued request is bound to its actual attempt records

T3 checked an upper ceiling and the timestamps of whatever attempts existed, so `attempts=[]` beside five successful requests validated, and the manifest was flushed per retry group rather than per attempt.

* **Capture**: `TimedTransport` is the attempt boundary. Each attempt carries `request_index` and `attempt_no`; the manifest is persisted at the **start** and the **end** of every attempt, retries included. The sleeper handed to the unchanged M2a transport now flushes before it waits, so a just-classified attempt is on disk before any backoff. Each request record carries `attempt_count` and `attempt_positions`.
* **Checks**: `reconcile_attempts` fails closed on an empty list beside issued requests, a transport count that disagrees with the retained records, missing fields, an unplanned or skipped request, a URL or source mismatch, non-contiguous or resumed numbering, out-of-order attempts, more than three attempts, pacing gaps under 1.5 s, and terminal inconsistency. The self-review added three cross-checks the first draft lacked: every finished attempt's `transport_outcome` must equal what the unchanged M2a transport would derive from its own status/error; a failed request's `transport_outcome`, `retryable` and `failure_kind` must match its final attempt; and an unfinished tail attempt must be genuinely in flight (no status, no error, no classification) and not yet counted by the transport. `attempt_positions` is now read and compared rather than merely written.

Regressions: the reviewer's scenario (`attempts=[]`) FAILs on the initial checks **and** on the retained-evidence replay; truncated, duplicated, misbound, orphaned, miscounted and unfinished lists are rejected; a classification contradicting its status, a wrong `attempt_positions`, a missing `attempt_count` and a failed request whose terminal fields disagree with its final attempt are each rejected; the genuine in-flight shape PASSes while both distortions of it FAIL; two 503s then a 200 are three real attempts, paced including backoff, with the manifest read from disk mid-run already carrying attempt 1's terminal outcome and attempt 2 as in flight; and a retry sequence cut off by the deadline leaves all three attempts on disk.

### R4 - the BJ non-service exception is bound to the KLC history request

The job result was the worst row of the job, so a 404 on request 5 (the outstanding-share endpoint) became `vendor_explicit_absence_at_path` for BJ history, skipped every per-symbol check, and produced `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` although request 4 had served and decoded history.

* `smoke_outcomes.aggregate_job` decides **by request kind**: the KLC history request's row stands, and it is the only request whose explicit 404/410 can yield `NOT_SERVED_AT_PATH`. With history decoded, a failed, absent or unusable auxiliary request is the new `INCONCLUSIVE_AUXILIARY`.
* The self-review found the first draft had **downgraded a reviewed row**: a 403/429 on the auxiliary request - `aborts_run`, "fail the capability unconditionally" in the reviewed table - was being softened to inconclusive auxiliary evidence. An auxiliary row that aborts the run is now `FAILED`, and `transport_state_of` keeps a header-latched vendor stop recorded as `aborted` classified as `vendor_stop`, so the run-abort rule still fires.
* An auxiliary request the **run abort** never issued is `INCONCLUSIVE_AUXILIARY` with that reason stated, rather than being reported as an unexplained skip.
* For `INCONCLUSIVE_AUXILIARY` the per-symbol **history checks still run**; `D5` is INCONCLUSIVE ("missing AUXILIARY evidence, not history evidence"), `U4` is not computable and `R1` records why no adapter replay ran. The job is FAIL if any required check on it fails - which includes `T2`/`S2` on a served but unusable auxiliary body - and otherwise INCONCLUSIVE. Never PASS, never the BJ-qualified PASS.
* `C2` records which request decided it (`decided_by: klc`), the per-kind request summary and `auxiliary_evidence` in **both** the served and the not-served branch.

Regressions: a 404 and a 410 on request 4 are the documented finding; a 404 on request 5 with valid history is `INCONCLUSIVE_AUXILIARY` -> per-job INCONCLUSIVE -> capability INCONCLUSIVE with 22 BJ checks still run; a 403 and a 429 on request 5 are `FAILED` -> capability FAIL; a run-global skip of request 5 is inconclusive auxiliary evidence; an empty or markup auxiliary 200 fails the job on its own required checks; and invalid history plus an absent auxiliary endpoint is FAIL - the absence masks nothing.

### Exact commands and actual results

```bash
cd "claude methods/_m2_smoke"
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2_smoke.py       # exit 0, 132 cases, 0 unexpected (104 -> 132)
../../backend/.venv/Scripts/python.exe -B -X utf8 smoke_capture.py --plan  # exit 0, F1-F8 all PASS, writes nothing

cd ../..
./backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_codex_review/review_m2b_1a_closure.py"
# exit 1 - the UNMODIFIED round-2 driver walks its eight closed scenarios and then can no longer
# reproduce its first remaining defect (R1): AssertionError at `assert waiting.is_set() and
# late_run.cancelled` - the gate it plants on Path.write_bytes at the final raw path is never
# reached, because bodies are staged outside the tree and published by os.replace under the seal.

cd "claude methods/_m1_closure"                                           # accepted M1, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 67 checks
cd ../_m2_pilot                                                           # accepted M2a, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py             # exit 0, 79 cases, 0 unexpected

git diff --check                                                          # exit 0; CRLF warnings only
```

Because the round-2 driver halts at its first assertion, its remaining scenarios were replayed with the same fixtures in scratch drivers (not added to the repository):

| Reviewer scenario | Was | Now |
|---|---|---|
| R1 worker paused at the raw write, released after finalization | raw file created with `cancelled=True`, unindexed | the gate is never reached; in the delivered event-controlled variants the publication is refused, the tree and manifest are byte-identical, the staged bytes discarded |
| R1 worker released in the pre-seal window (found by self-review, wire-call path) | 7 request entries, duplicate indices `[1, 2]`, T3 PASS | 5 entries, no duplicates, refusal already in force when the worker resumed, no body published, T3 PASS on consistent evidence |
| R2 cleanup consumes 121 s of the 120 s budget | `phase=done`, `capability=PASS`, `remaining_sec=-1.0` | `phase=incomplete_finalization`, `finalize.status=overrun`, `remaining_sec=-1.0`, exit code 1, evidence retained |
| R3 valid capture with `attempts=[]` | T3 PASS, capability PASS | T3 FAIL ("5 issued requests carry no attempt evidence at all; the transport counted 5 attempts but 0 attempt records are retained (truncated or padded evidence); request 1 is recorded ok but has no attempt record; ... request 5 ...") and capability FAIL, on first check and on replay |
| R4 request 4 = 200 decoded, request 5 = 404 | C2 `vendor_explicit_absence_at_path`, `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE`, per-symbol checks skipped | job `INCONCLUSIVE_AUXILIARY`, per-job INCONCLUSIVE, capability INCONCLUSIVE, C2 `pre_boundary_history_served` decided by `klc` with `auxiliary_evidence: absent`, 22 BJ checks run |
| R4 request 4 = 404 (the only documented route) | `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` | unchanged: `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE`, C2 `vendor_explicit_absence_at_path`, request 5 skipped |

### Files

| File | SHA-256 |
|---|---|
| `smoke_capture.py` | `b17f8d0d624c53ed189562566021f11c2e4a9f1bcad0add8713fc66dbc060156` |
| `smoke_checks.py` | `b2b8aaa9487bea54464386c90f9ccf3f2e11443d395a4a08a8c8e98a1421324c` |
| `smoke_outcomes.py` | `53a4301988bc5a6ced576718c8cab7a1a143ac2b798d9fc8d5f588e35d5b7a9e` |
| `sina_klc_decoder.py` (unchanged) | `6599285a2cdd5828e4d87698d01cd39012b2724cf5b76ae1ec6861891c6f1858` |
| `test_m2_smoke.py` | `5cb4cc3e1075b09054132398491657595ce72bd91694469ba4e1d275b57a3064` |

Accepted M2a pins still match (`pilot_runner.py` `943a8c3f...`, `test_m2a.py` `5ec05456...`, `acceptance.py` `efa46c13...`, `transport.py` `f57bbc6c...`); `_m1_closure/` untouched. Reviewer artefacts untouched: `review_m2b_1a.py` `df22a06f...`, `review_m2b_1a_closure.py` `2a38ba4c...`. The capture manifest schema is `m2b.capture_manifest.v3`. Production metadata unchanged (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B). No `tmp/`, `staging/`, `*.pending` or `evidence_*` directory exists. HEAD `73f266d`; index empty.

### Remaining limitations

* No thread is killed and no process terminated. What the store guarantees is that a worker refused or revoked cannot publish into, write into or clean up the evidence tree; what it cannot guarantee is when that worker's blocked call returns. A worker blocked inside one guarded operation completes exactly that one - at most one atomic rename - and nothing afterwards.
* A forced seal (lock not obtained within 30 s) lets exactly one in-flight publication complete as a unit; the run is reported unsealed and is not retained. A bounded, reported degradation.
* The lock and seal waits are wall-clock waits on a real lock, not on the injected clock. They are bounded at 30 s each and the finalization deadline starts before them, but they are not themselves clock-driven, so a test cannot make them expire without patching the constant.
* The vendor decode and the adapter replay have still never seen a real body; nothing here says anything about live connectivity, the real payload format, source semantics, a three-year corpus, the basis label, feature readiness or training. `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` remains not an unqualified PASS, is reachable only through an explicit 404/410 on the KLC history request, and authorizes nothing. Boundary 1b is not authorized and has not been run.


## 15. Boundary 1a technical validation (2026-09-08, `M2B_1A_ACCEPTANCE_CODEX.md`)

> Codex validated boundary 1a **for the offline scope**. That is a reviewer's technical
> verdict on this bounded stage, **not** user authorization for live work and **not** a
> statement that M2 is finished. Boundary 1b remains `proposed` and unauthorized; nothing
> in this section permits a request to be issued.

### What was validated, and what it does not cover

| Validated | Not validated by it |
|---|---|
| The offline engineering path: capture, decode, checks, retention and replay, and their synthetic failure handling. The four blocking findings R1–R4 of `M2B_1A_CLOSURE_CODEX_REVIEW.md` are closed on the reviewed revision, with no remaining blocker for this stage. | Real vendor response semantics. No real Sina body has yet proved decoder behaviour, identity, units, adjustment basis, session coverage or adapter losses. The three-year corpus, the 52-symbol pilot, the P1 basis label, production promotion and model training are untouched by this acceptance. |

The reviewer's own summary of the evidence is **"share with caveats"**, and the 132 test
cases are a description of coverage, not a readiness metric.

### Reproduced locally on 2026-09-08, before writing this section

```bash
./backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_smoke/test_m2_smoke.py"
# exit 0, 132 cases, 0 unexpected
./backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_codex_review/review_m2b_1a_round3.py"
# exit 0, baseline and independent R1-R4 closure probes PASS
./backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_smoke/smoke_capture.py" --plan
# exit 0, F1-F8 PASS, reference extraction PLANNED, nothing written
```

### Frozen revision

The five reviewed hashes are unchanged by this section, which edits documentation only:

| File under `_m2_smoke/` | SHA-256 |
|---|---|
| `smoke_capture.py` | `b17f8d0d624c53ed189562566021f11c2e4a9f1bcad0add8713fc66dbc060156` |
| `smoke_checks.py` | `b2b8aaa9487bea54464386c90f9ccf3f2e11443d395a4a08a8c8e98a1421324c` |
| `smoke_outcomes.py` | `53a4301988bc5a6ced576718c8cab7a1a143ac2b798d9fc8d5f588e35d5b7a9e` |
| `sina_klc_decoder.py` | `6599285a2cdd5828e4d87698d01cd39012b2724cf5b76ae1ec6861891c6f1858` |
| `test_m2_smoke.py` | `5cb4cc3e1075b09054132398491657595ce72bd91694469ba4e1d275b57a3064` |

Accepted M2a pins still match (`pilot_runner.py` `943a8c3f…`, `test_m2a.py` `5ec05456…`,
`acceptance.py` `efa46c13…`, `transport.py` `f57bbc6c…`); `_m1_closure/` and every reviewer
artefact are untouched (`review_m2b_1a.py` `df22a06f…`, `review_m2b_1a_closure.py`
`2a38ba4c…`, `review_m2b_1a_round3.py` `7b200b49…`). Production metadata unchanged
(`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700;
`market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B). No `tmp/`,
`staging/`, `*.pending` or `evidence_*` directory. HEAD `73f266d`; index empty.

### The reviewer's four required caveats, carried into this document

1. **Offline only.** Restated in the table above and in Section 10.
2. **Cancellation is not thread termination.** A worker already inside one guarded
   filesystem operation may finish that operation; a forced-unsealed capture is explicitly
   partial and is not retained. The tests validate those *reported degraded outcomes*, not
   immunity to an indefinitely stuck OS or disk. (Section 14, "Remaining limitations".)
3. **The timing restriction is an operator condition, not a checked gate.** F1–F8 read no
   clock and the `--plan` output prints no time, so a green pre-flight does not establish
   timing-window compliance. Immediately before any authorized run the operator must verify
   and record the Asia/Shanghai wall clock — before 09:15 or after 15:30 — in `REPORT.md`.
   F8 must be passed by the stack already being stopped; services are never started or
   stopped to make it pass. Sections 3 and 4 now say this where the rule lives.
4. **The stale qfq narrative is corrected.** Section 3 said production's `adjust="qfq"`
   path multiplies the klc OHLC by its factor. It **divides** (`stock_zh_a_sina.py:293-296`);
   the **hfq** branch is the one that multiplies (`:254-257`), and `adjust=""` applies
   neither (`:219-232`). Only the narrative was wrong: B2 has read these three properties out
   of the installed source since the round-2 closure, no accepted code was modified, and no
   raw-data basis was reinterpreted to match the old sentence.

### What boundary 1b still needs, and what it is when it comes

Not a consequence of this validation. It needs **the user's explicit, separate
instruction**, and that instruction must also settle the evidence-retention choice: whether
the captured raw bodies and the minimal frozen reference extract are retained **locally
only**, under the reviewed evidence directory, so that independent offline replay is
possible. The reviewer recommends retaining them locally; no Git staging, external upload or
production promotion is authorized either way.

When authorized, it is **one** run of the existing three-symbol smoke: `SH600011`,
`SH000300`, `BJ920000` in the fixed five-request order, at most 15 attempts including
per-request retries, concurrency 1, spacing ≥ 1.5 s, unchanged TLS checks and abort rules, a
fresh passing pre-flight, and the operator-verified timing condition above. Endpoints are not
substituted and symbols are not expanded after a failure. The report records the process exit
code and pipeline summary alongside the retained manifest, checks, report, hashes and frozen
reference, plus the actual request count, duration, failures, coverage and unresolved
semantics; the deterministic checks are then repeated offline from the retained evidence. It
stops at `ready_for_review` for Codex. It does not advance to the 52-symbol pilot, full-market
rebuilding, basis labelling, production writes or training.


## 16. Boundary 1b execution record — one run, 2026-09-08, run_id `20260908T021722Z`

> Status: `ready_for_review` for Codex. **Capability verdict: FAIL.** The run was authorized by
> the user on 2026-09-08 for exactly one execution and executed exactly once. Evidence is
> retained locally at `claude methods/_m2_smoke/evidence_20260908T021722Z/`. Nothing was
> committed, pushed, staged, promoted or trained; no service was started or stopped; no
> production database was written; no endpoint was substituted and no symbol was added.

### The timing condition was NOT satisfied, and the run proceeded on an explicit instruction

| | |
|---|---|
| Verified immediately before arming | 2026-09-08 **10:17:14 Asia/Shanghai**, Tuesday (02:17:14 UTC) |
| Required | before 09:15 or after 15:30 Asia/Shanghai |
| Result | **VIOLATED** — inside continuous trading |
| Action | I reported the violation and recommended holding until the window opened (about 5 h 20 m later). The user chose to run anyway. Recorded here because the operator condition exists precisely so this cannot be silent. |

Observed consequence in this capture: **none visible.** Both decoded series end at
**2026-09-07**, the previous session; neither carries a partial bar for the in-progress
2026-09-08 session. That is one observation on two symbols, not a rule — it does not establish
that the vendor never serves a partial current-session bar, and the design's own defence (rows
after 2026-09-04 are recorded and excluded from the window checks) was what would have
contained it in any case.

### What actually happened on the wire

| # | job | request | outcome | HTTP | bytes | payload state |
|---|---|---|---|---|---|---|
| 1 | `sh600011` | KLC history | issued | **200** | 73,353 | `undecodable` |
| 2 | `sh600011` | outstanding share | **not issued** (job-local skip) | — | — | — |
| 3 | `sh000300` | KLC history | issued | **200** | 100,465 | `undecodable` |
| 4 | `bj920000` | KLC history | **not issued** (run-global skip) | — | — | — |
| 5 | `bj920000` | outstanding share | **not issued** (run-global skip) | — | — | — |

**2 HTTP attempts** of a 5-request plan, against a ceiling of 15; **0 retries**. Attempt starts
0.000 s and 1.500 s on the monotonic clock — the pacing floor of 1.5 s held exactly, with a
1.203 s sleep inserted. Capture consumed **1.97 s of the 900 s** deadline; finalization
**0.109 s of its 120 s** allowance and completed; process exit code **1**. Both served URLs
equalled the requested URLs. Both responses were `application/x-javascript`, gzip, from
`Tengine`, with `Date` headers 02:17:08Z and 02:17:25Z.

Run status `aborted`, reason *"2 consecutive failed jobs; stopping before any further request"* —
the documented consecutive-failed-job stop firing correctly. **`BJ920000` was never contacted**,
so the BJ code-history question C2 is completely unanswered, as is Q1's amount/outstanding-share
separation, which needed request 2.

### Verdicts

| scope | verdict |
|---|---|
| job `sh600011` | INCONCLUSIVE (`INCONCLUSIVE_DECODE`) |
| job `sh000300` | INCONCLUSIVE (`INCONCLUSIVE_DECODE`) |
| job `bj920000` | FAIL (never issued) |
| **capability** | **FAIL** |

Every evidence gate passed: `EV0` (envelope complete and self-certified), `EV3` (frozen
reference hash recomputed and bound), `EV4` (calendar / akshare / `hk_js_decode` pins), `EV5`
(threshold contract), `EV2` on both bodies (bytes-to-text reproduces the captured
`response.text`), `T1`/`T2`/`T3`. The failure is `S2` on both bodies.

### D1 — the decoder is too strict for the real body. This is our defect, not the vendor's.

`sina_klc_decoder.extract_payload` requires the body to **end** at the assignment:

```python
_VAR_RE = re.compile(r'^\s*var\s+(\w+)\s*=\s*"([^"]*)"\s*;?\s*$', re.DOTALL)
```

The real body is an assignment **followed by a trailer**:

```text
var KLC_K2_sh600011="<73,050 chars>";

/* <281 chars of base64> */
```

(`sh000300` is the same shape: `var KLC_KL_sh000300="<100,135 chars>";` plus a 308-char
`/* … */` trailer.) The synthetic envelopes never had a trailer, so no offline test could have
caught it. The **installed adapter's own positional extraction**
(`text.split("=")[1].split(";")[0].replace('"', "")`) returns exactly the payload between the
quotes on both bodies — verified byte for byte against the retained evidence — so the adapter
would have decoded them; it was the stricter cross-check, added deliberately so the adapter's
truncation-prone extraction could not silently differ, that rejected the whole body.

**Offline analysis of the retained bytes** (read-only, no network, not part of the run's
verdict, not a check result): the payloads decode with the **pinned** routine and look sound.

| | `sh600011` | `sh000300` |
|---|---|---|
| branch, derived from the header | **O** (3466) | **D** (1479) |
| rows | 5,935 | 5,987 |
| span | 2001-12-06 … 2026-09-07 | 2002-01-04 … 2026-09-07 |
| keys | `date, open, high, low, close, volume, amount, prevclose` (+ `postVol`/`postAmt`) | `date, open, high, low, close, volume` (**no** `amount`) |
| dates strictly increasing, no duplicates | yes | yes |
| rows after 2026-09-04 | 1 (2026-09-07) | 1 (2026-09-07) |

This matches Section 10's stated expectations: branch `O` with `amount` for the stock, and the
index carrying no `amount`. `sh600011`'s first row is **2001-12-06, its listing date**, so the
vendor served the whole owed window and more. None of this is a check result — the required
checks never ran, and identity, units, basis and coverage remain **unverified**.

### D2 — pre-flight F8 fails OPEN on this machine, and always has

`default_process_lister` runs the PowerShell inventory with `subprocess.run(..., text=True)`,
which decodes stdout **strictly** as UTF-8. This machine's inventory contains byte `0xb9` (an
ANSI-encoded path), so the reader thread raises `UnicodeDecodeError`, `stdout` comes back
**empty**, `json.loads(out.stdout or "[]")` yields `[]`, F8 matches nothing and reports
**PASS**. The manifest records the consequence plainly: `process_inventory_size: 0`.

A decode-tolerant repeat of the same query sees **289 processes**. F8's PASS **in this run** is
therefore vacuous: it did not establish that the local stack was stopped.

> **Correction (2026-09-08, after `M2B_1B_CODEX_HANDOFF.md`).** An earlier version of this
> paragraph also claimed that *every* `--plan` output this project has produced on this machine
> was vacuous. That claim is withdrawn: it was not supported by evidence. The failure is
> **condition-dependent** — it occurs only when the inventory happens to contain a byte the
> strict UTF-8 decode rejects. It reproduced in this run and in my own probes on 2026-09-08,
> and it did **not** reproduce in Codex's probe, which returned 293 processes with no Unicode
> error. The retained `plan.txt` records only `F8  PASS  local stack stopped` and no inventory
> size, so whether any given historical F8 PASS was vacuous **cannot be determined** from the
> outputs that exist. What is established is this run's `process_inventory_size: 0`, and that
> the check could fail open at all.

Independently checked after the run, decode-tolerantly: **0 genuine project-stack processes**
were running (no `backend/scripts/*_loop.py`, no `run_stack`/`ensure_stack`, no `uvicorn`, no
`npm dev`). So the stack really was stopped and this run was not compromised — but that is my
out-of-band check, not F8's. The protected-input fingerprints agree: no invalidating change.

Not fixed here. Both D1 and D2 are code changes outside this authorization, and the reviewed
hashes are deliberately frozen for Codex.

### Offline replay from retained evidence

```bash
./backend/.venv/Scripts/python.exe -B -X utf8 -c "import sys;sys.path.insert(0,'claude methods/_m2_smoke');import smoke_checks;print(smoke_checks.replay('claude methods/_m2_smoke/evidence_20260908T021722Z')['matches_stored'])"
```

Deterministic block reproduced **byte for byte**: `02e1b76483cd659b5a16f1df78304392e37effcc706a5c325317eefd42448703`,
`matches_stored: True`, under `db_guard` so no production database was opened. `R1urls` PASS.
The per-symbol `R1` adapter replay did not run, because no job had all of its requests served.

### Evidence, retained locally only

`claude methods/_m2_smoke/evidence_20260908T021722Z/` — untracked, never staged, never uploaded:

| Path | Bytes |
|---|---|
| `raw/01_sh600011_klc_kl.js.bin` | 73,353 (sha256 `adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02`) |
| `raw/03_sh000300_klc_kl.js.bin` | 100,465 (sha256 `ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647`) |
| `reference/reference_extract.json` | 522,953 — frozen read-only extract, 538 / 538 / 501 rows, content sha256 `3a599027a963531f…` |
| `capture_manifest.json`, `checks.json`, `REPORT.md`, `plan.txt` | the manifest, deterministic checks, report and the authorized plan |

### State after the run

Production metadata unchanged (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns
1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B);
`invalidating_changes: []`, `run_valid: true`. The five reviewed source hashes are unchanged.
`tmp/m2b_smoke_20260908T021722Z/` was removed at cleanup and no `*.pending` directory remains
(`tmp/` itself is present and empty). No `staging/`. HEAD `73f266d`, index empty.
`test_m2_smoke.py` still 132 cases, exit 0.

### What this run did and did not establish

**Established:** the live transport, TLS path, pacing, attempt accounting, outcome table,
evidence store, finalization, retention and deterministic replay all worked on real traffic, and
the vendor serves full decodable history for `SH600011` and `SH000300` at the reconfirmed URLs.

**Not established:** identity, units, adjustment basis, session coverage, adapter losses and the
`amount` / outstanding-share separation — every required check on those was blocked by D1. The
BJ code-history question is untouched. Nothing here advances the 52-symbol pilot, the basis
label, the corpus, production promotion or training, and the capability verdict is FAIL.

**Recommended next step, for the user and Codex to decide — not taken here:** fix D1 (accept a
trailing comment after the assignment while keeping the adapter cross-check) and D2 (read the
process inventory as bytes and decode tolerantly, and fail CLOSED when the inventory cannot be
read), add regressions built from the retained real bodies, and only then consider a second
authorized run inside the timing window.


## 17. D1/D2 offline correction (2026-09-08, responding to `M2B_1B_CODEX_HANDOFF.md`)

> Status: `ready_for_review` for Codex. **Offline only.** No live call, no production write,
> no service operation, no commit, push or training. The original run-`20260908T021722Z`
> evidence tree, its manifest, its `checks.json` and its **FAIL** are untouched and were
> verified byte-identical before and after this work. Source-capability acceptance is still
> **not** passed, and no new capture is authorized.

### D1 — bounded trailer support

`sina_klc_decoder._VAR_RE` required the body to **end** at the assignment, so both retained
real bodies were rejected. The real grammar is an assignment followed by a non-executable
block comment:

```text
var KLC_K2_sh600011="<73,050 chars>";

/* <281 chars> */
```

The fix is a **scanner, not a looser pattern** (`_scan_trailer`). `_VAR_RE` still matches the
assignment strictly, anchored, up to its semicolon; the remainder is then walked and only
whitespace and **closed** `/* … */` blocks are accepted, bounded at 8,192 characters and 8
comments. Everything else is refused: a second statement, another assignment, a bare
identifier, a call, a line comment, an unterminated comment, an oversized trailer. Strict
bytes-to-text, dual-extraction agreement, the pinned routine hash, the payload/row/JS limits
and every existing malformed-input refusal are unchanged, and `decode_klc` now records the
trailer shape in its result. Raw downloaded JavaScript is still never evaluated — only the
base64 payload is passed to the pinned routine.

On the retained bodies (referenced by SHA-256 in the tests, so a substituted file fails rather
than passes): `sh600011` → branch **O**, 5,935 rows, `amount` present; `sh000300` → branch
**D**, 5,987 rows, no `amount`. Both single-comment trailers of 281 and 308 characters.

### D2 — fail-closed inventory and accurate stack recognition

Three separate defects, all closed:

1. **Fail-open on missing evidence.** `default_process_lister` swallowed every failure into
   `[]`. It now raises `InventoryUnavailable` on a non-zero exit, blank output, a strict-decode
   failure, invalid JSON, a non-list, an **empty** list, or a record missing `ProcessId` or the
   `CommandLine` column. F8 treats each of those as **FAIL**, and separately fails an empty
   inventory, because a machine always has processes: an empty list is a failed query, not an
   idle machine.
2. **Encoding.** The producer now states its own encoding
   (`[Console]::OutputEncoding = …UTF8Encoding($false)`) and the parent captures **bytes** and
   decodes them strictly as `utf-8-sig`. Lossy replacement is deliberately *not* the fallback,
   and the refusal message says so: a mangled command line could hide a running worker.
3. **Recognition.** The old `uvicorn\b.*backend` regex could not match the command
   `run_stack.ps1:338` actually uses. Matching is now structural — `classify_process` tokenizes
   the command line, honours quoting, and stops at the first inline-program flag (`-c`,
   `-Command`, `-EncodedCommand`), so a shell **quoting** those names is not mistaken for one
   running them. Recognised: `python -X utf8 -m uvicorn app.main:app …`; any
   `backend/scripts/*.py` worker; `node …/vite/bin/vite.js` and `npm run dev`;
   `run_stack.ps1` / `ensure_stack.ps1`. A process running under an image the stack uses
   (`python`, `pythonw`, `node`, `powershell`, `pwsh`, `uvicorn`) whose command line is
   **unreadable** is reported `ambiguous` and fails F8 — unproven absence is not absence.

A regression asserts that no smoke code path contains `Start-Process`, `Stop-Process`,
`taskkill`, `os.kill`, `terminate()` or a service verb, and that the only subprocesses it
launches are `git`, `ps` and `powershell`. **No service is ever started or stopped to make a
pre-flight pass.**

### Proof that a failed F8 refuses before anything happens

`L-D2 a failed F8 refuses BEFORE any HTTP call or run-tree creation` drives the real
`SmokeRun.capture` with an unavailable inventory and a transport factory that raises if it is
ever called. The result: `PreflightError` naming F8, the transport never invoked, and neither
`tmp/` nor the evidence directory created.

### Commands and results

```bash
cd "claude methods/_m2_smoke" && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2_smoke.py
# exit 0, 146 cases, 0 unexpected  (132 -> 146; the 14 new cases are the L- block)
../../backend/.venv/Scripts/python.exe -B -X utf8 ../_m2_pilot/test_m2a.py     # exit 0, 79 cases
cd ../_m1_closure
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py         # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py     # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py     # exit 0, 67 checks
```

The reviewer's `review_m2b_1b.py` is unmodified and now **exits 1**, as expected: its first
assertion, `replayed['matches_stored'] is True`, no longer holds — see the provenance note
below — and its D2 assertions (`f8([]) == 'PASS'`, `f8(api_command) == 'PASS'`,
`default_process_lister() == []` on a failed subprocess) now describe closed defects.

### Changed hashes

| File under `_m2_smoke/` | before | after |
|---|---|---|
| `sina_klc_decoder.py` | `6599285a2cdd5828…` | `d39e02c8cd736e10c29ae6efc12ce540eeadf790552dcdc14debcf5f18461fee` |
| `smoke_capture.py` | `b17f8d0d624c53ed…` | `fadcaf3cc4a3dcbe7e77afa8c6336d6a35aa5c57b2a5d036960d4e3009639b88` |
| `test_m2_smoke.py` | `5cb4cc3e1075b090…` | `748b5131882e54db5fb45ca2eb549e3a6c4156e51d52ced9fba70d4722517dd2` |
| `smoke_checks.py` | `b2b8aaa9487bea54…` | unchanged |
| `smoke_outcomes.py` | `53a4301988bc5a6c…` | unchanged |

Accepted M1 and M2a artefacts and every historical reviewer script are untouched.

### The revised offline check pass, recorded separately

`claude methods/_m2_smoke/revision_20260908T021722Z_d1d2/` re-checks the **same retained
bytes** with the corrected implementation. It is not a capture: the original tree was copied,
never moved or edited, and no request or database open occurred.

Result: **capability FAIL, deliberately.** `sh000300` now passes every one of its required
semantic checks — D1–D4, `I2` (close ratio within tolerance across 10 sessions), `I3` (volume
ratio ≈ 1), `C3` (first 2002-01-04 ≤ 2022-08-24, last 2026-09-07 ≥ the reference tail, span
complete) and **`R1`, the installed adapter replayed on the real body, returning 5,987 rows
with 0 fabricated dates**. The run as a whole still fails, correctly:

* `EV6` reports that the capture recorded both bodies as `undecodable` while the retained bytes
  now classify as `decoded`;
* `T3` refuses the skip of request 2, whose trigger no longer exists;
* `sh600011` and `bj920000` never had all their requests issued.

**The original run is not retro-promoted.** A capability PASS needs a new authorized capture
under the corrected implementation, and this revision neither is one nor substitutes for one.

### Provenance note: the original deterministic hash and `matches_stored`

The deterministic block is a function of the retained bytes **and** the implementation that
interprets them. D1 changed the decoder, so replaying the original evidence with the corrected
code necessarily yields a different hash — `784ffa6621c3e708…` instead of
`02e1b76483cd659b…` — and `matches_stored: False`. The original hash is still reproducible,
but only against the frozen pre-fix implementation, whose five SHA-256s are recorded in
`revision_20260908T021722Z_d1d2/PROVENANCE.json` alongside the new ones. Nothing about the
original result changed; the code that reads it did.

*Suggestion for Codex, not implemented unilaterally:* the deterministic block could carry the
implementation fingerprint itself, so a replay under different code is visibly a different
revision rather than an unexplained mismatch.

### Original receipts, preserved not reconstructed

`claude methods/_m2_smoke/receipts_20260908T021722Z/` holds the original console receipts of
the 1b run, copied byte for byte with their original modification times: the pipeline-summary
stdout (which is where the exit code 1 and the 0.109 s finalization figure come from), the
stderr carrying the two `UnicodeDecodeError` tracebacks, the shell's `EXIT_CODE` line, the
background task's own output line, and the pre-execution Asia/Shanghai clock verification
recording the timing-window **violation**. `RECEIPTS.json` states their SHA-256s, sources and
original mtimes, and records that the user's authorization and out-of-window waiver were given
in conversation and are not reproduced here. Nothing was reconstructed or backdated. **That
waiver is not standing permission for another out-of-window run.**

### What is still not established

No new live evidence exists. `BJ920000` has still never been contacted. Identity, units,
adjustment basis, session coverage and adapter losses for `SH600011` remain unverified,
because its auxiliary request was never issued. Source-capability acceptance remains **FAIL**.
Nothing here advances the 52-symbol pilot, the basis label, the corpus, production writes or
training, and no further live run is authorized by this work.


## 18. D2 process-gate closure (2026-09-08, responding to `M2B_D1D2_CODEX_REVIEW.md`)

> Status: `ready_for_review` for Codex. **Offline only.** No live capture, production
> database operation, service action, 52-symbol work, Git staging/commit/push or training.
> D1 stands as validated and was not touched. The sealed 1b evidence, its FAIL, the
> receipts and every reviewer script are unchanged. M2b source-capability acceptance
> remains **FAIL**, and no new capture is authorized.

The review validated D1 and reproduced **seven F8 false passes**, each of which went
through the real `preflight()` and returned PASS where it should have returned FAIL. All
seven are closed, in the three bounded groups the review defined. No general shell parser
was written and no existing safety check was weakened.

### P1a — incomplete or unidentifiable records

`cmdline_available` was `command is not None`, so an **empty or whitespace-only** command
line counted as readable evidence, and a record with no `Name` and a null `CommandLine` was
classified as an unrelated image.

* `_normalize_inventory` now sets `cmdline_available` only when the command line is present
  **and non-blank**, and rejects a non-string `Name` or `CommandLine` outright.
* `classify_process` treats a blank command line exactly like a missing one, and a record
  with **neither** a usable image name **nor** a readable command line is `ambiguous` —
  unidentifiable never collapses into unrelated.
* The legitimate `System` / `Registry` null-command records still classify as unrelated,
  because they carry an identifying name that is not one the stack runs under.

### P1b — backend-relative worker paths

The matcher required `backend/scripts/` inside the command line, so the same worker started
from the backend working directory — `python.exe -X utf8 scripts\control_plane_loop.py` —
read as a stopped machine.

Recognition is now by **basename against the known entrypoints** that `run_stack.ps1`
starts (`control_plane_loop.py`, `reference_data_loop.py`, `full_market_feature_loop.py`,
`market_history_refresh_loop.py`, `capital_flow_refresh_loop.py`,
`instrument_catalog_refresh_loop.py`, `full_market_calibration_loop.py`,
`codex_market_pulse.py`, `codex_decision_review.py`, `automation_loop.py`), in absolute,
backend-relative or bare form, **and** the absolute `backend/scripts/*.py` rule is kept for
scripts not on that list. The interpreter identity check is what stops an editor or a grep
that merely names one of those files from matching.

### P1c — inline execution is not the same as discussion

Everything after `-c` / `-Command` was discarded, which removed real launches along with
innocent quoted text. `python.exe -c "import uvicorn; uvicorn.run('app.main:app', …)"` runs
the API **inside that process**; no child has to appear for it to be running.

`_inline_verdict` now inspects the inline program — it is **read, never evaluated** — and
returns one of three answers, bounded at 4,096 characters:

| Inline program | Verdict |
|---|---|
| contains a recognised launch shape (`uvicorn.run(`, `runpy.run_path(`, `exec(open(`, `subprocess.*(`, `os.system/exec*/spawn*(`; PowerShell `&`/`.` on a `.ps1`, `Start-Process`, `Invoke-Expression`/`iex`, an inline `-m uvicorn`) **and** names a stack target | `stack` |
| names a stack target only inside a literal `print(...)` or a read-only PowerShell verb (`Get-Item`, `Get-Content`, `Select-String`, `Test-Path`, `ls`, `cat`, …) | `other` |
| names a stack target in any **other** shape, or is longer than the bound | `ambiguous` → F8 FAIL |
| names no stack target at all | `other` |

The comment that claimed inline code is necessarily only *talking about* a launch is gone;
it was the assumption behind the defect.

### The regression that has to keep working

`L-D2 no code path in the smoke starts or stops a process` began failing when `Start-Process`
entered the source as a **detection pattern**. It was tightened rather than relaxed:
`taskkill`, `os.kill`, `terminate()` and the service verbs remain banned outright as text;
`Start-Process` and `Stop-Process` are permitted **only** on a `re.compile(...)` line or in a
comment, never in a string this module executes; the only subprocesses launched are still
`git`, `ps` and `powershell`; and the one PowerShell program the module runs is asserted to
contain no mutating verb. **No service is started or stopped by any test.**

### Commands and results

```bash
cd "claude methods/_m2_smoke" && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2_smoke.py
# exit 0, 158 cases, 0 unexpected  (146 -> 158; the 12 new cases are the M- block)

cd ../.. && ./backend/.venv/Scripts/python.exe -B -X utf8 \
    "claude methods/_m2_codex_review/review_m2b_d1d2.py"
# exit 0, 55 checks, 55 passed, 0 failures   (was exit 1, 48/55)   -- driver UNCHANGED

./backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_pilot/test_m2a.py"   # 79 cases
cd "claude methods/_m1_closure"
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 67 checks
```

The reviewer's driver is byte-for-byte unchanged and now reports **55/55**.

### Changed hashes

| File under `_m2_smoke/` | before | after |
|---|---|---|
| `smoke_capture.py` | `fadcaf3cc4a3dcbe…` | `37942c386bc5659d574db2354b657d9b8a6ea78dbd234323ea9a38ad7f8f6312` |
| `test_m2_smoke.py` | `748b5131882e54db…` | `4103f03b9c5c52192cceb217171a74a4be3614075a3621c4eca9b99aa975a4b3` |
| `sina_klc_decoder.py` (D1, untouched) | | `d39e02c8cd736e10c29ae6efc12ce540eeadf790552dcdc14debcf5f18461fee` |
| `smoke_checks.py` | | unchanged `b2b8aaa9487bea54…` |
| `smoke_outcomes.py` | | unchanged `53a4301988bc5a6c…` |

The revision directory was regenerated so its declared pins match the code that produced it.
Its result is identical — `784ffa6621c3e708…`, capability **FAIL** — which confirms the D2
change touches only the pre-flight and not `run_checks`. The sealed original evidence was
verified byte-identical (7 files) before and after.

### The two documentation notes

* **`PROVENANCE.json` names no retrievable frozen artifact.** True, and now stated in the
  file itself: a digest identifies content without preserving it, this workspace holds no
  artifact of the pre-fix sources (they were edited in place and nothing was committed), so
  reproducing `02e1b764…` is **currently unverified by me**. Nothing was reconstructed or
  backdated, and no sealed evidence was altered. Codex verified that original replay in the
  earlier review; that observation stands on its own record.
* **The test docstring claimed there is no real sample.** Corrected: the L-block uses the two
  real bodies retained by run `20260908T021722Z`, pinned by SHA-256, and the docstring now
  says what they do and do not establish — two symbols on one day, decoder grammar only, not
  the live path, not the semantic checks, not a corpus. `BJ920000` has still never been
  contacted.

### Remaining limitations

* F8 inspects a **snapshot**. A PASS says nothing about what ran before or after it, and the
  review's point stands: no current process list proves historical absence of a writer.
* Recognition is bounded pattern matching over known launch shapes, not a shell parser. A
  launch obfuscated beyond those shapes would land in `ambiguous` if it names a stack target
  and in `other` if it does not — the second is a real residual gap, accepted deliberately in
  preference to a parser.
* `ambiguous` fails F8, so an unrelated process that merely names a stack target in an
  unrecognised shape will block a run until it exits. That is the intended direction of
  failure, but it is a usability cost, not a free win.
* On this machine the corrected gate currently reports `F8 PASS — local stack stopped (283
  processes inventoried, all classified)`, with zero recognised and zero unreadable relevant
  processes. That is one observation, not certification.
* Source-capability acceptance is still **FAIL**. No new live evidence exists, `BJ920000` has
  never been contacted, and identity, units, basis, coverage and adapter losses for
  `SH600011` remain unverified because its auxiliary request was never issued.


## 19. D2 literal-program boundary (2026-09-08, responding to `M2B_D2_LITERAL_BOUNDARY_CODEX_REVIEW.md`)

> Status: `ready_for_review` for Codex. **Offline only.** No live capture, production
> database operation, service operation, pilot collection, Git staging/commit/push or
> training. D1 and the previously closed fixes are untouched, every existing evidence and
> revision directory is unchanged, and no reviewer script was edited. M2b
> source-capability acceptance remains **FAIL**.

The review confirmed the earlier seven counterexamples closed and reported one remaining
boundary: the harmless-program exception proved nothing about the *whole* program. Three
executable programs were accepted as harmless, and one literal print was misread as a
launch. All four are fixed; only that boundary was touched.

### The defect in one line

`_PY_LITERAL_ONLY` was `^\s*(print|repr|str)\s*\(.*\)\s*;?\s*$` with a greedy `.*`, so
a program merely **starting** with a print satisfied it. `_PS_LISTING_ONLY` only inspected
the first verb. Both have been **replaced**, not reordered — the review was explicit that
swapping the order would not do, because the harmless rules were themselves unsound.

### Python: a bounded AST shape proof

`_python_program_is_inert` parses the program with `ast.parse` and requires **every**
statement to be an expression statement calling one of `print`, `repr`, `str`, `len`,
`format` **by bare name**, with literal arguments only (constants, or literal
tuples/lists/sets/dicts of constants; an f-string counts only if it interpolates nothing).
Bare literal expressions are allowed. Anything else — an import, an assignment, a loop, an
attribute call, a name argument, a comprehension, a syntax error, more than 400 AST nodes —
is not inert.

Parsing is not evaluation: `ast.parse` builds a tree and runs nothing. A regression proves
this by handing the checker a program whose execution would create a file, and asserting
the file does not appear.

### PowerShell: one complete simple read-only command

`_ps_program_is_inert` refuses the program outright if it contains any of
`; | & \` { } ( ) $ > <` or a newline — sequencing, pipelines, the call operator, script
blocks, subexpressions, variables or redirection — then requires the first token to be a
known read-only verb and every remaining token to be a literal. It is a refusal rule, not
a shell parser: anything it cannot prove simple is simply not proven.

### The order, and what it fixes

Inertness is now established **first**, over the whole program; the invocation patterns are
consulted only afterwards. That is what fixes P2: the invocation patterns are substring
searches and cannot tell a call from the same characters inside a string literal, so
`print('uvicorn.run(app.main:app)')` was read as a launch. Now the program is proven inert
and classified `other` regardless of what its literals happen to spell. A relevant program
that is neither proven inert nor a recognised launch is **`ambiguous`**, which fails F8.

| Reviewer counterexample | Before | After |
|---|---|---|
| `print('uvicorn.run(app.main:app)')` | FAIL (`stack`) | **PASS** (`other`, provably inert) |
| `print('starting'); from uvicorn import run; run('app.main:app')` | PASS (`other`) | **FAIL** (`ambiguous`) |
| `Get-Item .; python.exe scripts/control_plane_loop.py` | PASS (`other`) | **FAIL** (`ambiguous`) |
| `Get-Item $(python.exe scripts/control_plane_loop.py)` | PASS (`other`) | **FAIL** (`ambiguous`) |

### Commands and results

```bash
cd "claude methods/_m2_smoke" && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2_smoke.py
# exit 0, 165 cases, 0 unexpected   (158 -> 165; the 7 new cases are the N- block)

cd ../.. && ./backend/.venv/Scripts/python.exe -B -X utf8 \
    "claude methods/_m2_codex_review/review_m2b_d2_literal_boundary.py"
# exit 0, 8 checks, 8 passed, 0 failed   -- driver UNCHANGED   (was exit 1, 4/8)

./backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_pilot/test_m2a.py"  # 79 cases
cd "claude methods/_m1_closure"
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 67 checks
```

### One expected cross-version mismatch, reported and not "fixed"

```bash
./backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_codex_review/review_m2b_d1d2.py"
# exit 1: 55 checks, 54 passed
#   mismatch: "revision implementation matches declared pins"
```

That assertion compares the **current** sources against the producer pins declared by the
sibling revision `revision_20260908T021722Z_d1d2/`. Those sources changed for this fix, so
the check fails by construction. Per the review's clarification it is a **version-specific
pin mismatch, not a functional failure**, and it is reported rather than resolved: no
evidence directory, revision or reviewer script was edited to make it green. The other 54
checks pass.

### Changed hashes

| File under `_m2_smoke/` | before | after |
|---|---|---|
| `smoke_capture.py` | `37942c386bc5659d…` | `0ed93f05a8d8ab87da7dc57fa4c9c874806cc04d57b7ed93e53617cedc27daa2` |
| `test_m2_smoke.py` | `4103f03b9c5c5219…` | `d14a4f9822b8b249afe2366fc82eea80f1e9ed78de6e208c4b13c569e669df37` |
| `sina_klc_decoder.py` (D1) | | unchanged `d39e02c8cd736e10…` |
| `smoke_checks.py` | | unchanged `b2b8aaa9487bea54…` |
| `smoke_outcomes.py` | | unchanged `53a4301988bc5a6c…` |

### Provenance handling

The offline re-check went into a **new** directory,
`claude methods/_m2_smoke/revision_20260908T021722Z_d2_literal/`, which names its own
producer hashes and its parent evidence. Verified after writing it: the sealed original
evidence is unchanged (7 files) and the sibling revision `…_d1d2/` is unchanged (7 files).
Its result is again `784ffa6621c3e708…`, capability **FAIL** — the literal-boundary change
touches only the pre-flight, not `run_checks`.

**The earlier overwrite, stated plainly.** On 2026-09-08 I regenerated
`revision_20260908T021722Z_d1d2/` **in place** so its declared pins would match the code
that produced it. That overwrote its `PROVENANCE.json` and `checks.json` and rewrote the
rest of the directory from the sealed parent. The preservation boundary asked for that
revised evidence to stay unchanged, and I crossed it. **No pre-overwrite artifact exists**:
nothing was copied aside and nothing was committed, so there is no locator to give, and it
is deliberately not reconstructed or backdated. What is known about the overwritten version
is only what was recorded before it happened — the same deterministic result
`784ffa6621c3e708…` with capability FAIL, and producer pins naming `smoke_capture.py`
`fadcaf3cc4a3dcbe…` and `test_m2_smoke.py` `748b5131882e54db…` — a statement of what was
observed, not a recovered file. The sealed original evidence was never touched by any of
this. The full note lives in the new revision's `PROVENANCE.json`.

### Remaining limitations

* Inertness is a **proof of a narrow shape**, not a proof of harmlessness in general. A
  **relevant** program outside that shape — one naming a known stack target — is
  `ambiguous`, never silently allowed, at the cost of blocking a pre-flight until such a
  process exits. **Read that narrowly** (correction, per caveat 1 of
  `M2B_D2_ACCEPTANCE_CODEX.md`): a program that names **no** stack target returns `other`
  without any inertness proof being attempted, because relevance is tested first. An
  earlier version of this bullet said "unproven programs", which over-claimed. F8 is a
  point-in-time check of known visible launch forms — not a sandbox, a writer lock, or
  proof that the host is idle. Bash, encoded or obfuscated launches, and code carrying no
  recognisable target marker are **not** certified by it.
* The inline check covers Python and PowerShell inline programs. A `bash -c` program is
  still classified only by its argument vector, so a launcher hidden inside one would be
  missed. That gap is unchanged by this fix and is not in its scope.
* F8 remains a snapshot: it says nothing about what ran before or after it.
* Source-capability acceptance is still **FAIL**. No new live evidence exists, `BJ920000`
  has never been contacted, and identity, units, basis, coverage and adapter losses for
  `SH600011` are unverified because its auxiliary request was never issued. No new
  boundary-1b run is authorized.


## 20. D1/D2 technically validated; ONE new boundary-1b run requested (2026-09-08)

> Status: **preparation only, awaiting fresh user authorization.** Nothing here arms
> anything. Codex technically validated the bounded D1/D2 **offline** corrections
> (`M2B_D2_ACCEPTANCE_CODEX.md`). **M2b source capability remains FAIL** — the only real
> capture aborted and three of its five requests were never issued. This section closes
> the correction loop and asks for one run; it does not authorize one.

### What was validated, and what was not

| Technically validated (Codex, 2026-09-08) | Explicitly **not** validated |
|---|---|
| The bounded D1/D2 offline corrections: whole-program inertness, the process gate, blank/unidentifiable records, absolute and relative worker forms, and the literal boundary. The seven earlier and four literal counterexamples are closed, with no blocking defect found. | **M2b source capability — still FAIL.** `BJ920000` was never contacted; `SH600011`'s auxiliary request and every semantic check that depends on it are missing. This is also not user acceptance, not corpus readiness, not strategy evidence, and not training. |

Reviewer's runs: `test_m2_smoke.py` 165 cases exit 0; `review_m2b_d2_literal_boundary.py`
8/8 exit 0; `review_m2b_d2_final.py` 32/32 exit 0; `review_m2b_d1d2.py` 54/55 exit 1, the
one **expected** cross-version producer-pin mismatch, confined to `smoke_capture.py` and
`test_m2_smoke.py`. Those suites overlap deliberately and must not be summed.

### The reviewed implementation is now frozen locally

`claude methods/_m2_smoke/frozen_impl_20260908_d1d2_accepted/` holds a byte-for-byte copy
of the five validated source files, hash-verified before **and** after the copy, with a
`MANIFEST.json` recording each digest, size and original mtime. Untracked and never
staged, like everything under `claude methods/`. It contains **source files only** — no
credentials, private files, datasets, production databases, evidence or revisions. It
exists because a hash identifies content without preserving it, which is exactly how the
earlier revision's pre-overwrite provenance became unrecoverable.

```text
smoke_capture.py     0ed93f05a8d8ab87da7dc57fa4c9c874806cc04d57b7ed93e53617cedc27daa2
test_m2_smoke.py     d14a4f9822b8b249afe2366fc82eea80f1e9ed78de6e208c4b13c569e669df37
sina_klc_decoder.py  d39e02c8cd736e10c29ae6efc12ce540eeadf790552dcdc14debcf5f18461fee
smoke_checks.py      b2b8aaa9487bea54464386c90f9ccf3f2e11443d395a4a08a8c8e98a1421324c
smoke_outcomes.py    53a4301988bc5a6ced576718c8cab7a1a143ac2b798d9fc8d5f588e35d5b7a9e
```

---

## The request: ONE boundary-1b run, unchanged plan

**Exactly the same five requests as the reviewed plan.** No endpoint is substituted, no
symbol is added, and no limit is relaxed. What differs from the 2026-09-08 run is only
the corrected implementation, a fresh `run_id`, fresh output paths, and a timing
condition that is actually satisfied.

### Symbols and endpoints — Section 3, unchanged

| # | Job | Kind | URL |
|---|---|---|---|
| 1 | `sh600011` | KLC history | `https://finance.sina.com.cn/realstock/company/sh600011/hisdata_klc2/klc_kl.js` |
| 2 | `sh600011` | outstanding share | `https://stock.finance.sina.com.cn/stock/api/jsonp.php/var%20KKE_ShareAmount_sh600011=/StockService.getAmountBySymbol?_=20&symbol=sh600011` |
| 3 | `sh000300` | KLC history | `https://finance.sina.com.cn/realstock/company/sh000300/hisdata/klc_kl.js?d=2020_2_4` |
| 4 | `bj920000` | KLC history | `https://finance.sina.com.cn/realstock/company/bj920000/hisdata_klc2/klc_kl.js` |
| 5 | `bj920000` | outstanding share | `https://stock.finance.sina.com.cn/stock/api/jsonp.php/var%20KKE_ShareAmount_bj920000=/StockService.getAmountBySymbol?_=20&symbol=bj920000` |

Derived at run time from the installed akshare 1.18.64 constants, in this job order, and
printed verbatim by `--plan` before arming.

### Limits — unchanged, and not negotiable within this request

| Control | Value |
|---|---|
| Requests / attempt ceiling | 5 planned, **15** maximum including retries |
| Concurrency | 1 in flight, jobs sequential |
| Pacing | ≥ **1.5 s** between attempts, measured on actual post-pacing wire starts |
| Timeouts | connect 10 s, read 30 s, every attempt |
| Retries | ≤ 3 per request, backoff 2 s / 8 s, only on timeout / connection error / 500,502,503,504 — never on a TLS failure |
| Abort | **403/429 latched at the response headers**, the 15-attempt ceiling, 2 consecutive failed jobs, the 15-minute end-to-end deadline |
| Redirects | disabled; any 3xx is a failed attempt |
| TLS | `verify` pinned to certifi inside `backend/.venv`, no `*_CA_BUNDLE` override |
| Resource caps | 8 MiB per response, 32 MiB per run, bounded JS decode |

### Output paths — fresh, never reusing a retained directory

* During the run: `tmp/m2b_smoke_<new_run_id>/` (gitignored), plus its `.pending` sibling.
* At cleanup: `claude methods/_m2_smoke/evidence_<new_run_id>/`, retained **locally only**.
* `run_id` is a **fresh** UTC `YYYYMMDDTHHMMSSZ` stamp. `20260908T021722Z` is never reused.
* Every existing directory is preserved untouched: `evidence_20260908T021722Z/`,
  `receipts_20260908T021722Z/`, `revision_20260908T021722Z_d1d2/`,
  `revision_20260908T021722Z_d2_literal/`, `frozen_impl_20260908_d1d2_accepted/`. The
  original FAIL and its deterministic hash `02e1b764…` stand as the record of that run.

### Timing condition — the operator's, not the machine's

Before **09:15** or after **15:30 Asia/Shanghai**. I verify and record the wall clock
immediately before arming and abort if it is outside that window. F1–F8 read no clock and
`--plan` prints no time, so **a green pre-flight does not establish this**. The 2026-09-08
run went ahead at 10:17 local on your explicit instruction after I flagged the violation;
that authorization was consumed and is **not** standing permission.

### Fresh pre-flight requirements

All of F1–F8 must pass **in the same process, immediately before the first request** — the
armed mode re-runs them, and a failure refuses before any HTTP call or output directory is
created (regression-tested). Specifically: F1 branch/HEAD/status hash; F2 protected-input
fingerprints **and** the frozen read-only reference extract; F3 akshare 1.18.64 with the
three pinned URL constants; F4 the pinned `hk_js_decode` hash evaluating in `py_mini_racer`;
F5 no library-level retries; F6 fresh output and evidence paths, same volume; F7 TLS trust
pinned; F8 a **complete, decodable, non-empty** process inventory in which no known launch
form and no unresolved relevant process appears.

If F8 reports a running or ambiguous process, the run aborts and I report it. **No service
is started or stopped to make a pre-flight pass** — that is your action, never the smoke's.

### Read-only reference scope

`trading_local.sqlite3`, table `daily_bar_cache` only, opened `mode=ro` with
`PRAGMA query_only=1`, read **once** at F2 and frozen into
`reference/reference_extract.json`. `market_history.sqlite3` is never opened. No production
database is written. Every later check reads the frozen extract, and the offline replay
runs under `db_guard`, which makes a database open raise.

### What this run should answer, and why it is worth one request

The 2026-09-08 run left these open because it aborted after two requests:

1. **Does the corrected decoder work on live bytes end to end?** The retained bodies decode
   offline, but no capture has ever completed the decode-and-check path in flight.
2. **`SH600011` semantics — the whole reason for request 2.** Identity (I2), the volume
   unit (I3, U2), currency (U3), the `amount` vs `outstanding_share` separation (D5, Q1),
   adapter losses (C4/R1) and session coverage (C1). All are still unverified.
3. **`BJ920000` — completely unanswered.** It was never contacted. C2 decides between
   `pre_boundary_history_served`, `post_boundary_only` and an explicit
   `vendor_explicit_absence_at_path`, which is what the seven `bj_code_history` symbols'
   expected keys depend on.
4. **The index question** — whether `d=2020_2_4` bounds the served history (C3).

Expected outcomes are unchanged from Section 10 and are **not** padded around: any of the
three BJ classifications is useful, and a capability FAIL again produces findings, not an
escalation.

### What this request does not ask for

Not the 52-symbol pilot, not a second run, not the basis label, not production writes, not
service operations, not staging, commits, pushes or training. A capability PASS would prove
only that five specific responses were captured, decoded, replayed and checked as stated.

### To authorize

Say so explicitly, and state the retention choice: retain the raw bodies and frozen
reference locally under the new evidence directory (the reviewer's recommendation, and what
makes independent offline replay possible), or keep only their hashes. I will then verify
the Asia/Shanghai clock, run `--plan`, arm once, and stop at `ready_for_review`.

### Authorization received 2026-09-08 — GRANTED, held for the timing window

The user authorized **exactly one** boundary-1b run on the plan above, with the raw bodies
and the frozen reference extract **retained locally only** under the new evidence directory.

The authorization was given in conversation, in answer to an explicit question from me; the
user's original message text is not reproduced here, and this record is my account of it,
not the instruction itself. It covers **one run and nothing further**.

**Nothing was armed.** At the moment of authorization the Asia/Shanghai clock read
**2026-09-08 13:23 Tuesday**, inside continuous trading, so the operator timing condition
was **not** satisfied. The user chose to **hold** rather than run out-of-window or wait
unattended, and will re-trigger the run after **15:30 Asia/Shanghai** (or before 09:15 on a
later day). This is the opposite of what happened on 2026-09-08 at 10:17, and deliberately
so.

When re-triggered I will, in this order: verify and record the Asia/Shanghai wall clock and
abort if it is outside the window; run `--plan` and require F1–F8 green in-process; arm
once with a fresh UTC `run_id`; retain the evidence locally; run the offline replay; and
stop at `ready_for_review`. No limit, endpoint or symbol changes. If the pre-flight fails
— including an ambiguous process record — the run refuses before any HTTP call, and I
report rather than clearing the obstacle.


## 21. Execution readiness for the authorized run (2026-09-08, preparation only)

> **No live request has been issued.** The authorization logged in Section 20 is still
> unused: no new evidence directory, no `tmp/m2b_smoke_*` tree, no `.pending` sibling, no
> `run_id` minted. The window was **closed** when this was written — 2026-09-08 13:31:41
> Asia/Shanghai, inside continuous trading — so nothing was armed. A later re-trigger is
> required; see the stop condition at the end.

### Pre-arming verification, done and standing

| Item | Result |
|---|---|
| One-run authorization unused | confirmed — no new evidence dir, no run tree, no pending dir |
| Frozen source bundle `frozen_impl_20260908_d1d2_accepted/` | all five copies match their accepted pins, **and** the live sources still match the same pins |
| `evidence_20260908T021722Z/` | untouched — both raw bodies match `adc5a391…` / `ef2180be…` |
| `revision_…_d1d2/`, `revision_…_d2_literal/` | untouched — all four anchors match |
| `receipts_20260908T021722Z/` | untouched — all five receipts match their declared hashes |

The 165-case suite and the reviewer drivers were run earlier this session against these
exact source hashes and are not re-run here: nothing has changed since, and re-running
unchanged tests would add no evidence.

### Execution checklist — the operational sequence at arming

Each step must succeed before the next. Any failure stops the run and is reported; none
is worked around, and no process or service is ever stopped to clear one.

1. **Clock.** Record UTC and Asia/Shanghai wall clock. Require **before 09:15 or after
   15:30** local. Outside it → stop, do not arm.
2. **Authorization.** Re-confirm the Section 20 authorization is still unused (no new
   evidence dir, no run tree). A second run needs a new authorization.
3. **Integrity.** Re-verify the five live sources against the frozen bundle pins. A
   mismatch → stop: the reviewed implementation is not what would run.
4. **`--plan`.** Run it; require F1–F8 all PASS in that output, and check the five printed
   URLs are exactly the Section 20 table. It writes nothing and contacts nothing.
5. **Mint a fresh `run_id`** — UTC `YYYYMMDDTHHMMSSZ`. Never `20260908T021722Z`.
6. **Arm once**: `smoke_capture.py --i-authorize-live-calls <run_id>`. The armed mode
   re-runs F1–F8 **in-process**; a failure refuses before any HTTP call or directory
   creation. Expected shape: 5 requests, ≤15 attempts, ≥1.5 s spacing. On run duration,
   state a **floor, not an estimate**: five requests each paced ≥1.5 s from the previous
   start put ≥6.0 s between the first and fifth starts, plus the fifth request's own
   completion time, and more if any request retries — so a clean run consumes **at least
   ~6 s** of the 900 s budget. (An earlier draft said "~2 s", extrapolated from the
   2026-09-08 run, which issued only **two** requests and so contained a single 1.5 s gap.
   The limits themselves are unchanged.)
7. **Retain locally**: raw bodies + frozen reference under
   `claude methods/_m2_smoke/evidence_<run_id>/`. Never staged, never uploaded.
8. **Offline replay** from the retained evidence; require the deterministic block to
   reproduce and `db_guard` to hold (no production database opened).
9. **Report and stop** at `ready_for_review`. No second run, whatever the verdict.

### What the run must actually answer — derived from the sealed evidence, not assumed

The 2026-09-08 run aborted after two requests, so most required checks **never executed**.
Reading the sealed `checks.json` and the corrected offline re-check together:

| Status after the sealed run | Checks |
|---|---|
| **Never produced for any symbol** | `D5` (outstanding-share label), `U1` (positive volume/amount), `U2` (volume unit), `U3` (currency), `U4` (turnover, advisory), `C1` (`SH600011` coverage), `C4` (adapter post-processing losses) |
| **Produced for `sh000300` only** (via the corrected offline re-check, never in flight) | `D1`–`D4`, `I2`, `I3`, `R1`, `C3`, `B3`/`B4` advisory |
| **`sh600011`** | transport-level only — `EV2`, `S1`, `T1`, `T2`. No semantic check at all; `EV6` FAIL records that the capture called the body undecodable while the retained bytes decode |
| **`bj920000`** | nothing. `C2` exists only as a FINDING recording that it was **never contacted** |

So the run's job is: complete the `sh600011` stock semantics that all depend on the
never-issued request 2, obtain `BJ920000` for the first time, and confirm `sh000300`'s
checks in flight rather than only offline.

### Structure the boundary-1b acceptance report must have

So Codex can decide **source capability** — a decision this project has never been able to
make — the report is organised as:

1. **Run identity and honesty header** — `run_id`, both clocks with the window condition
   explicitly satisfied, authorization reference, the frozen-bundle pins that actually ran,
   and a statement of whether any live request was issued.
2. **Pre-flight record** — F1–F8 verbatim, including the process-inventory size and the
   count of recognised/ambiguous processes, so F8's PASS is evidenced rather than asserted.
3. **Wire record** — per request: URL requested and served, status, bytes, body SHA-256,
   attempt number and actual post-pacing start, retries with causes; plus the totals
   against the 15-attempt ceiling and the deadline.
4. **Outcome table** — every request's `(transport state, payload state)` → request/job
   result, and every skip with its `job_local` / `run_global` scope.
5. **The check table, split by evidential weight** — required PASS/FAIL/INCONCLUSIVE,
   advisory, and findings, each with measured value and threshold. The table from the
   previous section is the completeness target: a check that is still absent must be
   listed as absent, with the reason.
6. **The four questions answered or not** — the corrected decoder on live bytes;
   `SH600011` semantics (`D5`, `U1`–`U4`, `I2`, `I3`, `C1`, `C4`, `R1`); `BJ920000`'s `C2`
   classification and what it implies for the seven `bj_code_history` symbols' expected
   keys; and whether `d=2020_2_4` bounds the index history (`C3`).
7. **Verdicts** — per-job and the single capability verdict, with `PASS`,
   `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE`, `INCONCLUSIVE` or `FAIL` stated plainly, and the
   reminder that none of them authorizes the 52-symbol pilot.
8. **Offline replay** — the deterministic hash, whether it matches, and confirmation that
   no production database was opened.
9. **Preservation** — the new evidence paths, and confirmation that every prior evidence,
   receipt, revision and frozen directory is unchanged, with anchors.
10. **Limitations and what remains unproven**, in the same voice as the earlier reports:
    what five responses on one day can and cannot establish.

A capability FAIL again is an acceptable outcome and produces findings, not an escalation.

### Stop condition

**Preparation is complete and the window is closed.** I am stopping in a
**ready-to-run** state: authorization unused, bundle verified, checklist and report
structure fixed, nothing armed. There is no timer, background job or automatic
resumption — **a later re-trigger from the user is required**, at or after **15:30
Asia/Shanghai** on 2026-09-08 (or before 09:15 on a later day). At that point I begin at
step 1 of the checklist above.


## 22. Boundary-1b run 2 — `20260908T082833Z`, executed 2026-09-08 IN WINDOW

> Status: `ready_for_review` for Codex. **Capability verdict: FAIL**, but for entirely new
> reasons: all five requests were issued, all returned HTTP 200, and most of the semantic
> questions this project has carried since M1 are now **answered**. Three defects remain,
> all in our code, none fixed here — that is outside a one-run authorization. The prior
> evidence, receipts, revisions and frozen bundle are unchanged.

### The four gates, all satisfied before arming

| Gate | Result |
|---|---|
| Asia/Shanghai clock | **2026-09-08 16:27:57**, after 15:30 → **window OPEN**. Recorded before arming. |
| Authorization unused | confirmed — no evidence dir, no run tree, no `.pending`, no `run_id` |
| Source pins | all five live sources match the frozen accepted bundle |
| Fresh `--plan` | F1–F8 all PASS; the five printed URLs matched the Section 20 table exactly. **Process counts, distinguished:** my separate pre-arming `--plan` reported 280 inventoried processes, while the run's own re-run of F1–F8 recorded **279** — the number in the retained `plan.txt` and `capture_manifest.json`. They are two snapshots taken seconds apart, and **279 is the capture's inventory**; the 280 belongs only to the earlier standalone check. |

Then armed **once**. Exit code 1.

### What happened on the wire — all five requests issued

| # | job | request | HTTP | bytes | payload |
|---|---|---|---|---|---|
| 1 | `sh600011` | KLC history | 200 | 73,353 | **decoded** |
| 2 | `sh600011` | outstanding share | 200 | 1,108 | `undecodable` |
| 3 | `sh000300` | KLC history | 200 | 100,465 | **decoded** |
| 4 | `bj920000` | KLC history | 200 | 16,057 | **decoded** |
| 5 | `bj920000` | outstanding share | 200 | 1,705 | `undecodable` |

**5 attempts of a 15 ceiling, zero retries.** Actual post-pacing wire starts: 0.000,
1.515, 3.015, 4.515, 6.015 s — a first-to-fifth span of **6.015 s**, matching the ≥6 s
floor stated in Section 21 rather than the "~2 s" that section previously mis-stated. Run
consumed **7.5 s of the 900 s** deadline; finalization 0.594 s of 120 s, completed.
`run_status: completed`, `run_valid: true`, `invalidating_changes: []`.

### Answers obtained — most of them for the first time

**`BJ920000`, the question open since M1.** Contacted for the first time. C2 classifies it
**`pre_boundary_history_served`**: the vendor **does** serve pre-2024-08-13 history under the
`92xxxx` code — 1,393 rows, branch `O`, and `C2span` PASS (every reference session with
volume appears live).

**Correction (2026-09-08, per `M2B_RUN2_CODEX_REVIEW.md`).** An earlier version of this
paragraph said the result "settles the manifest's 'mapping unknown' note and the expected
keys of the seven `bj_code_history` symbols". **That over-generalized from one security.**
Exactly one BJ path was contacted. What is established is that **`BJ920000`'s** history
endpoint serves pre-2024-08-13 data under its `92xxxx` code. It is *not* established that
the same holds for the other six `bj_code_history` symbols, nor what mapping mechanism
produces it, nor their data coverage — one observation does not carry to six uncontacted
securities. Their uncertainty stands and the frozen manifest is unchanged.

**`SH600011` stock semantics**, all of which depended on request 2 being issued:

| Check | Result |
|---|---|
| `U2` volume unit | **`share`**, one-sided agreement with the price band — as predicted |
| `U3` currency | **amount ratio ≈ 1.00** — yuan, no 万元 scaling |
| `I3` volume ratio | **≈ 100** — confirms the cache stores 手 while the vendor serves 股 |
| `I2` identity | close ratio within tolerance across 10 sessions |
| `C1` coverage | first **2001-12-06** (its listing date) … last 2026-09-07, **span complete** |
| `U1`, `D2`, `D3`, `D4` | PASS |
| `C4` | 0 duplicate OHLCVA rows in the window |

`BJ920000` independently reproduces `U2 = share`, `U3 ≈ 1.00`, `I2`, `I3 ≈ 100`.
`SH000300` passes `D1`–`D4`, `I2`, `I3` and `C3` **in flight**, not merely offline.

### Three defects, all ours, none fixed here

1. **The outstanding-share payload is a list of OBJECTS, not pairs.** The vendor serves
   `[{"date":"2001-12-06","amount":14660.5}, …]` behind an XSS-guard comment
   (`/*<script>location.href='//sina.com';</script>*/`). `parse_outstanding_share` expects
   `[[date, value], …]` and refuses with *"entry 0 is not a [date, value] pair"*. Note what
   the vendor calls that field: **`amount`** — while it is outstanding shares in 万股. That
   is exactly the G3 mislabel this project has warned about since the M2b plan, now
   confirmed in live data. Consequence: `S2` FAIL on requests 2 and 5, `D5` INCONCLUSIVE,
   `U4` not computable, and per-symbol `R1` INCONCLUSIVE because the installed adapter
   fetches both URLs.
2. **`D1`'s JS-variable check false-FAILs on the stock prefix.** The variable is
   `KLC_K2_sh600011`; the check extracts digits and gets `2600011` — the `2` from `K2` —
   which is not a substring of `sh600011`, so it FAILs a body it had just decoded
   successfully (5,935 rows, branch `O`). The index variable `KLC_KL_sh000300` yields
   `000300` and passes, which is why no earlier run exposed this.
3. **The `R1` replay harness passes empty start/end dates.** It calls
   `stock_zh_a_daily(symbol, "", "")`, so the adapter reaches `temp_df["":""]` on a
   `DatetimeIndex` and raises `TypeError: cannot do slice indexing …`. That is our call
   site, not an adapter defect.

None is fixed in this turn: a one-run authorization covers the run and its report, not a
new correction round. All three are offline, bounded and reproducible from the retained
bodies.

### Verdicts

| scope | verdict |
|---|---|
| `sh600011` | FAIL |
| `sh000300` | INCONCLUSIVE |
| `bj920000` | FAIL |
| **capability** | **FAIL** |

Reasons recorded: run-level `R1` failed; `sh600011` and `bj920000` failed. The job-level
`INCONCLUSIVE_AUXILIARY` rollup behaved exactly as the R4 work intended — history served
and decoded, auxiliary request unusable, and that is **not** allowed to become a PASS.

### Offline replay

Deterministic block reproduced **byte for byte**:
`8ffb30b06a70aee4d301f4d7cea53c34e0ea8374dc0587d69b8848cb4f2ed5c2`,
`matches_stored: True`, under `db_guard`, no production database opened.

### Evidence, retained locally only

`claude methods/_m2_smoke/evidence_20260908T082833Z/` — untracked, never staged:
all **five** raw bodies (73,353 / 1,108 / 100,465 / 16,057 / 1,705 B), the 522,953-byte
frozen reference extract, `capture_manifest.json`, `checks.json`, `REPORT.md`, `plan.txt`.
The `tmp/` run tree and its `.pending` sibling were removed at cleanup.

Unchanged and verified afterwards: `evidence_20260908T021722Z/` (still capability FAIL,
raw bodies still `adc5a391…` / `ef2180be…`), both revision directories, the receipts, and
the frozen implementation bundle. Production metadata unchanged, nothing staged, HEAD
`73f266d`.

### What this run did and did not establish

**Established:** the corrected decoder works on live bytes end to end; the full pipeline —
transport, pacing, attempt accounting, outcome table, evidence store, finalization,
retention, replay — worked on a complete five-request run; `BJ920000` serves pre-boundary
history; and `SH600011`'s identity, unit, currency and coverage are measured rather than
assumed.

**Not established:** anything requiring the outstanding-share series (`D5`, `U4`), the
adapter replay (`R1`), and therefore source capability, which remains **FAIL**. Nothing
here advances the 52-symbol pilot, the basis label, the corpus, production promotion or
training, and **no second run is authorized**.


## 23. R2-A/B/C offline corrections (2026-09-08, responding to `M2B_RUN2_CODEX_REVIEW.md`)

> Status: `ready_for_review` for Codex. **Offline only** — no network call, production
> write, service change, pilot expansion, training, staging, commit or push. Both
> boundary-1b authorizations are consumed and **no further capture was made**. The two
> capture directories, both earlier revisions, both receipt sets, the frozen bundle and
> every reviewer script are unchanged. **M2b source capability remains FAIL.**

### R2-A — the real auxiliary format, with the zeros kept

The live bodies are an array of **objects** behind an XSS-guard comment:

```text
/*<script>location.href='//sina.com';</script>*/
var KKE_ShareAmount_sh600011=([{"date":"2001-12-06","amount":14660.5}, ...]);
```

`parse_outstanding_share` now parses that envelope **as data, never executing it**, binds
the variable name to the expected exchange and symbol, and validates dates, schema and
numerics. Confirmed against the retained bodies: **26** entries for `SH600011`, **42** for
`BJ920000`.

The field the vendor calls `amount` is **outstanding shares in 万股**, not traded amount —
`stock_zh_a_sina.py:207` multiplies it by 10,000 and `:208` divides volume by the result
for turnover. It is renamed `outstanding_share_wan` at the boundary, with the conversion
constant recorded, so the distinction cannot be lost downstream.

**Zero policy, stated and tested.** `BJ920000` really reports 0 on **2015-03-06** and
**2015-09-15**. Those rows are **kept in the series**, flagged `usable: False` with a
reason, and never used as a denominator. Nothing is fabricated, nothing is dropped, and
there is no division by zero. A **negative** count, by contrast, is impossible rather than
uninformative and is refused outright.

The series is a **step function**, so `outstanding_share_as_of` carries the last *usable*
observation **forward** and never backfills a later count into an earlier date — which is
what the installed adapter's `ffill` does.

> **Correction (2026-09-08, per `M2B_R2ABC_CODEX_REVIEW.md`; see Section 24).** The
> sentence above is the claim this round made, and the equivalence to `ffill` in it was
> **wrong**. Taking the last *usable* observation skips a **newer explicit zero** and
> silently restores an older positive count across it, while `ffill` keeps the zero
> (`[100, 0, NaN, 200].ffill()` is `[100, 0, 0, 200]`). Corrected in Section 24: the state
> is the **latest** observation at or before the date, and while an explicitly unusable
> one is in force there is **no** usable denominator until a later valid observation.
> The two retained research windows are unaffected — both `BJ920000` zeros precede its
> first positive observation — so the numbers reported in this section stand. That matters concretely: `SH600011`'s last
observation is 2019-10-15, *before* the window, so it has **zero in-window entries** yet
the value in force at the window start is well defined. `share_series_quality` reports
in-window versus pre-window entries and every unusable row separately, so an unusable
pre-window row is never confused with the validity of the series over the consumed window.
`U4` consequently moved from exact-date matching — which reported "0 common dates" for
`SH600011` — to as-of alignment, now covering **728 research rows** for both stocks with
**0** rows lacking an applicable observation.

**And it reports how stale that denominator is, because "0 exceed 100%" would otherwise
read as a fresh measurement.** For `SH600011` every in-window row resolves to the single
observation of **2019-10-15**: median age **1,975 days**, maximum **2,516 days** — 6.9
years. `BJ920000` is far better at median 173 / maximum 511 days. The turnover check
therefore passes on both, but for `SH600011` it is a check against a share count almost
seven years old, and `U4` now says so in its own text rather than leaving the reader to
infer it.

### R2-B — complete symbol identity, not digit collection

Observed grammar, from every retained body of both captures: `KLC_K2_<sym>` for the stock
history path, `KLC_KL_<sym>` for the index path, `KKE_ShareAmount_<sym>` for the auxiliary
endpoint. `expected_js_variable` and `check_js_variable` now match the **complete** name
against the expected exchange and symbol.

The old rule collected every digit and asked for a substring: `KLC_K2_sh600011` yielded
`2600011` — the `2` from the `K2` prefix — which failed a body it had just decoded.
`KLC_KL_sh000300` yielded `000300` and passed, which is why only the stock path showed it.
Regressions cover correct stock, index and auxiliary names, plus wrong symbol, wrong
exchange, index prefix on a stock, stock prefix on the index, wrong payload family, a
trailing suffix, and the old synthetic `klc_kl_` name.

### R2-C — real dates, and diagnostics that say what happened

The replay passed empty strings, so the adapter reached `temp_df["":""]` on a
`DatetimeIndex` and raised `TypeError`. It now passes the declared window explicitly as
`20220824` / `20260904`. On the retained bytes both stock adapters return **978 rows,
2022-08-24 … 2026-09-04**, and the index adapter — which takes no date arguments — returns
**5,987**, matching Codex's diagnostic exactly.

`R1` now asserts the returned rows and dates rather than the absence of an exception, and a
job that was **NOT EVALUATED** is worded and statused distinctly from one that failed. The
text claiming an auxiliary body "was not captured" is corrected: in run 2 it *was*
captured and failed to parse — a different fact with a different remedy. `C4` no longer
reports share-dependent statistics as measured zeros when the series is absent; it says
`NOT MEASURED` and marks `share_series_available: false`.

### Results

```bash
cd "claude methods/_m2_smoke" && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2_smoke.py
# exit 0, 175 cases, 0 unexpected   (165 -> 175; the 10 new cases are the O- block,
# five of them driven by the retained run-2 bodies, referenced by SHA-256)
```

### The corrected offline re-evaluation, in a NEW directory

`claude methods/_m2_smoke/revision_20260908T082833Z_r2abc/` — parent link, producer hashes
and input hashes all recorded in its `PROVENANCE.json`. The original capture and its FAIL
are untouched.

| | Original live verdict | Corrected offline re-evaluation |
|---|---|---|
| capability | **FAIL** | **FAIL** |
| `sh600011` | FAIL | FAIL |
| `sh000300` | INCONCLUSIVE | **PASS** |
| `bj920000` | FAIL | FAIL |

What the corrections fixed is visible per check: `D1` PASS for all three with the exact
expected variable names; `D5` PASS for both stocks (26 and 42 entries, never labelled
amount); `R1` PASS for all three with real row counts and dates; `C4` reporting measured
statistics again.

**The capability verdict is still FAIL, and deliberately so.** `EV6` FAILs for `sh600011`
and `bj920000`: the capture-time parser recorded those bodies as `undecodable` while the
corrected parser reads them as `decoded`. That is a genuine **parser version difference**,
and it is exactly the condition `EV6` exists to surface. **It is not waived.** The
consequence is stated plainly in the provenance file: while `EV6` disagrees, this retained
capture cannot yield a corrected capability PASS from these inputs. Establishing capability
under the corrected implementation requires a **new authorized capture**, which this work
neither has nor requests. No result was forced green and no stored input was massaged.

### Reporting corrections

* **The seven-symbol BJ generalization is withdrawn.** One BJ path was contacted. What is
  established is that `BJ920000` serves pre-boundary history under its `92xxxx` code — not
  the mapping mechanism, and not the coverage of the other six `bj_code_history` symbols.
  Corrected in Section 22 and in the Section 2 selection note; the frozen manifest is
  unchanged.
* **The process counts are distinguished.** My separate pre-arming `--plan` reported 280;
  the run's own in-process F1–F8 recorded **279**, the number in the retained `plan.txt`
  and manifest. Two snapshots seconds apart — 279 is the capture's inventory.
* **The handoff no longer says the second run is unused.** Both authorizations are
  consumed; the pre-run terms are archived as such rather than left reading as current.

### Remaining limitations

No new live evidence exists and none was sought. The `EV6` provenance gate blocks a
corrected capability verdict from the retained inputs. `SH600011`'s and `BJ920000`'s
semantics are measured on **one day's** capture of **one** security each. The BJ result
does not generalize. Source capability remains **FAIL**.

## 24. R2-ABC closure — C1/C2 (2026-09-08, responding to `M2B_R2ABC_CODEX_REVIEW.md`)

> Status: **technically validated by Codex on 2026-09-08 within this bounded offline
> scope** (`M2B_R2ABC_CLOSURE_CODEX_REVIEW.md`; recorded in Section 25). It was
> `ready_for_review` when written. **Offline only** — no live request, production database
> access, service change, token access, dataset change, staging, commit, push or training.
> Both boundary-1b authorizations remain consumed and **no capture was made or requested**.
> Every existing capture, revision, receipt set, frozen bundle and reviewer script is
> unchanged. **M2b source capability remains FAIL.**

### C1 — an explicit invalid observation interrupts denominator validity

Codex's counterexample: `2020-01-01 = 100`, `2020-01-03 = 0`, `2020-01-05 = 200`. The
previous `outstanding_share_as_of` returned the *last usable* observation, so on 01-03 and
01-04 it handed back **100** — skipping the newer zero and silently restoring a superseded
denominator — and a window opening on 01-04 reported `covers_window_start: true`.

The state at a date is now the **latest** observation at or before it, usable or not:

* while an explicitly unusable observation is in force there is **no usable denominator**,
  until a **later valid** observation supersedes it;
* the zero is **preserved** in the series with its reason, and reported — never dropped;
* nothing is ever backfilled from a later date;
* a series that **ends** unusable has no denominator from that date onward.

This matches the installed pandas: `[100, 0, NaN, 200].ffill()` is `[100, 0, 0, 200]`,
asserted against the installed version rather than assumed. The earlier docstring's
equivalence claim was wrong and is corrected in Section 23.

`share_series_quality` now also reports `state_at_window_start` / `state_at_window_end`
(the raw observation that decided coverage, including a withheld zero) and
`invalid_denominator_intervals` — each unusable observation with the date of the later
valid one that restores validity, or `null` when none does. `U4` splits its
missing-denominator count into **rows before the series begins** versus **rows under an
explicit invalid observation**, and lists the intervals.

**On the retained bytes this changes no number.** Both `BJ920000` zeros (2015-03-06 and
2015-09-15) precede its first positive observation of 2015-10-27, so both intervals close
seven years before the research window: `U4` still reports 728 aligned rows and 0 without
an applicable observation for both stocks. This was a **general validity defect**, not a
demonstrated corruption of the two retained windows — and the intervals are now visible in
the evidence rather than implied.

### C2 — R1 validates the actual returned dates

`{rows: 1, first_date: "2023-01-03", last_date: null, dates: []}` used to PASS: metadata
claiming a first date was taken as proof that dates came back. `_replay_verdict` now
requires a **non-empty actual date sequence** that agrees with the row count and the
first/last metadata, is free of repeats, and is ascending — and, for the **stock**
interface, which is handed explicit dates, lies **inside the declared window**. The index
interface takes no date arguments and returns its full served series, so the stock window
is **not** imposed on it; it is held to the same sequence consistency. The no-fabricated-
date rule is unchanged. This is defensive hardening: the real adapter's retained replay
was and remains internally consistent, and no security is required to return any
particular row count.

### Results

```bash
cd "claude methods/_m2_smoke"        && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2_smoke.py
# exit 0, 182 cases, 0 unexpected    (175 -> 182: the 7 new P- cases, incl. an end-to-end U4)
cd "claude methods/_m2_smoke"        && ../../backend/.venv/Scripts/python.exe -B -X utf8 closure_r2abc_v2.py
# exit 0, 49 checks, 49 passed       (the separately versioned closure driver for the new revision)
cd "claude methods/_m2_codex_review" && ../../backend/.venv/Scripts/python.exe -B -X utf8 review_m2b_r2abc.py
# exit 1, 39 checks, 36 passed, 3 failed - ALL cross-version against the OLD revision
```

The three failures in Codex's unchanged reviewer are reported, not erased: it pins
`revision_20260908T082833Z_r2abc`'s producer hashes and deterministic hash, and the C1/C2
corrections changed three of the five sources. Its four previously failing assertions —
the three denominator ones and the R1 metadata one — now **pass**. Its own independent
replay reproduces the new hash `099640a2…` exactly.

### The corrected offline re-evaluation, in a NEW directory

`claude methods/_m2_smoke/revision_20260908T082833Z_r2abc_v2/` — its `PROVENANCE.json`
carries the parent capture link, the superseded revision link, current producer hashes,
the seven input hashes, and a `cross_version_producer_pins` block naming the three sources
that changed and the superseded revision's own accepted hash. Deterministic hash
**`099640a21e5927a057f3d2d1468b5765312bf1b68ff0d056051a18317fc81292`**.

| | Original live verdict | `…_r2abc` | `…_r2abc_v2` |
|---|---|---|---|
| capability | **FAIL** | **FAIL** | **FAIL** |
| `sh600011` | FAIL | FAIL | FAIL |
| `sh000300` | INCONCLUSIVE | PASS | PASS |
| `bj920000` | FAIL | FAIL | FAIL |

**`EV6` stays visible and is still the only failing gate** — `sh600011` and `bj920000`,
capture-time `undecodable` versus current `decoded`. It is **not waived**: while it
disagrees, these retained inputs cannot yield a corrected capability PASS. That would need
a new authorized capture, which this work neither has nor requests.

Current producer pins (these are the **current** implementation, not the historical
accepted D1/D2 freeze at `_m2_smoke/frozen_impl_20260908_d1d2_accepted/`):

| file | sha256 |
|---|---|
| `smoke_capture.py` | `059d0c43…` (unchanged this round) |
| `smoke_outcomes.py` | `5bbb6ef0…` (unchanged this round) |
| `smoke_checks.py` | `4b062a55…` |
| `sina_klc_decoder.py` | `c6d736b1…` |
| `test_m2_smoke.py` | `23b917c5…` |
| `closure_r2abc_v2.py` | `63f73196…` (new, this round) |

### Remaining limitations

No new live evidence exists and none was sought. The `EV6` provenance gate still blocks a
corrected capability verdict from the retained inputs. C1 is a validity fix proven on
synthetic series and on the reviewer's counterexample; it changes **no** measured value in
either retained window. C2 is defensive hardening, not a new completeness requirement.
`SH600011`'s and `BJ920000`'s semantics remain measured on **one day's** capture of **one**
security each, and `SH600011`'s turnover check still rests on a share count **2,516 days**
old at the window end. The BJ result does not generalize. Source capability remains
**FAIL**.

## 25. R2-ABC closure technically VALIDATED by Codex (2026-09-08, bounded offline scope)

Source: `claude methods/M2B_R2ABC_CLOSURE_CODEX_REVIEW.md`. Documentation-only entry — no
implementation change, no repeat test cycle, no capture.

### What was validated, and against what

Codex technically validates the bounded offline R2-ABC closure **bound to these five
producer hashes**, which are the current implementation and are unchanged by this entry:

| file | sha256 |
|---|---|
| `smoke_capture.py` | `059d0c43547db0bf520afc9c034dbc5c1638b3beb12c77e35e62ace03f85ad35` |
| `smoke_checks.py` | `4b062a55fae6f9bd348a7ffdf20073debababffafc71568e2aaaf8181c832bbe` |
| `smoke_outcomes.py` | `5bbb6ef052a309c84aaa69d43c721470670ca4428ab6747ad0993e5ad4607ec0` |
| `sina_klc_decoder.py` | `c6d736b170c29009ef273ed7705330f2a251545bca720d55c998d0a715f83fc8` |
| `test_m2_smoke.py` | `23b917c51d4bb3f880571df5baeabedd394a043654694643623d238c756742db` |

Closed in this scope: **C1** denominator validity (an explicit zero interrupts the
denominator; positive-zero-positive, consecutive zeros, a trailing zero, a leading zero,
an empty series, genuine forward carry over missing observations, and day-by-day window
coverage all behave as required), **C2** actual-date-sequence consistency (no real dates,
row-count disagreement, first/last disagreement, repeats, reverse order, out-of-window
stock dates and fabricated dates are all refused; a short legitimate sequence passes and
the index full-series interface is constrained separately), and **C3** the operative
two-captures / two-consumed-authorizations handoff.

### What this is NOT

Not M2b **source-capability acceptance**. Not **user** acceptance. Not corpus
certification, feature/label/strategy readiness or training readiness. Not authorization
for another capture, a 52-symbol pilot, production ingestion or promotion. **M2b source
capability remains FAIL.** The earlier `M2B_R2ABC_CODEX_REVIEW.md` round was **partial
technical acceptance**, not final acceptance — including where the v2 provenance field is
named `accepted_in_revision_20260908T082833Z_r2abc`: that name records the **producer
pins of that partially accepted round**, nothing more. The retained revision is **not**
edited to reword it.

### Runs of record

| driver | result |
|---|---|
| `test_m2_smoke.py` (mine) | **182 cases, 0 unexpected, exit 0** — run by Codex under an audit hook refusing file-backed SQLite opens |
| `review_m2b_r2abc.py` (Codex's, **unchanged**) | **39 checks, 36 passed, 3 failed, exit 1** |
| `review_m2b_r2abc_closure_codex.py` (Codex's, new) | **76 checks, all passed, exit 0** — 48 contract/preservation checks plus 28 revision, source and retained-input checks |
| `closure_r2abc_v2.py` (mine, `63f73196…`) | **49 checks, 49 passed, exit 0** |

```powershell
& 'backend/.venv/Scripts/python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_r2abc_closure_codex.py' 'claude methods/_m2_smoke/revision_20260908T082833Z_r2abc_v2'
```

Codex's raw outputs are at `_m2_codex_review/r2abc_closure_codex_results.json`.

**The 36/39, stated plainly.** The three failures are the **producer-pin comparison** and
**two stored-result comparisons** — the old revision's `matches_stored` and its
deterministic hash `c23f44bc…`. They fail **across versions**, exactly as expected, because
that reviewer is pinned to the superseded `…_r2abc` revision and three of the five sources
changed. The **four functional expectations that failed last round — the three denominator
ones and the R1 metadata one — now pass.** Neither the old reviewer nor the old revision
is edited to turn them green, and neither ever will be.

**A clerical correction, mine.** I reported this round's closure driver as 48/48. The
driver's own output is **49/49** — same driver, same hash `63f73196…`, no PASS/FAIL,
verdict or authorization state affected. Corrected here and in the ledger; the earlier
figure is a miscount in my summary, not a changed result.

### Two scope clarifications Codex recorded

* **728 versus 978.** `U4`'s denominator alignment covers the **728 research sessions**;
  the remaining 250 of the adapter's 978 rows are the **warm-up** span. The 978-row replay
  count must not be read as U4's research-row count. Codex corrected its own draft
  fixture's expectation on this point; no implementation changed.
* **What v2 actually moved.** Comparing the two deterministic blocks, only `checks`
  differs at the top level. Both hold **71 checks**; only two `U4` and three `R1` entries
  changed in counts, thresholds or wording. **No check status, no per-job verdict, no
  capability verdict and no pilot-authorization state changed.**

### Standing limitations, unchanged

`EV6` still FAILs for `sh600011` and `bj920000` — capture-time `undecodable` versus current
offline `decoded` — and is **not waived**; both original capture FAIL records stand
unrewritten. Both retained research windows have 728 usable denominators and **zero**
missing rows, so this correction addressed a **general** invalid-interval defect and claims
no contamination of those two windows. `SH600011`'s maximum carried-forward denominator age
is still **2,516 days**, and no new share observation exists. `BJ920000`'s result does not
extrapolate to other BJ symbols. **No third capture is requested or executed to clear
`EV6`.**

## 26. P1 basis module — implemented offline; BR-R1…BR-R4 closed for the reviewed hashes (2026-09-09)

> **Documentation record only.** This section reports a bounded *implementation*
> validation. **P1 is not closed**, `U-6` remains deferred, every eligibility result is
> `false`, **M2b source capability remains FAIL**, and **both capture authorizations remain
> consumed**. It is **not** policy adoption beyond the **Claude-reported** adoption of
> U-1…U-5 and U-7 recorded below, **not** corpus certification, **not** training readiness
> and **not** an operational authorization. No gate was wired and no production schema or
> label changed.

### Attribution of the adoption and authorization (DOC-R1) — Claude-reported

The adoption of the bounded **U-1, U-2, U-3, U-4, U-5 and U-7** recommendations of
`M2B_P1_BASIS_CONTRACT_PROPOSAL.md` (revision 6), the deferral of **U-6**, and the
authorization of the offline module were given to me as a **user instruction in the Claude
session on 2026-09-09**, immediately before the implementation round. Its exact bounded
scope was: adopt U-1, U-2, U-3, U-4, U-5 and U-7; leave **U-6 deferred**; authorize the
offline module implementation; **create only** `claude methods/_m2_smoke/basis_record.py`,
`claude methods/_m2_smoke/test_basis_record.py` and **one** fresh `basis_eval_*` output
directory; follow the reviewed revision-6 specification and the Codex clarification;
implement both digest-anchor checks, input verification and fail-closed handling; **expose
no `eligible=true` path**; run focused offline synthetic tests and retained-artifact
validation; preserve all existing files and evidence; **no** adapter replay, network,
SQLite, gate wiring, production change, capture, service operation, token access, pilot,
training, source expansion, Git staging/commit/push or live trading; **both capture
authorizations remain consumed**; stop at `ready_for_review` with hashes, commands, results
and preservation evidence; and **do not claim P1 closure or source-capability acceptance**.

**Its verifiability, stated plainly.** **No file artifact in this repository records that
instruction.** It is therefore **Claude-reported and not independently verified by Codex**,
and it is labelled as such everywhere it appears in these two documents. It is **not**
inferred from Codex's technical validation — the R2 review is explicit that technical
validation is not policy adoption — and **neither** a Codex review, the module's own
docstring, nor any suggested instruction text is the authorization. **No authorization
receipt has been created, backdated or requested**, and nothing here asks for another
capture. If a durable record of the instruction is wanted, only the user can supply it;
this section does not substitute for one.

### What was built

Exactly three artifacts were created:
`_m2_smoke/basis_record.py`, `_m2_smoke/test_basis_record.py`, and one fresh output
directory. The module accepts **one** selected revision directory, binds its `checks.json`
and `PROVENANCE.json`, verifies the required input inventory and **both** digest anchors,
rejects incomplete legacy schemas, derives one record per job, and evaluates
basis-dependent eligibility with **no `eligible=true` path**.

### The first review, preserved as history

`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW.md` withheld bounded acceptance with four
findings: **BR-R1** input verification could be bypassed by omitting `input_hashes`, and the
consumed-file ledger omitted the reference extract; **BR-R2** the output guard accepted a
reviewer directory and compared protected prefixes case-sensitively on Windows; **BR-R3**
request/attempt/replay associations did not gate a positive transform claim; **BR-R4** view
evaluation ignored mixed record-producer identities. **Those findings and the first output
directory `_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2/` are preserved
unchanged** — the first output is the historical artifact of the pre-correction module and
is not an output of the validated version.

### The corrections, and their independent validation

`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md` (2026-09-09) records
**BR-R1, BR-R2, BR-R3 and BR-R4 as technically closed for the reviewed version**, bound to
these hashes:

| Artifact | SHA-256 |
|---|---|
| `_m2_smoke/basis_record.py` | `0fda4f7effba73ac04a8f10ce35b686a7a646a741650159f55cd9288b6bd2cc7` |
| `_m2_smoke/test_basis_record.py` | `51add34ec943188fa9bdc7a039cd675d5deee26b711409fd99ad04546f6bad67` |
| new output `basis_records.json` | `c5b1bf3c2f660dcca84c1f3d44fba8252b1580d98fbce300d5412340d32448de` |
| new output `PROVENANCE.json` | `a1b662a2cf67bb331202cec7e086887e59115994abd9828d4bcde7d4aafee514` |

New output directory:
**`claude methods/_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2__br_r1_r4/`**;
deterministic records digest
**`f9bef731a8f3e7541f4e266a9b8ad11096727e851a551ce75d657af45b83da9d`**.

| Run of record | Result |
|---|---|
| `test_basis_record.py` (mine), executed by the independent driver | **41/41, exit 0** |
| Codex independent expectations (`review_basis_record_codex_r2.py`) | **21/21**, no unexpected exceptions |

The selected source revision is unchanged: `revision_20260908T082833Z_r2abc_v2`,
deterministic digest `099640a2…`, **capability FAIL**, with its historical `EV6`
disagreements untouched. Codex reports 104 protected files unchanged during execution, and
production database sizes and nanosecond mtimes unchanged with no SQLite connection opened.

### What the records say, and what they do not

Both stocks derive `adapter_transform: none`; `sh000300` stays `unknown` because D-1b's
index-adapter pin is recorded nowhere in the retained artifacts and cannot be supplied
retrospectively. All three carry `vendor_basis: unverified`, and **every eligibility result
is `false`** — by construction, since `U-6` defines no sufficiency rule. A record asserting
`unadjusted` is refused even with genuine evidence references and current pins. The stated
detection limits stand unchanged, including that revision binding **does not** detect every
same-digest file substitution, and that a self-consistent forgery is not detectable.

### Standing position

**P1 remains OPEN.** `U-6` remains **deferred**. **M2b source capability remains FAIL** on
the two `EV6` parser-version disagreements, which are not waived. **Both capture
authorizations remain consumed** and no capture is requested. Nothing in this section
authorizes the 52-symbol pilot, production ingestion, promotion or training.
