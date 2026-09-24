# G-1: official corporate-action evidence for SH600011 and BJ920000, 2024-08-13 … 2026-07-23

> **Revision 2** — task `G1-R1-20260909`, correcting and continuing `G1-OFFICIAL-CA-20260909`
> against findings **G1-R1**, **G1-R2** and **G1-R3** of
> `M2B_G1_CORPORATE_ACTIONS_CODEX_REVIEW.md`. The v1 delivery is frozen by the reviewer at
> `_m2_codex_review/g1_review_20260909_r1/reviewed_delivery/` and was not touched. The original
> five PDFs in `official_notices/` are unchanged; two official PDFs and a classification note
> were added.
>
> **Scope.** A bounded, read-only lookup of **public official** corporate-action disclosures
> (cash dividends, bonus shares, capital-reserve conversion, rights issues) for exactly the two
> stocks of the retained comparison, over exactly the 470-session interval **2024-08-13 to
> 2026-07-23 inclusive**. The issuer universe was not expanded. Preferred-share distributions
> are **out of scope** by reviewer direction. No market-data capture, and none is authorized.
>
> **P1 remains open, U-6 deferred, every eligibility false, source capability FAIL**, both
> capture authorizations remain consumed. Nothing here adopts a policy, sets a threshold,
> changes a basis label, gate or eligibility, or upgrades any verdict. This is an isolated local
> review artifact, never a production dataset, strategy or knowledge-base update.

## What v1 got wrong, and what this revision does about it

| Finding | v1 defect | Correction |
|---|---|---|
| **G1-R1** | a nonofficial mirror (`stockmc.xueqiu.com`) was listed among "public official notices" and cited as E-2's evidence; the tier was described as **byte-identical** to the official original although **no official original had been retrieved**; provenance claimed **official-only** retrieval | the byte-identity claim is **withdrawn**; the mirror is reclassified **NON-EVIDENCE** and is no longer cited (kept unchanged as history — see `official_notices/CLASSIFICATION.md`); the official-only claim is corrected; **no further nonofficial mirror was fetched** |
| **G1-R2** | N-1 inferred *no* bonus/conversion/rights event in 2025 from equal opening/closing capital; N-2 read `差异化分红送转：否` as a no-bonus/no-conversion/no-rights statement; the identity bracket asserted `2025-10-28` with no retained artifact; the report said "four trading days before 2026-07-23", called BJ's structure "four plateaus", and summarised the comparison as "four of six" | all six corrected below: the inferences are narrowed to what the documents state, the unsupported date is removed, **14 sessions** replaces "four trading days", **five levels / four transitions** replaces "four plateaus", and the comparison is reported as separate exact counts |
| **G1-R3** | six gaps open or unattempted | **G-d closed** with an official document; **G-g partly closed** from the BSE official mapping table; **G-a/G-b/G-c/G-e** remain open, each labelled *attempted-and-failed* or *partly attempted*, with the actual attempts recorded; **G-f withdrawn from scope** |

## Evidence tiers

| Tier | Meaning |
|---|---|
| **A** | a document hosted by the exchange, the issuer or the official disclosure platform, retrieved here and retained in `official_notices/` with its hash |
| **B (attested, not retained)** | an official-host document **read by the independent reviewer** and cited with page references in its review, which **this session could not retrieve** (HTTP 503). Facts at this tier name the attesting document and have **no retained copy here** |
| **NON-EVIDENCE** | a nonofficial commercial host. Retained only as retrieval history; never cited |
| **C (lead)** | a search-engine summary of a page that was not read. A search lead, never evidence, and **never counted as a confirmed implementation** |

Sina remains deliberately excluded as a corporate-action source: it is the vendor whose price
basis is the open question, so using it would be circular.

## 1. Identity and code history

**SH600011 = 华能国际电力股份有限公司 (Huaneng Power International, Inc.)**, SSE, code `600011`
throughout the interval — Tier A from three retained announcement headers.

**BJ920000 = 安徽凤凰滤清器股份有限公司 / ANHUI PHOENIX FILTER CO., LTD**, BSE, 91,680,000 shares.
The **official** BSE 新旧代码对照表 (<https://www.bse.cn/service/code_mapping.html>, retrieved
2026-09-09T05:25:40Z) carries this issuer at **row 214**: 证券简称 安徽凤凰, 上市日期 **2020/12/23**,
旧代码 **832000**, 新代码 **920000**.

