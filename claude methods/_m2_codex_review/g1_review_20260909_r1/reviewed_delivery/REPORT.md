# G-1: official corporate-action evidence for SH600011 and BJ920000, 2024-08-13 … 2026-07-23

> **Scope.** Task `G1-OFFICIAL-CA-20260909`. A bounded, read-only lookup of **public official**
> corporate-action disclosures (cash dividends, bonus shares, capital-reserve conversion,
> rights issues) for exactly the two stocks of the retained comparison, over exactly the
> 470-session interval **2024-08-13 to 2026-07-23 inclusive**. The issuer universe was not
> expanded. **No market-data capture** was made and none is authorized: the only network use
> was the approved public corporate-action lookup and the identity verification it requires.
>
> **This is an isolated local review artifact.** It is not a production dataset, strategy or
> knowledge-base update. **P1 remains open, U-6 deferred, every eligibility false, source
> capability FAIL**, and both historical capture authorizations remain consumed. Nothing here
> adopts a policy, sets a threshold, changes a basis label, gate or eligibility, or upgrades
> any verdict.

## Evidence tiers used throughout

| Tier | Meaning |
|---|---|
| **A** | read directly from a document hosted by the exchange or the official disclosure platform (`bse.cn`, `cninfo.com.cn`) and retained here with its hash |
| **A−** | the issuer's filing text read from an SSE-**designated disclosure newspaper** and/or a retained byte-identical mirror of the filing; the exchange-hosted original was not retrieved |
| **C** | a search-engine summary of an aggregator page, **no document read** — recorded as a *lead*, never as evidence |

No fact below is asserted above the tier of the document it came from. **Sina was deliberately
excluded as a corporate-action source**: it is the vendor whose price basis is in question, so
using it here would make the evidence circular.

## 1. Issuer identity and code history — verified before attribution

**SH600011 = 华能国际电力股份有限公司 (Huaneng Power International, Inc.)**, Shanghai Stock
Exchange, code `600011` throughout the interval. Verified from the headers
`证券代码：600011　证券简称：华能国际` on both retrieved distribution announcements (Tier A / A−).

**BJ920000 = 安徽凤凰滤清器股份有限公司 (ANHUI PHOENIX FILTER CO., LTD)**, Beijing Stock
Exchange, total share capital **91,680,000** shares. **Its code changed inside the interval:
`832000` → `920000`.** Officially bracketed, Tier A:

* `公告编号 2025-053` (2025-07-01) and `公告编号 2025-103` (2025-09-10) both carry
  **`证券代码：832000　证券简称：安徽凤凰`**;
* the FY2025 annual-report summary (`公告编号 2026-006`, 2026-04-21) carries
  **`股票代码：920000`** with the same legal name, and states
  `公司披露年度报告的证券交易所网站 www.bse.cn`.

So the announcements published under `832000` and those published under `920000` are the **same
issuer**, and attribution across the code change is safe. Public reporting places the
exchange-wide switch of existing BSE listings to the `920xxx` range at **2025-10-09**; the BSE's
own 新旧代码对照表 was **not** retrieved (gap **G-g**), so the exact effective date for this
issuer rests on the bracket above rather than on the mapping table.

*One consequence worth recording, as an observation only:* the code `920000` did not exist for
this issuer before roughly October 2025, yet the retained vendor series serves history under
`BJ920000` from long before that. That is consistent with vendor-side code remapping. It is
**not** a finding about the vendor's price basis.

## 2. Confirmed events inside the interval

### E-1 — SH600011, FY2024 annual cash dividend · **Tier A**

`公告编号 2025-036`《华能国际电力股份有限公司2024年年度权益分派实施公告》— an **implementation**
announcement, not a plan.

| Field | Value |
|---|---|
| Approval (declaration) | **2025-06-24**, `2024年年度股东大会` |
| Announcement date | 2025-07-02 (disclosure-platform publication path) |
| 股权登记日 (record) | **2025-07-09** |
| 除权（息）日 (ex) | **2025-07-10** |
| 现金红利发放日 (payment) | **2025-07-10** |
| Cash | `A 股每股现金红利0.27元人民币（含税）` |
| Share basis / total | 15,698,093,359 股 / 4,238,485,206.93 元（含税） |
| 送股 / 转增 / 配股 | `差异化分红送转： 否` — cash only |
| Tax basis | 差别化个人所得税 per 财税[2015]101号; QFII 10% per 国税函[2009]47号 |

