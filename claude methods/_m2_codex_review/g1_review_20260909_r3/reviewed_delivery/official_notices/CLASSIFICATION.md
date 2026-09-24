# Classification of every file in this folder — revision 3

The folder name `official_notices/` was chosen in the first delivery and is **kept unchanged**
so that no retained path or byte moves. It is therefore best read as a **retrieval folder**: its
contents are classified **individually** below, and one of them is **not** an official source.
That mislabelling was the substance of finding **G1-R1** and is corrected here rather than by
deleting or renaming history.

Round 3 (`G1-COMPLETE-20260909-R2`) added twelve files. **Nothing already in the folder was
modified**: all seven pre-existing PDFs keep their revision-2 hashes.

## Every file

| File | Host | Class | Admissible as evidence? |
|---|---|---|---|
| `cninfo_600011_2024-034_FY2023_equity_distribution_implementation.pdf` | `static.cninfo.com.cn` — official disclosure platform | **official** | **yes** (Tier A) |
| `cninfo_600011_2025-036_FY2024_equity_distribution_implementation.pdf` | `static.cninfo.com.cn` | **official** | **yes** (Tier A) |
| `cninfo_600011_2026-018_FY2025_profit_distribution_plan.pdf` | `static.cninfo.com.cn` | **official** | **yes** (Tier A) — but it is a **board plan**, not an implementation |
| `cninfo_600011_2026-036_FY2025_equity_distribution_implementation.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — **this replaces the Tier B attestation for E-2** |
| `cninfo_600011_FY2024_annual_report.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — periodic report; cited for its 股本变动 statement |
| `cninfo_600011_FY2025_annual_report.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — same |
| `cninfo_600011_2026H1_report.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — same |
| `bse_832000_2025-103_2025H1_equity_distribution_implementation.pdf` | `www.bse.cn` — the exchange itself | **official** | **yes** (Tier A) |
| `cninfo_832000_2024-068_2024H1_equity_distribution_implementation.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — **closes G-a** |
| `cninfo_832000_2025-047_FY2024_equity_distribution_implementation.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — **closes G-b** |
| `cninfo_920000_2026-037_FY2025_equity_distribution_implementation.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — **closes G-c** |
| `cninfo_832000_2025-022_FY2024_annual_report_summary.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — carries the FY2024 **预案** and the FY2024 股本结构 |
| `cninfo_920000_2026-047_2026H1_report_summary.pdf` | `static.cninfo.com.cn` | **official** *(added round 3)* | **yes** (Tier A) — carries the H1-2026 股本结构 |
| `bse_920000_2026-006_FY2025_annual_report_summary.pdf` | `dataclouds.cninfo.com.cn` (BSE on-market set); the document itself names `www.bse.cn` as its disclosure site | **official** | **yes** (Tier A) — but its distribution figure is a **预案 / plan** |
| `cninfo_832000_2025-053_articles_amendment_identity.pdf` | `static.cninfo.com.cn` | **official** | **yes** (Tier A) — identity only; not a corporate action |
| `bse_code_mapping_new_old_codes.html` | `www.bse.cn` — the exchange itself | **official** *(added round 3)* | **yes** (Tier A) — see the A-tier note below |
| `bse_2024-231_stock_code_switch_preparation_notice.html` | `www.bse.cn` | **official** *(added round 3)* | **yes** (Tier A) — 北证公告〔2024〕231号; relevant to **G-g** |
| `issuer_phoenixfilters_home.html` | `www.phoenixfilters.net` — the BSE issuer's own site | **official** *(added round 3)* | **yes** (Tier A) — identity only; the site carries **no** disclosure/investor section |
| `mirror_600011_2026-036_FY2025_equity_distribution_implementation.pdf` | `stockmc.xueqiu.com` — **a nonofficial commercial host** | **NON-EVIDENCE — superseded** | **no** |

The `disclosure_index/` sibling folder holds official-platform **query responses**, classified
in its own `README.md`.

## The A-tier definition and the mapping page (repairs the revision-2 inconsistency)

Revision 2 defined Tier A as *"retrieved here and retained with its hash"* and then labelled the
BSE 新旧代码对照表 Tier A while recording `retained_copy: none`. That was inconsistent.

**It is resolved by actually retaining the page**, not by relaxing the definition and not by
inventing a hash. The page was re-retrieved in round 3 with a cookie-bearing request and is
retained as `bse_code_mapping_new_old_codes.html`
(`95d43bba3b5ca2d6e5a2654755ea732ef52fa8d2c39fe667b5d4eab533a3b877`, 459,945 bytes). The cited
row is **server-rendered in the retained bytes**, not JavaScript-injected: parsing the retained
file yields 250 `<tr>` rows, header `序号 / 证券简称 / 上市日期 / 旧代码 / 新代码`, and row **214**
= `安徽凤凰 / 2020/12/23 / 832000 / 920000`. The retained bytes also contain **no** effective-date
wording, which is the basis for saying the page states none.

Tier A therefore keeps its original meaning throughout this artifact: **retrieved here and
retained here with a hash.** No source is admitted at Tier A without a retained file.

## The mirror, and the byte comparison that can now actually be made

* The mirror is retained **only as retrieval history**, unchanged
  (`269ed39f77af653f72c171be12068561b4f5ea0e5a934c90f8a37c0c4b8fdedb`, 113,763 bytes).
* **A filing-shaped document does not become an official source through its host.** v1 cited it
  as evidence for **E-2** and described it as "byte-identical" to the official original. **That
  claim was withdrawn in revision 2 because no comparison had been performed** — no official
  original had been retrieved.
* **Round 3 retrieved the official original** from the disclosure platform
  (`https://static.cninfo.com.cn/finalpage/2026-06-25/1225385939.PDF`) and performed the
  comparison: the two files are **byte-identical**, same size and same SHA-256. So the *fact*
  v1 asserted turns out to hold — but v1 asserted it **without having done the comparison**, and
  that remains the defect. An unverified claim is not made sound by later turning out true.
* The mirror's classification is **unchanged: NON-EVIDENCE**. What changed is that E-2 no longer
  needs it: the citation is now the retained official copy
  `cninfo_600011_2026-036_FY2025_equity_distribution_implementation.pdf`.
* **No further nonofficial mirror was fetched in round 2 or round 3.**