Two cautions, both corrections to v1:

* the `2020/12/23` column is the **listing date**, not the code-change date;
* **the page states no effective date** for the switch, so the code-change date is **unknown**.

The change is bracketed by retained filings only: **still `832000` on 2025-09-10** (`2025-103`
header) and **already `920000` on 2026-04-21** (`2026-006` cover). **The v1 claim of 2025-10-28
is removed** — no primary artifact for that date was retrieved by this session.

## 2. Events with an ex-date inside the interval

### E-1 — SH600011, FY2024 · **Tier A**

`公告编号 2025-036`《2024年年度权益分派实施公告》— implementation. Approval **2025-06-24**
(`2024年年度股东大会`); announced 2025-07-02; 股权登记日 **2025-07-09**; 除权（息）日 **2025-07-10**;
发放日 **2025-07-10**; `A 股每股现金红利0.27元人民币（含税）`; basis 15,698,093,359 股; total
4,238,485,206.93 元. The 分配方案 provides **cash only**. Retained:
`official_notices/cninfo_600011_2025-036_…pdf` p.1. Source
<https://static.cninfo.com.cn/finalpage/2025-07-02/1224057212.PDF>. The reviewer independently
read the same official URL.

### E-2 — SH600011, FY2025 · **plan Tier A; implementation Tier B**

**Plan (Tier A, retained).** `公告编号 2026-018`《关于2025年度利润分配方案的公告》, announced
**2026-03-25**, decided by 第十一届董事会第十八次会议: `每股派发现金红利0.40元人民币（含税）`, basis
15,698,093,359 股, 预计共派发 6,279,237,343.60 元. The document states its own limit:
`本次利润分配以实施权益分派股权登记日登记的总股本为基数，具体日期将在权益分派实施公告中明确` — i.e. **it fixes
no dates**. Retained: `official_notices/cninfo_600011_2026-018_…pdf` p.1.

**Implementation (Tier B — attested, not retained).** `公告编号 2026-036`, approval **2026-06-16**
(`2025年度股东会`), announced **2026-06-25**, 股权登记日 **2026-07-02**, 除权（息）日 **2026-07-03**,
发放日 **2026-07-03**, 0.40 元/share gross. These facts rest on the **reviewer's read of the
issuer's own official PDF** (`https://www.hpi.com.cn/Announcement/华能国际2025年年度权益分派实施公告.pdf`,
p.1 dates/amount, p.3 announcement date), recorded in `M2B_G1_CORPORATE_ACTIONS_CODEX_REVIEW.md`.
**My own retrieval of that URL failed: HTTP 503 on three attempts, plus HTTP 503 on the issuer's
announcement index.** I therefore hold **no retained official copy**, and the previously cited
Xueqiu mirror is **non-evidence**. 上海证券报 (an SSE-designated disclosure newspaper) independently
carries the same 公告编号, per-share amount, share basis, total and approval date, but its date
table rendered as placeholder glyphs, so **no date was taken from it**.

### E-3 — BJ920000 (as `832000`), H1-2025 · **Tier A**

`公告编号 2025-103`《2025年半年度权益分派实施公告》, published on the exchange's own site.
Approval **2025-09-05** (`2025年第二次临时股东会`); announced **2025-09-10**; 权益登记日 **2025-09-17**;
除权除息日 **2025-09-18**; 现金红利发放日 **2025-09-18**;
`以公司现有总股本 91,680,000 股为基数，向全体股东每 10 股派 0.70 元人民币现金` = **0.070 元/股（含税）**;
total 6,417,600.00 元; tax 差别化 (≤1 月 0.14 元/10股 补缴, >1 月至 1 年 0.07 元, >1 年 免缴; QFII
实际每 10 股派发 0.63 元). The 方案 provides **cash only**. Retained:
`official_notices/bse_832000_2025-103_…pdf` pp.1–2. Source
<https://www.bse.cn/disclosure/2025/2025-09-10/fbcef28bfcee4cb1ba8e287f0ab68658.pdf>. The reviewer
read a copy of the same announcement on an alternative official host
(`static.cninfo.com.cn/finalpage/2025-09-10/1224649747.PDF`); **no hash identity between the two
hosts' files is claimed by either side**.

