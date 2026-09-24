# G-1 search coverage, failures and method — revision 2

Round 1 (`G1-OFFICIAL-CA-20260909`) ran 2026-09-09 04:55Z–05:10Z. Round 2 (`G1-R1-20260909`,
this correction) ran 2026-09-09 05:20Z–05:35Z. Network use in both rounds was confined to the
approved public corporate-action lookup and the issuer-identity verification it requires.
**No local file and no raw vendor data was uploaded to any search service.**

## Corrected statement of retrieval scope (G1-R1)

The v1 provenance said retrieval was official-only. **That was wrong.** The accurate statement:

* **Round 1** retrieved documents from `bse.cn`, `static.cninfo.com.cn` and
  `dataclouds.cninfo.com.cn` (all official) — **and also** from `paper.cnstock.com` (an
  SSE-designated disclosure newspaper, not an exchange/issuer/platform host) and
  **`stockmc.xueqiu.com` (a nonofficial commercial host)**. It additionally **attempted** two
  nonofficial aggregator fetches (`cfi.net.cn`, `basic.10jqka.com.cn`), which failed.
* **Round 2** retrieved only from official hosts (`bse.cn`, `static.cninfo.com.cn`) and
  **attempted** the issuer's own official host (`www.hpi.com.cn`), which failed. **No further
  nonofficial mirror was fetched.**

`official_notices/CLASSIFICATION.md` classifies every retained file accordingly.

## Method, and a deliberate exclusion

Searches were driven by **issuer and reporting period** — FY2023 annual, H1-2024, FY2024 annual,
H1-2025, FY2025 annual, H1-2026 — not by the dates of the price-ratio series. The reviewer's
caution is recorded and accepted: **reporting periods alone do not enumerate all possible interim
or extraordinary distributions**, so this enumeration is a floor, not a complete space of events.
The G-3 series was consulted only after the documents were gathered, and only read-only.

**Sina was excluded on purpose** as a corporate-action source (it is the vendor under question).
`同花顺 (10jqka)` and `中财网 (cfi.net.cn)` were treated as pointers only in round 1 and were not
used as evidence; both failed to render in any case.

## Round 2 fetches

| URL | Result |
|---|---|
| `https://www.hpi.com.cn/Announcement/华能国际2025年年度权益分派实施公告.pdf` | **HTTP 503** (attempt 1, raw Chinese path) |
| `…/Announcement/%E5%8D%8E…%E5%85%AC%E5%91%8A.pdf` (percent-encoded) | **HTTP 503** (attempt 2) |
| `https://www.hpi.com.cn/Announcement/华能国际2025年年度权益分派实施公告.pdf` | **HTTP 503** (attempt 3, retry) |
| `https://www.hpi.com.cn/announcement/publish.aspx` (issuer A股公告 index) | **HTTP 503** |
| `http://static.cninfo.com.cn/finalpage/2026-03-25/1225029357.PDF` | **retrieved** — `2026-018` FY2025 **plan**, Tier A, retained |
| `https://www.bse.cn/service/code_mapping.html` | **retrieved** — official 新旧代码对照表; row 214 gives 安徽凤凰 / 上市日期 2020-12-23 / 旧代码 832000 / 新代码 920000, and the page states **no** effective date |
| `https://www.bse.cn/products/neeq_listed_companies/related_announcement.html?companyCode=920000` | **JavaScript-only** — no announcements in the page text |
| the same URL loaded in the browser pane | **rendered nothing usable** — the tab reported a 0×0 viewport and resolved to `https://bse.cn`; no announcement list obtained |
| `https://static.cninfo.com.cn/finalpage/2025-04-22/1223221764.PDF` | retrieved — turned out to be the **2025 Q1 report** (`公告编号 2025-041`, code 832000), **not** the FY2024 annual report; useful only as an identity data point, not retained |
| `http://static.cninfo.com.cn/finalpage/2024-07-03/1220521266.PDF` | **retrieved** — `2024-034` FY2023 implementation, Tier A, retained; **closes G-d** |

