# G-1: official corporate-action evidence for SH600011 and BJ920000, 2024-08-13 … 2026-07-23

> **Revision 3** — task `G1-COMPLETE-20260909-R2`, continuing `G1-R1-20260909` and
> `G1-OFFICIAL-CA-20260909` against `M2B_G1_CORPORATE_ACTIONS_CODEX_REVIEW_R2.md`. The v1 and
> revision-2 deliveries are frozen by the reviewer at
> `_m2_codex_review/g1_review_20260909_r1/reviewed_delivery/` and
> `_m2_codex_review/g1_review_20260909_r2/reviewed_delivery/` and were not touched. **All seven
> PDFs already in `official_notices/` keep their revision-2 hashes**; twelve official files were
> added there, plus a new `disclosure_index/` folder of official-platform query responses.
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

## 0. What revision 3 changes

| Item from the R2 review | State after this pass |
|---|---|
| **remaining official-evidence pass** for G-a, G-b, G-c, G-e | **all four closed at Tier A**, via the official disclosure platform's own announcement-listing endpoint rather than a search index |
| E-2's implementation leg at **Tier B (attested, not retained)** | **upgraded to Tier A** — the official platform copy of `2026-036` was retrieved and retained. Every fact the reviewer attested is confirmed exactly. **No fact in this artifact now rests on Tier B** |
| **Tier A defined as "retained with a hash" but applied to an unretained HTML page** | resolved by **retaining the page** (`bse_code_mapping_new_old_codes.html`, `95d43bba…`). No hash was invented and the tier definition was not relaxed. See `official_notices/CLASSIFICATION.md` |
| §5 displayed BJ's final plateau as **74 sessions through 2026-09-04** while the interval ends 2026-07-23 | both figures are now given and **labelled**: **43 sessions inside the interval** (2026-05-25 … 2026-07-23) and 74 in the full retained series (… 2026-09-04). Independently recounted from the G-3 artifact, which was **not** modified |
| the unsupported claim that round 2 **ran from 05:20 UTC** | withdrawn. `search_coverage.md` now reports measured retrieval and write times, marks unmeasured round starts as unmeasured, and keeps claimed windows distinct from file times |
| the mirror's withdrawn **byte-identity** claim | the comparison can now actually be made, and it **passes** — but v1 asserted it *without having made it*, and that remains the defect. The mirror stays **NON-EVIDENCE** |

## Evidence tiers

| Tier | Meaning |
|---|---|
| **A** | a document hosted by the exchange, the issuer or the official disclosure platform, retrieved here and **retained** in `official_notices/` (or `disclosure_index/`) with its hash |
| **B (attested, not retained)** | an official-host document read by the independent reviewer and cited with page references in its review, which this session could not retrieve. **Now unused: no fact in this artifact rests on Tier B** |
| **NON-EVIDENCE** | a nonofficial commercial host. Retained only as retrieval history; never cited |
| **C (lead)** | a search-engine summary of a page that was not read. A search lead, never evidence, and never counted as a confirmed implementation. **Now unused: the one former Tier C lead has been replaced by its Tier A document** |

Sina remains deliberately excluded as a corporate-action source: it is the vendor whose price
basis is the open question, so using it would be circular.

## 1. Identity and code history

**SH600011 = 华能国际电力股份有限公司 (Huaneng Power International, Inc.)**, SSE, code `600011`
throughout the interval — Tier A from four retained announcement headers and three retained
periodic reports. The platform's own issuer record gives `orgId = gssh0600011`.

**BJ920000 = 安徽凤凰滤清器股份有限公司 / ANHUI PHOENIX FILTER CO., LTD**, BSE, 91,680,000 common
shares. The **official** BSE 新旧代码对照表 is now **retained**
(`official_notices/bse_code_mapping_new_old_codes.html`): parsing the retained bytes yields 250
`<tr>` rows, header `序号 / 证券简称 / 上市日期 / 旧代码 / 新代码`, and row **214** =
`安徽凤凰 / 2020/12/23 / 832000 / 920000`. Three further Tier A identity points:

* the platform's issuer record for `920000` carries `orgId = gfbj0832000` — the platform's own
  identifier for this issuer **embeds the old code**;
