# G-1 search coverage, failures and method — revision 3

Three rounds have run, all on 2026-09-09, all under the same narrow authorization for a
read-only lookup of public official corporate-action disclosures for the two stocks:

| Round | Task | Outcome |
|---|---|---|
| 1 | `G1-OFFICIAL-CA-20260909` | first delivery (v1) |
| 2 | `G1-R1-20260909` | corrections G1-R1/R2/R3 (revision 2) |
| 3 | `G1-COMPLETE-20260909-R2` | this pass — **G-a, G-b, G-c, G-e closed; E-2 upgraded to Tier A** |

Network use in all three rounds was confined to the approved corporate-action lookup and the
issuer-identity verification it requires. **No local file and no raw vendor data was uploaded to
any search service.** No credentials, accounts, tokens or sign-in were used; nothing was
installed; no protection or bot-check was bypassed.

## Corrected round timing (repairs the revision-2 05:20 claim)

Revision 2 asserted *"Round 2 … ran 2026-09-09 05:20Z–05:35Z"*. **That was not a measured start
time and is withdrawn.** Times are now reported from actual activity, and **claimed execution
windows are kept distinct from measured file times**:

| Round | Request received | Earliest measured retrieval | Latest measured write |
|---|---|---|---|
| 1 | **not measured here** | `04:57:07Z` (recorded document retrieval) | `05:07:30Z` (the five v1 PDFs written) |
| 2 | **≈05:24–05:25Z**, per the reviewer's own record of when it was sent — not measured by this session | `05:25:40Z` (BSE mapping page) | `05:37:32Z` (`PROVENANCE.json`) |
| 3 | **not measured here** | `05:58:03.678Z` (first document fetch, from the millisecond stamp in the fetch tool's saved-output filename) | see `PROVENANCE.json` `generated_at_utc` |

Round 3's measured retrievals span **`05:58:03Z` … `06:17:26Z`**; document writes follow.
Revision 2's claimed round-2 end of `05:35Z` was also wrong: the last measured round-2 write was
`05:37:32Z`.

Two provenance conventions, stated so they are not confused. A **retrieval timestamp** is either
the millisecond stamp in the fetch tool's saved-output filename or the modification time of the
file `curl` wrote. A **write time** is a file modification time inside this directory. Neither is
a claim about when a round began; where a start time is not measured, it is left blank rather
than inferred.

## Method

Rounds 1–2 were driven by **issuer and reporting period** through a web search engine with
official-host domain filters. That method found some documents and missed others, and its misses
were **not** evidence of absence.

Round 3 replaced it with the **official disclosure platform's own announcement-listing endpoint**
(`POST http://www.cninfo.com.cn/new/hisAnnouncement/query`), which enumerates an issuer's filings
directly instead of relying on a search index. A public disclosure query using POST is still a
read-only lookup. This is what closed G-a, G-b, G-c and G-e: **every** announcement for both
issuers over a window that over-covers the task interval was listed and paginated to completion —
190/190 for the BSE issuer and 227/227 for the SSE issuer. The raw responses, the exact request
parameters, and two endpoint quirks that shaped the method are retained in
`disclosure_index/README.md`.

**Sina remains deliberately excluded** as a corporate-action source: it is the vendor whose price
basis is the open question, so using it would be circular. `同花顺 (10jqka)` and `中财网
(cfi.net.cn)` were treated as pointers only in round 1, were never used as evidence, and failed
to render in any case.

## Round 3 fetches

| URL | Result |
|---|---|
| `POST .../new/information/topSearch/query` `keyWord=920000` | **retrieved** — `orgId gfbj0832000`; retained |
| `POST .../new/information/topSearch/query` `keyWord=600011` | **retrieved** — `orgId gssh0600011`; retained |
| `POST .../new/hisAnnouncement/query` `stock=920000,gfbj0832000` `seDate=2024-08-01~2026-07-31` | **retrieved** — 190 records over 7 pages; retained |
| `POST .../new/hisAnnouncement/query` `stock=600011,gssh0600011` `seDate=2024-08-01~2026-07-31` | **retrieved** — 227 records over 8 pages; retained |
| the same endpoint, both issuers, `seDate=2026-08-01~2026-09-09` | **retrieved** — 10 and 11 records; retained |
| `https://static.cninfo.com.cn/finalpage/2025-03-31/1222976533.PDF` | **retrieved** — BJ `2025-022` FY2024 年度报告摘要, Tier A, retained. Fetched **twice by two different tools**; both copies byte-identical (`e53a93f4…`) |
| `https://static.cninfo.com.cn/finalpage/2025-04-14/1223097471.PDF` | **retrieved** — turns out to be BJ `2024年年度报告业绩说明会预告公告`, an earnings-call notice, **not** a distribution document; read, **not retained** |
| `https://static.cninfo.com.cn/finalpage/2024-09-20/1221258690.PDF` | **retrieved** — BJ `2024-068` H1-2024 implementation, Tier A, retained; **closes G-a** |
| `https://static.cninfo.com.cn/finalpage/2025-05-07/1223491665.PDF` | **retrieved** — BJ `2025-047` FY2024 implementation, Tier A, retained; **closes G-b** |
| `https://static.cninfo.com.cn/finalpage/2026-05-15/1225310540.PDF` | **retrieved** — BJ `2026-037` FY2025 implementation, Tier A, retained; **closes G-c** |
| `https://static.cninfo.com.cn/finalpage/2026-08-14/1225473518.PDF` | **retrieved** — BJ `2026-047` 2026 半年度报告摘要, Tier A, retained (G-e) |
| `https://static.cninfo.com.cn/finalpage/2026-06-25/1225385939.PDF` | **retrieved** — SH `2026-036` FY2025 implementation on an **official** host, Tier A, retained; **upgrades E-2 from Tier B** |
| `https://static.cninfo.com.cn/finalpage/2025-07-02/1224057212.PDF` | **retrieved** — re-fetch of E-1's source purely as an integrity check; reproduces the retained file's hash `439ceb65…` exactly; the duplicate was discarded |
| `https://static.cninfo.com.cn/finalpage/2025-03-26/1222896784.PDF` | **retrieved** — SH FY2024 年度报告 (366 pp.), Tier A, retained (G-e) |
| `https://static.cninfo.com.cn/finalpage/2026-03-25/1225029354.PDF` | **retrieved** — SH FY2025 年度报告 (372 pp.), Tier A, retained (G-e) |
| `https://static.cninfo.com.cn/finalpage/2026-08-19/1225480837.PDF` | **retrieved** — SH 2026 半年度报告 (268 pp.), Tier A, retained (G-e) |
| `https://static.cninfo.com.cn/finalpage/2026-03-25/1225029352.PDF` | **retrieved** — SH FY2025 年度报告摘要; read, and found to carry **no** 股份变动 table, so the full report was used instead; **not retained** |
| `https://static.cninfo.com.cn/finalpage/2025-03-31/1222976528.PDF` | **downloaded, not read, not retained** — BJ `公司2024年年度权益分派预案公告`; superseded by the retained `2025-047` implementation notice. No claim is made anywhere about its contents |
| `https://static.cninfo.com.cn/finalpage/2025-05-14/1223537409.PDF` | **retrieved and rejected** — a search hit titled `2024年年度分红派息实施公告` that belongs to **苏州华源控股股份有限公司, code 002787 (Shenzhen)**, a different issuer entirely. Read, discarded, **not retained**; recorded here so the false lead is on the record |
| `https://www.bse.cn/service/code_mapping.html` | **retrieved and now retained** — the first round-3 attempt, without a cookie jar, hit a redirect loop; with one it returns 200. Row 214 is server-rendered in the retained bytes |
| `https://www.bse.cn/important_news/200024109.html` | **retrieved and retained** — 北证公告〔2024〕231号 (2024-12-13), the official code-switch preparation notice |
| `https://www.phoenixfilters.net/` | **retrieved and retained** — the BSE issuer's own site, the lead named in the FY2024 summary. It is a **product site**: it states `股票代码 920000` but has **no** investor-relations or disclosure section, so it carries no announcements |

## Round 3 queries

| # | Query | Domain filter | Outcome |
|---|---|---|---|
| 21 | `安徽凤凰滤清器 2024年年度报告 公告编号 2025-021 832000` | `cninfo`, `bse` | did not surface `2025-021`; surfaced unrelated 2025 filings. `2025-021` is the FY2024 **full** report; the retained summary is `2025-022` |
| 22 | `安徽凤凰 832000 2024年年度权益分派实施公告 权益登记日 除权除息日 2025年5月` | `cninfo`, `bse` | surfaced the **wrong issuer's** document (002787, above). The search-index route failed again here; the platform endpoint then found the real document immediately |
| 23 | `北京证券交易所 启用新证券代码 920 号段 通知 2025年10月 存量公司 变更` | `bse`, `cninfo`, `csrc` | **found** 北证公告〔2024〕231号 and two 2023–2024 notices; none names a switch date for this issuer |
| 24 | `北交所 存量上市公司 证券代码切换 第一批 名单 2025年10月13日 生效日` | `bse` | **nothing** — no batch-list notice is indexed. Not retried in another wording; recorded as failed |

## Round 3 failures and blocked paths, precisely

* **The search-index route failed twice more** (queries 21–22) on documents the official platform
  endpoint returned immediately. That is a property of the search index, not of the issuers.
* **`https://www.bse.cn/service/code_mapping.html` without a cookie jar** returns an endless 302
  loop — `curl: (47) Maximum (50) redirects followed`. With `-c/-b` it returns 200.
* **No batch-list notice for the `920000` code switch was found** on `bse.cn` (query 24). The
  official preparation notice states the switch runs `分批次` and that `具体事宜本所将另行通知`, and
  names **no** date. **G-g's effective date therefore remains unknown.**
* **No PDF library is available** in the environment and installation is not authorized, so the
  three long SSE periodic reports could not be indexed programmatically. They were navigated via
  their own printed 目录 pages instead; that is why cited pages are printed page numbers, which in
  these three files coincide with PDF page numbers.
* **`www.hpi.com.cn` was not retried in round 3.** Round 2 had already recorded four HTTP 503
  responses, and the document it was wanted for is now retained from an official platform host,
  so retrying it would repeat a known-failed request for a need that no longer exists.
* **HKEX was not used.** Round 3's task named a suitable HKEX A-share filing as a fallback *"if
  needed"* for the SH dates. It was **not needed**: those dates now come from the retained
  official `2026-036` itself. No HKEX request was made.

## Attempted-and-failed versus unattempted — updated

**Previously blocked, now resolved:**

* cninfo's disclosure query — revision 2 listed it as *unattempted (POST-only; unreachable with
  the available fetch tool)*. Round 3 reached it with `curl`; it is what closed G-a/G-b/G-c/G-e.