### E-4 — BJ920000, FY2025 · **plan Tier A; implementation NOT confirmed**

The **plan** is Tier A: the FY2025 annual-report summary, `公告编号 2026-006` (re-read from the
retained file and confirmed), published **2026-04-21**, shows in `1.5 权益分派预案` —
`每 10 股派现数（含税） 0.8`, `每 10 股送股数 0`, `每 10 股转增数 0`, under the header `单位：元/股`.
That is a **预案**.

A **Tier C lead** reports approval 2026-05-12, 权益登记日 2026-05-22, 除权除息日 2026-05-25,
0.80 元/10股, total 7,334,400.00 元. **No document was read; it is not evidence and is not counted
as a confirmed implementation** (gap **G-c**).

## 3. One event established and excluded by date — closes G-d

**E-0 — SH600011, FY2023 · Tier A.** `公告编号 2024-034`《2023年年度权益分派实施公告》, approval
**2024-06-25**, announced **2024-07-03**, 股权登记日 **2024-07-10**, 除权（息）日 **2024-07-11**,
发放日 **2024-07-11**, `A 股每股现金红利 0.20 元人民币（含税）`, basis 15,698,093,359 股, total
3,139,618,671.80 元, `差异化分红送转： 否`. **Both the announcement and the ex-date precede
2024-08-13, so this event is outside the interval** and is not compared. Retained:
`official_notices/cninfo_600011_2024-034_…pdf` p.1. Source
<http://static.cninfo.com.cn/finalpage/2024-07-03/1220521266.PDF>.

## 4. Bounded observations — narrowed per G1-R2

* **N-1 (Tier A).** The FY2025 annual-report summary shows 总股本 **91,680,000** at 期初 and 期末
  with `本期变动 0`, and a plan with 送股 0 / 转增 0. **What that supports:** the **net reported**
  share capital did not change over FY2025, and that specific plan carries no bonus or conversion
  component. **What it does not support:** that *no* bonus/conversion/rights event occurred in
  2025 — **offsetting intra-period changes are not excluded by equal opening and closing
  balances** — nor anything about 2024 or 2026. The v1 no-event wording is withdrawn.
* **N-2 (Tier A / B).** Each retrieved SH600011 announcement carries `差异化分红送转： 否`. That
  line means **no differential distribution**; it is **not** a standalone no-bonus/no-conversion/
  no-rights statement. The cash-only character of E-0, E-1 and E-2 is taken from each event's own
  **分配方案 provisions**, and is not generalised to the interval. The v1 reading is withdrawn.

**Failed or empty searches prove nothing.** Every open item in §6 is *missing evidence*.

## 5. Read-only comparison with the retained G-3 series — separate, exact counts

The validated G-3 r2 series (`results.json` `538adc5c…`) was read **read-only**; nothing was
re-run. **No corporate action is inferred from any price step.** Two corrections to v1's
description of that series, both verified against it:

* BJ920000's difference has **five levels and four transitions** (v1 said "four plateaus"):
  `+0.29` (2024-08-13…2024-09-27, 32 sessions) → `+0.23` (…2025-05-14, 147) → `+0.15`
  (…2025-09-17, 89) → `+0.08` (…2026-05-22, 159) → `+0.00` (…2026-09-04, 74).
* The retained series carries **14 usable sessions strictly after 2026-07-03 through 2026-07-23**
  (2026-07-06 … 2026-07-23). v1's "four trading days before 2026-07-23" was wrong.

**Direction 1 — from each established in-interval implementation to the series.** None of these
pairs sits at a source/`updated_at` metadata boundary.

| Event | Tier | Ex-date | Official cash/share | G-3 difference before → after | Δ | Date match | Magnitude match |
|---|---|---|---|---|---|---|---|
| E-1 | A | 2025-07-10 | 0.27 | 0.65 → 0.37 | −0.28 | yes | **no — differs by 0.01** |
| E-2 | B (dates) | 2026-07-03 | 0.40 | 0.40 → 0.00 | −0.40 | yes | yes |
| E-3 | A | 2025-09-18 | 0.070 | 0.150 → 0.080 | −0.070 | yes | yes |