* the issuer's own website (`official_notices/issuer_phoenixfilters_home.html`) states
  `股票代码 920000` under the full legal name. It is a **product site** with no disclosure section;
* the retained filings carry `832000` in their headers through 2025-09-10 and `920000` from
  2026-04-21 (and, in the enumeration, from the `2026-037` header of 2026-05-15).

Two cautions carried forward from revision 2, both still correct:

* the `2020/12/23` column is the **listing date**, not the code-change date;
* **the mapping page states no effective date** — verified against the retained bytes, which
  contain no `生效` / `启用日` / `变更日` / `实施日` wording anywhere.

### G-g: the code-change date is still unknown, but the bracket is narrower

Two new official items, neither of which supplies a date:

* **北证公告〔2024〕231号** (2024-12-13, retained as
  `official_notices/bse_2024-231_stock_code_switch_preparation_notice.html`) sets out the switch:
  存量 companies keep their last three digits and take the `920` prefix; the switch runs
  `分批次` with a pilot batch first; and `具体事宜本所将另行通知`. **It names no date** for any
  batch. A further `bse.cn` search for a batch list returned nothing.
* the **platform's per-announcement `secCode` field** in the retained enumeration changes
  mid-series: the last announcement stored under `832000` is dated **2025-09-29** (published
  2025-09-30) and the first stored under `920000` is dated **2025-10-13** (published 2025-10-14).

The bracket therefore narrows from `(2025-09-10, 2026-04-21]` to **`(2025-09-29, 2025-10-13]`**.
Stated precisely: this narrowing rests on a **field in an official-platform search response**,
which is weaker than a statement in a filing — it is what the platform stores with each
announcement, not an exchange declaration of an effective date. **No effective date is claimed.**
The issuer published no code-change announcement of its own, and the enumeration contains no such
title, which is consistent with the switch being an exchange action.

## 2. Events with an ex-date inside the interval — six, all Tier A

### E-5 — BJ920000 (as `832000`), H1-2024 · **Tier A** · closes G-a