## Round 2 queries

| # | Query | Domain filter | Outcome |
|---|---|---|---|
| 17 | `华能国际 2026-036 2025年年度权益分派实施公告 finalpage` | `cninfo`, `sse`, `hkexnews` | the `2026-036` implementation is **not indexed** on those official hosts; surfaced the `2026-018` plan and the 2025年度股东会会议资料 |
| 18 | `华能国际 权益分派实施公告 股权登记日 2026年7月2日 除权 2026年7月3日` | `cninfo`, `sse`, `hpi.com.cn` | again no `2026-036`; surfaced SSE-hosted annual reports and the issuer's announcement index URL |
| 19 | `"安徽凤凰" 滤清器 "权益登记日" 权益分派实施公告 2024 2026` | `cninfo`, `bse` | no 2024 distribution announcement; surfaced the 2024-10-28 and 2025-10-28 quarterly reports and an alternative official host copy of `2025-103` |
| 20 | `华能国际 2023年年度权益分派实施公告 股权登记日 除权息日 2024年 每股现金红利0.20元` | `cninfo`, `sse` | **found** the official `2024-034` PDF — the round-2 success |

## Round 1 queries and fetches (unchanged record)

Sixteen queries (#1–#16) and eleven fetches, as recorded in v1: identity searches for both codes;
period-by-period distribution searches for both issuers with and without `bse.cn` / `cninfo.com.cn`
domain filters; the `2025-103` official PDF found at #8; the FY2025 annual-report summary at #7;
the `2025-036` disclosure-platform id at #14; a Tier C lead for the BJ FY2025 implementation at
#15; nothing for H1-2024 at #16. Failures: `https://www.bse.cn/company/stock_detail.html?920000`
→ HTTP 404 (guessed path); `https://www.cfi.net.cn/p20250507004089.html` → `Socket is closed`,
then an empty body; `http://basic.10jqka.com.cn/832000/event.html` and
`https://basic.10jqka.com.cn/832000/bonus.html` → `Socket is closed`.

## Attempted-and-failed versus unattempted (G1-R3)

**Attempted and failed** — a demonstrated retrieval limitation, not an untried path:

* the issuer's own official host for E-2's implementation (`hpi.com.cn`) — 4 attempts, all 503;
* the BSE per-company announcement list — JavaScript-only, and the browser pane rendered nothing;
* BJ920000's 2024 announcements and its FY2025 implementation — 6 search formulations across two
  official hosts returned nothing from 2024 and no FY2025 implementation;
* the BJ FY2024 annual report — one candidate id fetched, which proved to be the Q1-2025 report.

**Unattempted, and named as such:**

* cninfo's full-text search API (POST-only; unreachable with the available fetch tool);
* SSE's per-company announcement list (`sse.com.cn/assortment/stock/list/info/announcement`),
  which is JavaScript-driven like the BSE one;
* the SH600011 FY2024 and FY2025 **annual reports** themselves (seen in search results on official
  hosts, not read) — the most promising remaining path for **G-e**;
* the BJ920000 FY2024 annual report and 2026 interim filings — also relevant to **G-e**;
* HKEX filings for SH600011 (an official exchange host) — not needed once the cninfo originals for
  E-0 and E-1 were read, and not pursued for E-2.

## Honest characterisation of the coverage

Search-engine indexing of `bse.cn` and `cninfo.com.cn` returns 2025–2026 filings for these
issuers readily and returned **nothing from 2024** for the BSE issuer, and it does **not** index
the SH600011 `2026-036` implementation on any official host. Those are properties of the index and
of host availability — **not** evidence about the issuers. Of the six candidate distribution
occasions inside the interval, **three are established implementations** (E-1, E-3 at Tier A;
E-2's dates at Tier B), **one is a plan with an unconfirmed implementation** (E-4), and **two
remain unresolved** (G-a, G-b). One further event (E-0) was established and excluded by date.