Retained: `official_notices/cninfo_600011_2025-036_FY2024_equity_distribution_implementation.pdf`,
page 1. Source: <https://static.cninfo.com.cn/finalpage/2025-07-02/1224057212.PDF>, retrieved
2026-09-09T05:05:57Z.

### E-2 — SH600011, FY2025 annual cash dividend · **Tier A−**

`公告编号 2026-036`《华能国际电力股份有限公司2025年年度权益分派实施公告》— implementation.

| Field | Value |
|---|---|
| Approval (declaration) | **2026-06-16**, `2025年度股东会` |
| Announcement date | 2026-06-25 (as carried in 上海证券报) |
| 股权登记日 | **2026-07-02** |
| 除权（息）日 | **2026-07-03** |
| 现金红利发放日 | **2026-07-03** |
| Cash | `A 股每股现金红利0.40元人民币（含税）` |
| Share basis / total | 15,698,093,359 股 / 6,279,237,343.60 元（含税） |
| 送股 / 转增 / 配股 | `差异化分红送转： 否` — cash only |
| Tax basis | 差别化个人所得税; QFII 扣税后 每股 0.36 元 |

The ex-date **2026-07-03** falls inside the interval, four trading days before its 2026-07-23
close. Retained: `official_notices/mirror_600011_2026-036_FY2025_equity_distribution_implementation.pdf`,
pages 1–2. Sources: <https://paper.cnstock.com/html/2026-06/25/content_2234858.htm> (上海证券报,
SSE-designated disclosure newspaper) and the mirrored filing
<https://stockmc.xueqiu.com/202606/600011_20260625_8Y0U.pdf>, retrieved 2026-09-09T05:05:01Z.
**Tier A− because the SSE-hosted original was not retrieved**; the newspaper independently
carries the same 公告编号, per-share amount, share basis, total and approval date.

### E-3 — BJ920000 (as `832000`), H1-2025 interim cash dividend · **Tier A**

`公告编号 2025-103`《安徽凤凰滤清器股份有限公司2025年半年度权益分派实施公告》— implementation,
published on the exchange's own site.

| Field | Value |
|---|---|
| Approval (declaration) | **2025-09-05**, `2025年第二次临时股东会` |
| Announcement date | **2025-09-10** |
| 权益登记日 (record) | **2025-09-17** |
| 除权除息日 (ex) | **2025-09-18** |
| 现金红利发放日 (payment) | **2025-09-18** |
| Cash | `以公司现有总股本 91,680,000 股为基数，向全体股东每 10 股派 0.70 元人民币现金` = **0.070 元/股（含税）** |
| Total | 6,417,600.00 元 |
| 送股 / 转增 | none in the plan — cash only |
| Tax basis | 持股 ≤1 月 每 10 股补缴 0.14 元; >1 月至 1 年 0.07 元; >1 年 免缴; QFII 实际每 10 股派发 0.63 元 |

Retained: `official_notices/bse_832000_2025-103_2025H1_equity_distribution_implementation.pdf`,
page 1 (方案, 扣税说明) and page 2 (权益登记日与除权除息日; 权益分派方法). Source:
<https://www.bse.cn/disclosure/2025/2025-09-10/fbcef28bfcee4cb1ba8e287f0ab68658.pdf>, retrieved
2026-09-09T05:00:37Z.

### E-4 — BJ920000, FY2025 annual distribution · **plan Tier A, implementation Tier C**

The **plan** is official: the FY2025 annual-report summary (`公告编号 2026-006`, published
**2026-04-21** on `www.bse.cn`) shows, in `1.5 权益分派预案`, `每 10 股派现数（含税） 0.8`,
`每 10 股送股数 0`, `每 10 股转增数 0`. That is a **预案**, expressly not an implementation.

A **Tier C lead** — a search-engine summary of an aggregator page, with no document read —
reports approval 2026-05-12, 权益登记日 2026-05-22, 除权除息日 **2026-05-25**, 每 10 股派 0.80 元,
total 7,334,400.00 元. **This is recorded as a lead, not as evidence** (gap **G-c**): the
implementation announcement itself was not retrieved from an official source.

## 3. Bounded negative observations — not blanket no-event statements

* **N-1 (Tier A).** For BJ920000, the FY2025 annual-report summary shows 总股本 **91,680,000** at
  both 期初 and 期末 with `本期变动 0`, and the FY2025 plan shows 送股 0 and 转增 0. This supports
  *no bonus issue, capital-reserve conversion or share-count-changing rights issue taking effect
  during calendar 2025*. It says **nothing** about 2024 or 2026.