`公告编号 2024-068`《2024年半年度权益分派实施公告》. Approval **2024-09-12**
(`2024年第二次临时股东大会`); announced **2024-09-20** (the document's own board date and the
publication path; the platform's `announcementTime` is 2024-09-19); 权益登记日 **2024-09-27**;
除权除息日 **2024-09-30**; 现金红利发放日 **2024-09-30**;
`以公司现有总股本 91,680,000 股为基数，向全体股东每 10 股派 0.6 元人民币现金` = **0.06 元/股（含税）**;
total **5,500,800.00 元** (= 91,680,000 × 0.06, exact); 基准日 合并 未分配利润 303,552,394.23 元,
母公司 285,792,370.24 元; tax 差别化 (≤1 月 每 10 股补缴 0.120000 元, >1 月至 1 年 0.060000 元,
>1 年 免缴; QFII 实际每 10 股派发 0.540000 元). The 方案 provides **cash only**. Retained:
`official_notices/cninfo_832000_2024-068_…pdf` pp.1–2. Source
<https://static.cninfo.com.cn/finalpage/2024-09-20/1221258690.PDF>.

### E-6 — BJ920000 (as `832000`), FY2024 · **Tier A** · closes G-b

`公告编号 2025-047`《2024年年度权益分派实施公告》. Approval **2025-04-22** (`2024年年度股东会`);
announced **2025-05-07**; 权益登记日 **2025-05-14**; 除权除息日 **2025-05-15**; 现金红利发放日
**2025-05-15**; `以公司现有总股本 91,680,000 股为基数，向全体股东每 10 股派 0.8 元人民币现金` =
**0.08 元/股（含税）**; total **7,334,400.00 元** (exact); 基准日 合并 未分配利润 326,751,018.56 元,
母公司 310,254,055.62 元; tax 差别化 (0.16 / 0.08 / 免; QFII 实际每 10 股派发 0.72 元). The 方案
provides **cash only**. Retained: `official_notices/cninfo_832000_2025-047_…pdf` pp.1–2. Source
<https://static.cninfo.com.cn/finalpage/2025-05-07/1223491665.PDF>.

The matching **预案** is the FY2024 annual-report summary `公告编号 2025-022`, disclosed
**2025-03-31**, whose `1.5 权益分派预案` reads `每 10 股派现数（含税） 0.8` with the `每 10 股送股数`
and `每 10 股转增数` cells rendered as dashes (no value). Retained:
`official_notices/cninfo_832000_2025-022_…pdf` p.2.

### E-1 — SH600011, FY2024 · **Tier A**

`公告编号 2025-036`《2024年年度权益分派实施公告》. Approval **2025-06-24** (`2024年年度股东大会`);
announced **2025-07-02**; 股权登记日 **2025-07-09**; 除权（息）日 **2025-07-10**; 发放日
**2025-07-10**; `A 股每股现金红利0.27元人民币（含税）`; basis **15,698,093,359 股**; total
4,238,485,206.93 元. The 分配方案 provides **cash only**. Retained:
`official_notices/cninfo_600011_2025-036_…pdf` p.1. Source
<https://static.cninfo.com.cn/finalpage/2025-07-02/1224057212.PDF>. Round 3 re-fetched this URL
purely as an integrity check and it **reproduced the retained file's hash exactly**.

### E-3 — BJ920000 (as `832000`), H1-2025 · **Tier A**

`公告编号 2025-103`《2025年半年度权益分派实施公告》, published on the exchange's own site.
Approval **2025-09-05** (`2025年第二次临时股东会`); announced **2025-09-10**; 权益登记日
**2025-09-17**; 除权除息日 **2025-09-18**; 现金红利发放日 **2025-09-18**;
`以公司现有总股本 91,680,000 股为基数，向全体股东每 10 股派 0.70 元人民币现金` = **0.070 元/股（含税）**;
total 6,417,600.00 元; tax 差别化 (0.14 / 0.07 / 免; QFII 实际每 10 股派发 0.63 元). The 方案
provides **cash only**. Retained: `official_notices/bse_832000_2025-103_…pdf` pp.1–2. Source
<https://www.bse.cn/disclosure/2025/2025-09-10/fbcef28bfcee4cb1ba8e287f0ab68658.pdf>.

### E-4 — BJ920000 (as `920000`), FY2025 · **plan Tier A; implementation now Tier A** · closes G-c

**Plan (Tier A, retained).** The FY2025 annual-report summary, `公告编号 2026-006`, published
**2026-04-21**, `1.5 权益分派预案`: `每 10 股派现数（含税） 0.8`, `每 10 股送股数 0`,
`每 10 股转增数 0`, under `单位：元/股`. A **预案**, not an implementation.

**Implementation (Tier A, retained — replaces the former Tier C lead).** `公告编号 2026-037`
《2025年年度权益分派实施公告》, header code **920000**. Approval **2026-05-12** (`2025年年度股东会`);
announced **2026-05-15**; 权益登记日 **2026-05-22**; 除权除息日 **2026-05-25**; 现金红利发放日
**2026-05-25**; `以公司现有总股本 91,680,000 向全体股东每 10 股派 0.80 元人民币现金` =
**0.08 元/股（含税）**; total **7,334,400.00 元**; 基准日 合并 未分配利润 372,294,660.98 元,
母公司 358,008,957.03 元; tax 差别化 (0.16 / 0.08 / 免; QFII 0.72). Retained:
`official_notices/cninfo_920000_2026-037_…pdf` pp.1–2. Source
<https://static.cninfo.com.cn/finalpage/2026-05-15/1225310540.PDF>.

Revision 2's Tier C lead had named approval 2026-05-12, record 2026-05-22, ex 2026-05-25 and
total 7,334,400.00. **The official document confirms every one of those values.** That is
recorded as a fact about this document, not as retrospective validation of leads: refusing the
lead as evidence was right, and it is the document that now carries the facts.

### E-2 — SH600011, FY2025 · **plan Tier A; implementation now Tier A**

**Plan (Tier A, retained).** `公告编号 2026-018`《关于2025年度利润分配方案的公告》, announced
**2026-03-25**, decided by 第十一届董事会第十八次会议: `每股派发现金红利0.40元人民币（含税）`, basis
15,698,093,359 股, 预计共派发 6,279,237,343.60 元, and its own limit
`本次利润分配以实施权益分派股权登记日登记的总股本为基数，具体日期将在权益分派实施公告中明确` — i.e. **it fixes
no dates**. Retained: `official_notices/cninfo_600011_2026-018_…pdf` p.1.

**Implementation (Tier A, retained — replaces the Tier B attestation).** `公告编号 2026-036`
《2025年年度权益分派实施公告》. Approval **2026-06-16** (`2025年年度股东会`); announced **2026-06-25**;
`A 股每股现金红利0.40元人民币（含税）`; the 相关日期 table gives 股权登记日 **2026/7/2**, 最后交易日 **—**,
除权（息）日 **2026/7/3**, 现金红利发放日 **2026/7/3**; `差异化分红送转： 否`; basis
`公司总股本15,698,093,359股`, 共计派发 6,279,237,343.60 元; QFII 扣税后 每股 0.36 元. Retained:
`official_notices/cninfo_600011_2026-036_…pdf` pp.1–2. Source
<https://static.cninfo.com.cn/finalpage/2026-06-25/1225385939.PDF>.

**Every fact the reviewer attested at Tier B is confirmed exactly** — approval date, announcement
date, record date, ex date, payment date and per-share amount. `www.hpi.com.cn` was **not**
retried: it had already returned HTTP 503 four times, and the document is now held from an
official platform host.

## 3. One event established and excluded by date — closes G-d

**E-0 — SH600011, FY2023 · Tier A.** `公告编号 2024-034`《2023年年度权益分派实施公告》, approval
**2024-06-25**, announced **2024-07-03**, 股权登记日 **2024-07-10**, 除权（息）日 **2024-07-11**,
发放日 **2024-07-11**, `A 股每股现金红利 0.20 元人民币（含税）`, basis 15,698,093,359 股, total
3,139,618,671.80 元, `差异化分红送转： 否`. **Both the announcement and the ex-date precede
2024-08-13, so this event is outside the interval** and is not counted in §5's in-interval
totals. Retained: `official_notices/cninfo_600011_2024-034_…pdf` p.1. Source
<http://static.cninfo.com.cn/finalpage/2024-07-03/1220521266.PDF>.

## 4. Bonus shares, capital-reserve conversion and rights issues across the whole interval — G-e closed

Revision 2 left this open and said, correctly, that **equal opening and closing share capital is
not absence evidence** and that **periodic reports alone cannot settle it**. Both cautions still
hold. What closes G-e is not a re-reading of balances — it is a **complete announcement
enumeration** combined with explicit period statements and repeated distribution bases.

### 4.1 The enumeration

Using the official disclosure platform's own announcement-listing endpoint, **every** filing for
each issuer was listed over `2024-08-01 … 2026-07-31`, a window that over-covers the interval at
both ends, and paginated to completion:

| Issuer | `totalRecordNum` | Rows fetched | Titles matching 送股 / 转增 / 配股 / 股本 / 资本公积 / 回购 / 优先股 |
|---|---|---|---|
| BJ920000 (`stock=920000,gfbj0832000`) | **190** | **190** (7 pages) | **none at all** |
| SH600011 (`stock=600011,gssh0600011`) | **227** | **227** (8 pages) | **none** — and all **63** titles containing 发行 are **debt instruments** (超短期融资券, 中期票据, 公司债/公司债券, 可续期公司债券, 科技创新债券) |

The raw responses are retained in `disclosure_index/`, with the exact request parameters and two
endpoint quirks recorded in its `README.md`. The enumeration also independently shows that the
interval contains **exactly** the distribution implementations listed in §2 — four for the BSE
issuer, two for the SSE issuer — and no others.

### 4.2 Explicit period statements (Tier A)

| Issuer | Period covered | Document | What it states |
|---|---|---|---|
| SH600011 | 2024-01-01 … 2024-12-31 | FY2024 年度报告, printed p.95, 第七节 一(一)1 | `报告期内，公司股份总数及股本结构未发生变化。` — with 股份变动情况说明 不适用 and 限售股份变动情况 不适用; 证券发行 lists **debt only** |
| SH600011 | 2025-01-01 … 2025-12-31 | FY2025 年度报告, printed p.74, 第六节 一(一)1 | the same sentence, the same 不适用 rows, 证券发行 **debt only** |
| SH600011 | 2026-01-01 … 2026-06-30 | 2026 半年度报告, printed p.34, 第六节 一(一)1 | the same sentence and the same 不适用 rows |
| BJ920000 | 2024-01-01 … 2024-12-31 | `2025-022` 摘要 p.4, 2.3 普通股股本结构 | 总股本 期初 91,680,000 · **本期变动 0** · 期末 91,680,000; also 2.5 特别表决权股份 **不适用** and 2.7 优先股 **不适用** |
| BJ920000 | 2025-01-01 … 2025-12-31 | `2026-006` 摘要 p.4, 2.3 | 总股本 期初 91,680,000 · **本期变动 0** · 期末 91,680,000 |
| BJ920000 | 2026-01-01 … 2026-06-30 | `2026-047` 摘要 p.4, 2.3 | 总股本 期初 91,680,000 · **本期变动 0** · 期末 91,680,000 |

### 4.3 Repeated distribution bases (Tier A)

Each implementation notice states the share count it distributes on:

* **SH600011 — 15,698,093,359 股** at record dates **2024-07-10** (E-0), **2025-07-09** (E-1) and
  **2026-07-02** (E-2): identical at all three.
* **BJ920000 — 91,680,000 股** at record dates **2024-09-27** (E-5), **2025-05-14** (E-6),
  **2025-09-17** (E-3) and **2026-05-22** (E-4): identical at all four.

### 4.4 The conclusion, and exactly what it rests on

**No bonus-share issue, capital-reserve conversion or rights issue took effect for either
A-share instrument inside the interval.** Every distribution in §2 is cash-only on its own
方案's terms.

The three supports are independent in the right way: a share-count-changing action cannot occur
without its own implementation announcement (**none exists in either enumeration**), it would
break the period statements (**all six say no change**), and it would move the distribution basis
(**both bases are constant across the interval**). In particular, revision 2's objection that
*offsetting intra-period changes are not excluded by equal opening and closing balances* is
answered **by the enumeration**, not by the balances: either leg of an offsetting pair would
require its own announcement, and there is none.

Three residual limits, stated rather than papered over:

1. the enumeration is the **disclosure platform's holding** for these two issuers over the
   queried window, completely paginated. It is not a proof that no document exists on some other
   official host;
2. it is a scan of **titles**, not of document bodies;
3. **2026-07-01 … 2026-07-23** has no period statement covering it (the interim reports stop at
   2026-06-30). For those 23 calendar days the support is the enumeration plus, for SH600011,
   E-2's 2026-07-02 basis; for BJ920000 it is the enumeration alone.

### 4.5 Bounded observations

* **N-1 (Tier A).** An annual summary's equal 期初/期末 总股本 with `本期变动 0` supports only that
  the **net reported** count did not change over that period. It does **not** by itself exclude
  offsetting intra-period changes. That limitation is real; §4.4 closes the question with the
  enumeration, not with this observation.
* **N-2 (Tier A).** `差异化分红送转： 否` means **no differential distribution**. It is **not** a
  standalone no-bonus/no-conversion/no-rights statement. Each event's cash-only character is
  taken from its own **分配方案 provisions**.
* **N-3 (Tier A, bounded).** 北证公告〔2024〕231号 states that after a code switch
  `股票在北交所上市以来的行情信息按照新代码连续展示` and that
  `代码切换后首个交易日，股票前收盘价以其前一交易日原代码收盘价为其前收盘价`. **What that supports:**
  the exchange displays this issuer's history continuously under `920000` and applies **no price
  adjustment at the switch itself**. **What it does not support:** anything about how any vendor
  adjusts prices, or what basis any vendor's series is on. It is recorded because it explains how
  a series can legitimately be served under `920000` for dates when the code was `832000`, and
  for no other purpose.

## 5. Read-only comparison with the retained G-3 series

The validated G-3 r2 series (`results.json` `538adc5c…`) was read **read-only**; nothing was
re-run and the artifact was **not modified**. **No corporate action is inferred from any price
step, and no tolerance or matching rule is defined.**

### 5.1 Interval-restricted versus full-series figures — the R2 display repair

The G-3 artifact's reference spans run past the task interval on both instruments, so its own run
lengths are **full-series** figures. Both readings are given here, each labelled:

| BJ920000 difference level | Artifact run (full series) | **Inside the 470-session interval** |
|---|---|---|
| `+0.29` | 2024-08-13 … 2024-09-27, 32 sessions | 32 |
| `+0.23` | 2024-09-30 … 2025-05-14, 147 | 147 |
| `+0.15` | 2025-05-15 … 2025-09-17, 89 | 89 |
| `+0.08` | 2025-09-18 … 2026-05-22, 159 | 159 |
| `+0.00` | 2026-05-25 … **2026-09-04, 74** | **2026-05-25 … 2026-07-23, 43** |

Recounted directly from the artifact: BJ has **501** compared dates, of which **470** fall inside
the interval and **31** after it, and the final level holds **43** of those 470. Only the final
level differs; the first four lie wholly inside the interval. Revision 2 printed the 74 without
saying it was full-series — that is the defect being repaired.

The same distinction applies to SH600011: its reference span is **2024-06-21 … 2026-09-04** with
**538** compared dates, of which **470** fall inside the interval. Its final `0.00` run is **46
sessions** full-series (2026-07-03 … 2026-09-04) and **15** inside the interval (2026-07-03 …
2026-07-23) — of which **14 lie strictly after** the 2026-07-03 ex-date, which is the figure
revision 2 reported.

**SH600011's difference is not piecewise constant.** Over the full series it has **233 runs and
31 distinct rounded values**, wandering between 0.00 and 0.87; only two moves are large. BJ's, by
contrast, has exactly **five levels and four transitions**. Any wording suggesting the two
instruments behave alike would be wrong.

### 5.2 Direction 1 — from each established in-interval implementation to the series

Difference is `vendor_close − reference_close`. **None of these six pairs sits at, or crosses, a
source/`updated_at` metadata boundary** — verified per pair against the artifact's own
`metadata_boundary` and `interval_metadata_boundary` flags, both `false` in all six cases. Every
metadata boundary in either series lies outside the interval.

| Event | Tier | Ex-date | Official cash/share | Difference before → after | Δ | Date match | Magnitude match |
|---|---|---|---|---|---|---|---|
| E-5 | A | 2024-09-30 | 0.06 | 0.29 → 0.23 | −0.06 | yes | **yes** |
| E-6 | A | 2025-05-15 | 0.08 | 0.23 → 0.15 | −0.08 | yes | **yes** |
| E-1 | A | 2025-07-10 | 0.27 | 0.65 → 0.37 | −0.28 | yes | **no — differs by 0.01** |
| E-3 | A | 2025-09-18 | 0.070 | 0.15 → 0.08 | −0.07 | yes | **yes** |
| E-4 | A | 2026-05-25 | 0.08 | 0.08 → 0.00 | −0.08 | yes | **yes** |
| E-2 | A | 2026-07-03 | 0.40 | 0.40 → 0.00 | −0.40 | yes | **yes** |

### 5.3 Direction 2 — from each BJ transition to the evidence

| Transition | Δ | Established implementation on that date? |
|---|---|---|
| 2024-09-30 | −0.0600 | **yes — E-5, Tier A** (`2024-068`) |
| 2025-05-15 | −0.0800 | **yes — E-6, Tier A** (`2025-047`) |
| 2025-09-18 | −0.0700 | **yes — E-3, Tier A** (`2025-103`) |
| 2026-05-25 | −0.0800 | **yes — E-4, Tier A** (`2026-037`) |

BJ920000 now has **exactly four** official implementations with ex-dates inside the interval and
**exactly four** difference transitions, pairing one-to-one with no leftovers on either side.
Revision 2's arithmetic note also resolves: the opening level `0.29` equals the sum of the four
transition magnitudes (0.06 + 0.08 + 0.07 + 0.08), and **all four magnitudes now have a retrieved
official counterpart**. Nothing is inferred from that identity.

### 5.4 Counts, kept separate

* **6** established in-interval implementations, **all Tier A**.
* **5** exact date-and-magnitude matches.
* **1** date match with a magnitude discrepancy (E-1: 0.28 observed against 0.27 disclosed).
* **4** BJ transitions examined; **4** have an established implementation; **0** rest on a plan or
  a lead.
* **Plans counted as matches: 0. Leads counted as matches: 0. Facts resting on Tier B: 0.**

**Full-series context, labelled as such and excluded from the counts above.** The retained SH
series begins 2024-06-21, so it also spans E-0, whose ex-date 2024-07-11 is **before** the
interval: the difference there moves 0.87 → 0.67, Δ **−0.20**, against E-0's disclosed 0.20/share,
with no metadata boundary at that pair. Recorded for completeness only and **not** counted as an
in-interval match.

### 5.5 The E-1 discrepancy, unresolved on purpose

E-1 is the one date-matched pair whose magnitude disagrees: the series moves **0.28** where the
official announcement says **0.27 元/股**. Revision 3 retrieved and re-verified that document
again, including a byte-exact re-fetch of its source URL, so **the 0.27 is not in doubt**. No
explanation for the 0.01 is offered, no tolerance is invented to absorb it, and it is not treated
as immaterial. It stands as an open discrepancy.

### 5.6 What this section does not establish

**No causation, no vendor price basis, no threshold.** Six same-day coincidences with five exact
magnitudes are a stronger coincidence than revision 2 could report, and they remain a coincidence
of dates and magnitudes. The evidence in §§1–4 stands on its own documents and would be unchanged
if the G-3 series did not exist.

## 6. Gap ledger

| # | Gap | State |
|---|---|---|
| **G-a** | BJ920000 — an H1-2024 distribution | **CLOSED** — E-5, `2024-068`, Tier A, ex-date 2024-09-30, 0.06 元/股 |
| **G-b** | BJ920000 — an FY2024 distribution | **CLOSED** — E-6, `2025-047`, Tier A, ex-date 2025-05-15, 0.08 元/股 |
| **G-c** | BJ920000 — the FY2025 implementation | **CLOSED** — E-4 implementation, `2026-037`, Tier A, ex-date 2026-05-25, 0.08 元/股 |
| **G-d** | SH600011 FY2023 inside or outside the interval | **CLOSED** — E-0, ex-date 2024-07-11, outside |
| **G-e** | bonus/conversion/rights across the whole interval | **CLOSED** — see §4, with the three residual limits stated there |
| **G-g** | the official **effective date** of `832000 → 920000` | **STILL OPEN** — no official document states one. Four distinct routes tried across rounds 2–3. Bracket narrowed to **(2025-09-29, 2025-10-13]** from official-platform per-announcement metadata, which is weaker than a filing statement |
| ~~G-f~~ | preferred-share distributions | **withdrawn from scope** by reviewer direction |

Also newly closed, though never numbered as gaps: **E-2's Tier B dependency** (now Tier A) and
**the mirror byte comparison** (now performed; see `official_notices/CLASSIFICATION.md`).

**G-g may well not be closable from public disclosure.** The exchange said the arrangements would
be notified separately, and no such notice is reachable here. Nothing about it is guessed, and no
capture or further authorization is requested to close it — it is reported as unknown, with its
bracket.

**Failed or empty searches still prove nothing**, and that principle is what round 3 vindicated:
everything rounds 1–2 recorded as *attempted and failed* was a limitation of the retrieval route,
and every one of those items turned out to exist.

## 7. Files in this directory

| File | Role |
|---|---|
| `REPORT.md` | this report (revision 3) |
| `events.json` | the structured event and evidence index (schema v3), with per-fact tiers, page references, corrections and the gap ledger |
| `search_coverage.md` | every query and fetch across all three rounds, what failed and why, with corrected timing |
| `PROVENANCE.json` | retained-file hashes, URLs, retrieval timestamps, retrieval-scope statement, preservation evidence |
| `official_notices/CLASSIFICATION.md` | per-file classification, the A-tier repair, and the mirror |
| `official_notices/*.pdf`, `official_notices/*.html` | 19 retained files — 18 official evidence, 1 non-evidence mirror kept as history |
| `disclosure_index/README.md` | the official query endpoints, exact parameters, record counts and limits |
| `disclosure_index/*.json` | 19 raw official-platform query responses |
| `disclosure_index/derived_*.txt` | 2 derived title listings; the JSON is authoritative |

**Stop: `ready_for_review`.**