* the SH600011 FY2024 and FY2025 annual reports — revision 2 listed them as *unattempted*. Both
  are now retrieved, read at the 股本变动 section, and retained.
* the BJ FY2024 annual report summary and both 2026 interim reports — same; retrieved and retained.
* retention of the BSE mapping page — resolved by re-retrieving and retaining the page itself.
* the byte comparison between the Xueqiu mirror and the official original — now performed; see
  `official_notices/CLASSIFICATION.md`.

**Still failed, and named as such:**

* the BSE per-company announcement list (`related_announcement.html?companyCode=920000`) —
  JavaScript-only; round 2's page fetch returned no announcements and the browser pane reported a
  0×0 viewport. **Not retried in round 3**, because the platform endpoint supplies the same list.
* `www.hpi.com.cn` — four HTTP 503 responses in round 2; not retried, for the reason above.
* an official statement of the `832000 → 920000` **effective date** — four distinct routes tried
  across rounds 2–3: the mapping table, the issuer's own filings, the issuer's website, and two
  `bse.cn` searches. None states one.
* `www.cfi.net.cn` and `basic.10jqka.com.cn` (round 1, nonofficial) — `Socket is closed` / empty
  body; deliberately never retried.

**Deliberately not attempted:**

* Sina, as the vendor under question.
* HKEX, as no longer needed.
* any further nonofficial mirror.