* **N-2 (Tier A / A−).** For SH600011, both retrieved announcements state `差异化分红送转： 否`.
  That covers **those two events only**, not the whole interval.

**Failed or empty searches prove nothing.** Every item in §5 is *missing evidence*, not a
confirmed absence of events.

## 4. Read-only comparison with the validated G-3 series — coincidence, not causation

The G-3 r2 analysis (validated; `results.json` `538adc5c…`, read here **read-only**, nothing
re-run) reports, for the same interval, a `vendor_close − reference_close` difference series.
Its plateau structure is set beside the official ex-dates **without any inference of cause**:

**BJ920000** — four difference plateaus, and **none** of the four step dates coincides with a
source/`updated_at` metadata boundary (`interval_metadata_boundary: false` at all four):

| G-3 step date | Δ difference | official ex-date | official cash/share | tier |
|---|---|---|---|---|
| 2024-09-30 | −0.0600 | **not retrieved** | unknown | gap G-a |
| 2025-05-15 | −0.0800 | **not retrieved** | unknown | gap G-b |
| **2025-09-18** | **−0.0700** | **2025-09-18** | **0.070** | **A** |
| 2026-05-25 | −0.0800 | 2026-05-25 *(lead)* | 0.080 *(plan: 0.8/10股, A)* | C / A |

**SH600011** — the difference is not plateaued, but it moves sharply on exactly the two official
ex-dates, neither of which is a metadata boundary:

| G-3 date | difference before → after | Δ | official ex-date | official cash/share | note |
|---|---|---|---|---|---|
| **2025-07-10** | 0.65 → 0.37 | **−0.28** | **2025-07-10** (A) | **0.27** | Δ exceeds the dividend by **0.01** |
| **2026-07-03** | 0.40 → 0.00 | **−0.40** | **2026-07-03** (A−) | **0.40** | exact |

One further arithmetic observation, stated as arithmetic: BJ920000's opening plateau **+0.29**
equals the sum of its four subsequent steps (0.06 + 0.08 + 0.07 + 0.08 = 0.29).

**What this section does and does not say.** It records that four of six magnitude/date pairs
line up, that two of the six magnitudes rest on documents that were **not** retrieved, and that
one of the matched pairs (2025-07-10) shows a **0.01 discrepancy** against the official
per-share amount. It does **not** claim causation, does **not** establish or alter the vendor's
price basis, defines **no** threshold or matching rule, and closes **neither U-6 nor P1**. The
corporate-action evidence in §§1–3 stands entirely on its own documents and would be unchanged
if the G-3 series did not exist.

## 5. Unresolved evidence gaps

| # | Gap |
|---|---|
| **G-a** | BJ920000: a possible **2024 年半年度** distribution — no official document retrieved; dates, amounts and even existence unconfirmed |
| **G-b** | BJ920000: a possible **2024 年年度** distribution — an aggregator URL slug indicates a 2025-05-07 publication titled 《2024年年度权益分派实施公告》, but the page did not render and no official document was retrieved |
| **G-c** | BJ920000: the **FY2025 implementation** announcement (approval/record/ex dates) was not retrieved; only the plan is Tier A |
| **G-d** | SH600011: whether the **FY2023** distribution's ex-date falls before 2024-08-13 (outside) or inside the interval was not determined |
| **G-e** | Both: **rights issues (配股)** were probed only indirectly; no official statement covering the whole interval was obtained either way |
| **G-f** | SH600011: **优先股** distributions were not searched (they create no common-share ex-date, but were not ruled out) |
| **G-g** | BJ920000: the BSE official **新旧代码对照表** was not retrieved; the `832000 → 920000` change rests on the two-filing bracket |

All seven are closable by further **public official** search within this same authorization; none
requires a market-data capture, a database open or any new data operation. No future or
unavailable announcement is guessed at anywhere in this artifact.

## 6. Files in this directory

| File | Role |
|---|---|
| `REPORT.md` | this source-backed report |
| `events.json` | the structured event and evidence index, with per-fact tiers, page references and gaps |
| `search_coverage.md` | every query and fetch attempted, what failed, and why |
| `PROVENANCE.json` | retained-notice hashes, URLs, retrieval timestamps, and preservation evidence |
| `official_notices/*.pdf` | the five retained public official notices (hashes in `PROVENANCE.json`) |

**Stop: `ready_for_review`.**
