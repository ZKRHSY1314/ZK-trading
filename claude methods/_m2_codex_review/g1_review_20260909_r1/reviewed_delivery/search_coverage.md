# G-1 search coverage, failures and method

Task `G1-OFFICIAL-CA-20260909`, executed 2026-09-09 between 04:55Z and 05:10Z. Network use was
confined to the approved public corporate-action lookup and the issuer-identity verification it
requires. **No local file and no raw vendor data was uploaded to any search service.**

## Method and a deliberate exclusion

Searches were driven by **issuer and reporting period** — the complete enumeration of occasions
on which either issuer could have distributed inside the interval (FY2023 annual, H1-2024,
FY2024 annual, H1-2025, FY2025 annual, H1-2026) — not by the dates of the price-ratio series.
The G-3 series was consulted only **after** the official documents were gathered, and only
read-only.

**Sina was excluded as a corporate-action source on purpose.** Sina is the vendor whose price
basis is the open question; using its dividend pages as the independent evidence would be
circular. Several search results pointed at Sina announcement mirrors; none was fetched or used.
`同花顺 (10jqka)` and `中财网 (cfi.net.cn)` were treated as **pointers only** — and both failed to
render in any case (see below).

## Queries issued

| # | Query | Domain filter | Outcome |
|---|---|---|---|
| 1 | `600011 沪市 股票代码 公司名称 华能国际 上海证券交易所` | — | identified SH600011 = 华能国际电力股份有限公司; SSE company page surfaced |
| 2 | `920000 北交所 股票代码 公司 证券简称 北京证券交易所` | — | established the `920000–920999` BSE range and the 2025-10-09 exchange-wide switchover context |
| 3 | `"920000" 北交所 上市公司 证券简称 原代码` | — | first indication of 安徽凤凰 / former code 832000 (summary only — later verified from filings) |
| 4 | `安徽凤凰 920000 832000 北交所 代码变更 公告 bse.cn` | — | surfaced the cninfo filing `2025-053` used for identity |
| 5 | `安徽凤凰 832000 权益分派实施公告 2025年 每股现金红利 股权登记日 除权除息日` | — | surfaced cninfo `2025-082` and aggregator pointers to the H1-2025 and FY2024 announcements |
| 6 | `"安徽凤凰" "权益分派实施公告" 除权除息日 股权登记日 2024年年度 每10股派` | — | aggregator pointers only; no official document |
| 7 | `安徽凤凰 权益分派实施公告 除权除息日` | `cninfo.com.cn` | surfaced the FY2025 annual-report summary and the Q3-2025 report under code 920000 |
| 8 | `安徽凤凰 920000 权益分派 实施 现金红利 每10股` | `bse.cn` | **surfaced the official BSE PDF for `2025-103`** (event E-3) and the BSE 新旧代码对照表 page |
| 9 | `安徽凤凰 2024年年度权益分派实施公告 权益登记日 除权除息日` | `bse.cn` | no 2024/2025-05 announcement indexed |
| 10 | `"安徽凤凰" "2024年年度权益分派实施公告" 832000 公告编号` | — | aggregator pointers only (slug indicates a 2025-05-07 publication) |
| 11 | `安徽凤凰 权益登记日 2024年9月 除权除息日 现金红利 滤清器` | `bse.cn`, `cninfo.com.cn` | nothing from 2024 indexed |
| 12 | `安徽凤凰 滤清器 2024年年度权益分派实施公告 每10股派 0.8 权益登记日 2025年5月` | `bse.cn` | nothing new |
| 13 | `华能国际 600011 2025年年度权益分派实施公告 除权除息日 每股现金红利 2026年` | — | surfaced 上海证券报, the cninfo plan `2026-018`, an HKEX filing and the mirrored `2026-036` |
| 14 | `华能国际 600011 2024年年度权益分派实施公告 股权登记日 除权息日 每股现金红利 2025年7月` | — | surfaced the disclosure-platform id for `2025-036` (event E-1) |
| 15 | `"安徽凤凰" 920000 2025年年度权益分派实施公告 2026年 权益登记日 除权除息日 每10股派0.8元` | — | Tier C lead for the FY2025 implementation dates; no official document |
| 16 | `"安徽凤凰" 832000 2024年半年度权益分派实施公告 权益登记日 2024年9月 除权除息日 每10股派0.6元` | — | nothing; gap G-a stands |

## Documents fetched

| URL | Result |
|---|---|
| `https://www.bse.cn/company/stock_detail.html?920000` | **HTTP 404** — the guessed BSE company-page path does not exist |
| `http://static.cninfo.com.cn/finalpage/2025-07-01/1224057969.PDF` | retrieved; `2025-053`, used for **identity** (code 832000 as of 2025-07-01) |
| `https://static.cninfo.com.cn/finalpage/2025-07-01/1224057934.PDF` | retrieved; `2025-082` — a governance rule, **not** a distribution; not retained |
| `https://www.bse.cn/disclosure/2025/2025-09-10/fbcef28bfcee4cb1ba8e287f0ab68658.pdf` | retrieved; **event E-3**, Tier A |
| `http://dataclouds.cninfo.com.cn/sjother2/bse_onmarket/2026/20260421/0bd035a264234374b353418af424f2f7.pdf` | retrieved; FY2025 annual-report summary — **event E-4 plan**, Tier A, and observation N-1 |
| `https://paper.cnstock.com/html/2026-06/25/content_2234858.htm` | retrieved as HTML; 上海证券报 text of `2026-036`. Its date table rendered as `■` placeholders, so the dates were taken from the mirrored filing instead |
| `https://stockmc.xueqiu.com/202606/600011_20260625_8Y0U.pdf` | retrieved; the `2026-036` filing text **including** the date table — **event E-2**, Tier A− |
| `https://static.cninfo.com.cn/finalpage/2025-07-02/1224057212.PDF` | retrieved; **event E-1**, Tier A |
| `https://www.cfi.net.cn/p20250507004089.html` | **failed twice** — one `Socket is closed`, one empty body. This was the pointer to the FY2024 BJ implementation; gap **G-b** |
| `http://basic.10jqka.com.cn/832000/event.html` | **failed** — `Socket is closed` |
| `https://basic.10jqka.com.cn/832000/bonus.html` | **failed** — `Socket is closed` |

Every PDF arrived as binary and was read page-by-page from the locally saved copy; the five that
carry evidence are retained in `official_notices/` with their hashes.

## Not attempted, and why

* **The BSE 新旧代码对照表** (`https://www.bse.cn/service/code_mapping.html`) — surfaced but not
  fetched; the code change is instead bracketed by two official filings. Gap **G-g**.
* **The HKEX filing** for the FY2024 dividend (`hkexnews.hk/.../2025070100025_c.pdf`) — surfaced
  but not needed once the cninfo original for `2025-036` was read.
* **cninfo full-text search** — its query endpoint is POST-only and not reachable with the
  available fetch tool, which is the main reason the 2024 BJ announcements stayed unresolved.
* **Any 行情/market-data endpoint, database, service or token** — out of scope and not touched.

## Honest characterisation of the coverage

Search-engine indexing of `bse.cn` and `cninfo.com.cn` returned 2025 and 2026 filings readily
but returned **nothing from 2024** for this issuer. That is a property of the index, not evidence
about the issuer: the absence of a retrievable 2024 announcement does **not** mean no
distribution occurred in 2024. Two of the six candidate distribution occasions in the interval
therefore remain unresolved (**G-a**, **G-b**), one is confirmed only as a plan (**G-c**), and
three are confirmed as implementations (**E-1**, **E-2**, **E-3**).