**Direction 2 — from each BJ transition to the evidence.**

| Transition | Δ | Established implementation on that date? |
|---|---|---|
| 2024-09-30 | −0.0600 | **none retrieved** (G-a) |
| 2025-05-15 | −0.0800 | **none retrieved** (G-b) |
| 2025-09-18 | −0.0700 | **yes — E-3, Tier A** |
| 2026-05-25 | −0.0800 | **none** — a Tier A *plan* of 0.8 元/10股 exists and a Tier C *lead* names this date (G-c) |

**Counts, kept separate (replacing v1's "four of six"):** 3 established in-interval
implementations; **2** exact date-and-magnitude matches; **1** date match with a magnitude
discrepancy; 4 BJ transitions examined, of which **1** has an established implementation, **1**
has a plan only with a lead-only date, and **2** have no retrieved evidence. **Plans counted as
matches: 0. Leads counted as matches: 0.**

One arithmetic note, stated as arithmetic on the retained series only: BJ920000's opening level
`0.29` equals the sum of its four transition magnitudes (0.06 + 0.08 + 0.07 + 0.08). Two of those
four magnitudes have **no** retrieved official counterpart, and nothing is inferred from the
identity.

**This section establishes no causation, no vendor price basis, and no threshold.** The evidence
in §§1–4 stands on its own documents and would be unchanged if the G-3 series did not exist.

## 6. Remaining gaps, with their actual state

| # | Gap | State |
|---|---|---|
| **G-a** | BJ920000 — a possible **H1-2024** distribution: existence, dates, amounts unknown | **attempted and failed** — four search formulations against `bse.cn`/`cninfo.com.cn` returned no 2024 announcement for this issuer; the BSE per-company announcement list is JavaScript-only and rendered nothing via page fetch or the browser pane; cninfo's full-text search is POST-only and unreachable with the available fetch tool |
| **G-b** | BJ920000 — a possible **FY2024** distribution (an aggregator slug indicates a 2025-05-07 implementation announcement) | **attempted and failed** — same official paths; the aggregator page failed twice in round 1 and was **not** re-fetched here |
| **G-c** | BJ920000 — the **FY2025 implementation** announcement (approval/record/ex dates) | **attempted and failed** — searches surfaced the plan and later 2026 filings, not the implementation |
| **G-d** | SH600011 FY2023 inside or outside the interval | **CLOSED** — E-0, ex-date 2024-07-11, outside |
| **G-e** | bonus/conversion/rights coverage across the **whole** interval | **partly attempted** — N-1 covers BJ's net FY2025 capital only; BJ's FY2024 and 2026-to-date capital tables were not retrieved (one candidate fetch turned out to be the 2025 Q1 report, `2025-041`); for SH600011 no share-capital-change section was read. **Periodic reports alone cannot settle this**, since reporting periods do not enumerate interim or extraordinary distributions |
| **G-g** | the official **effective date** of `832000 → 920000` | **partly closed** — the official mapping table confirms the pairing but states no effective date; the date remains **unknown**, bracketed to (2025-09-10, 2026-04-21] |
| ~~G-f~~ | preferred-share distributions | **withdrawn from scope** by reviewer direction |

**No promise is made that any open gap is closable.** G-a, G-b and G-c are blocked on retrieval
paths that have already failed here; G-e cannot be settled by periodic reports alone. No future
or unavailable announcement is guessed at anywhere in this artifact.

## 7. Files in this directory

| File | Role |
|---|---|
| `REPORT.md` | this corrected source-backed report (revision 2) |
| `events.json` | the structured event and evidence index (schema v2), with per-fact tiers, page references, corrections and gaps |
| `search_coverage.md` | every query and fetch attempted across both rounds, what failed and why |
| `PROVENANCE.json` | retained-notice hashes, URLs, retrieval timestamps, corrected retrieval-scope statement, preservation evidence |
| `official_notices/CLASSIFICATION.md` | per-file classification, including the superseded mirror |
| `official_notices/*.pdf` | seven retained PDFs — six official evidence, one non-evidence mirror kept as history |

**Stop: `ready_for_review`.**