## Round 2 record (unchanged except the timing claim)

Round 2 retrieved `2026-018` (the SH FY2025 board plan) and `2024-034` (the SH FY2023
implementation, closing G-d) from `static.cninfo.com.cn`, plus the BSE mapping page; it attempted
`www.hpi.com.cn` four times (all HTTP 503) and the BSE per-company list twice (JavaScript-only);
it fetched `finalpage/2025-04-22/1223221764.PDF`, which proved to be the BJ **2025 Q1** report
(`2025-041`), not the FY2024 annual report. Its four queries (#17–#20) stand as recorded in
revision 2: #17 and #18 failed to surface `2026-036` on any official host; #19 found no 2024
distribution announcement; #20 found the `2024-034` PDF.

## Round 1 record (unchanged)

Sixteen queries (#1–#16) and eleven fetches: identity searches for both codes; period-by-period
distribution searches for both issuers with and without official-host domain filters; the
`2025-103` official PDF at #8; the FY2025 annual-report summary at #7; the `2025-036` platform id
at #14; a Tier C lead for the BJ FY2025 implementation at #15; nothing for H1-2024 at #16.
Failures: `https://www.bse.cn/company/stock_detail.html?920000` → HTTP 404 (a guessed path);
`https://www.cfi.net.cn/p20250507004089.html` → `Socket is closed`, then an empty body;
`http://basic.10jqka.com.cn/832000/event.html` and
`https://basic.10jqka.com.cn/832000/bonus.html` → `Socket is closed`.

## Honest characterisation of the coverage

The decisive change in round 3 is **not** better search wording — it is that the enumeration no
longer depends on a search index at all. Search-engine indexing of `bse.cn` and `cninfo.com.cn`
returned nothing from 2024 for the BSE issuer across rounds 1–2 and never surfaced `2026-036` on
an official host, while the platform's own listing endpoint returned all of them on the first
call. Everything rounds 1–2 reported as *"attempted and failed"* was therefore a limitation of
the retrieval route, exactly as those rounds said, and **never** evidence about the issuers.

What the enumeration supports and what it does not is stated in `disclosure_index/README.md` and
in `REPORT.md` §4. In particular a **title-keyword scan is a scan of titles, not of document
bodies**, and the enumeration is the platform's holding for these two issuers over the queried
window — not a proof that no document exists on some other official host.
