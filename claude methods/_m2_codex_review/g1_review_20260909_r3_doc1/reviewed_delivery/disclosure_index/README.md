# Retained official disclosure-index responses (round 3; notes corrected by `G1-DOC-20260909-R3`)

Everything in this folder is a **raw response body from the official disclosure platform
`www.cninfo.com.cn`**, retained unmodified, plus two **derived** text renderings clearly
labelled as such. The 19 raw responses are **17** `cninfo_hisAnnouncement_*` announcement pages
plus **2** `cninfo_topSearch_*` issuer lookups.

These responses back the pagination-completeness statements in `../REPORT.md` §4.1 and the
negative title-search finding in §4.4. They do **not** establish whole-interval absence of a
bonus/conversion/rights event — see §4.5 — and they do **not** yield a code-change
effective-date bracket for **G-g**; see the `secCode` field note below. Both of those readings
appeared in the revision-3 text and are withdrawn.

A public disclosure query is a **read-only lookup**. No credentials, accounts, tokens or
sign-in were used; nothing was installed; no protection was bypassed; no local file and no
vendor data was uploaded.

## The two endpoints used

| Purpose | Method | URL |
|---|---|---|
| resolve an issuer's platform `orgId` | POST | `http://www.cninfo.com.cn/new/information/topSearch/query` |
| list an issuer's announcements | POST | `http://www.cninfo.com.cn/new/hisAnnouncement/query` |

Both were called with `curl` from this session, `Content-Type:
application/x-www-form-urlencoded; charset=UTF-8`, a desktop-browser `User-Agent`, and
`Referer: http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice`.

**topSearch** body: `keyWord=<code>&maxNum=10`. Results (retained):

* `920000` → `orgId = gfbj0832000`, `zwjc = 安徽凤凰`, `category = A股`, `delisted = false`
* `600011` → `orgId = gssh0600011`, `zwjc = 华能国际`, `category = A股`, `delisted = false`

The `920000` record's own `orgId` embeds `0832000`, which is an **official-platform**
data point tying the new code to the old one, independent of the BSE mapping table.

**hisAnnouncement** body, per page:

```
tabName=fulltext&pageSize=30&pageNum=<N>&column=sse&category=&plate=
&seDate=<from>~<to>&searchkey=&sortName=&sortType=&isHLtitle=true
stock=<code>,<orgId>
```

Two observed behaviours of the endpoint are recorded because they shaped the method. They are
recorded as **observed outcomes**, without a theory of the endpoint's internals — revision 3
wrote that "`column` is effectively ignored", which contradicts the very outcomes listed below:
a genuinely ignored parameter could not produce different results for different values.

* **`column` changed the outcome, and only two of the five values tried returned anything.**
  With `stock` carrying a valid `orgId`, `column=bse`, `column=third` and `column=neeq` each
  returned `totalRecordNum 0` for `920000`, while `column=sse` and `column=szse` each returned
  the issuer's full set with identical payloads. `column=sse` was used for both issuers. **Why
  the zero-returning values behave that way was not determined and is not asserted here**; what
  matters for this artifact is that those zeros are an outcome of the parameter value, **not**
  evidence about the issuers' filings.
* **`searchkey` combined with `stock` returned nothing.** `searchkey=权益分派` and
  `searchkey=分红` both returned `totalRecordNum 0` for `920000`. The enumeration was
  therefore taken **unfiltered** and filtered locally by title.

## Retained responses and their record counts

| File(s) | Query | `totalRecordNum` | Rows fetched |
|---|---|---|---|
| `cninfo_hisAnnouncement_920000_20240801-20260731_page1..7.json` | `stock=920000,gfbj0832000`, `seDate=2024-08-01~2026-07-31` | **190** | **190** (7 pages) |
| `cninfo_hisAnnouncement_600011_20240801-20260731_page1..8.json` | `stock=600011,gssh0600011`, `seDate=2024-08-01~2026-07-31` | **227** | **227** (8 pages) |
| `cninfo_hisAnnouncement_920000_20260801-20260909_page1.json` | same issuer, `seDate=2026-08-01~2026-09-09` | 10 | 10 |
| `cninfo_hisAnnouncement_600011_20260801-20260909_page1.json` | same issuer, `seDate=2026-08-01~2026-09-09` | 11 | 11 |

Every page was fetched until `totalRecordNum` was fully accounted for, so each enumeration is
**complete for the query as stated** — no page was skipped and no result was truncated.

**`seDate` filters publication dates, not event dates.** The window `2024-08-01~2026-07-31`
brackets the task interval `2024-08-13 … 2026-07-23` in *publication* terms, which is **not** the
same as covering every event whose implementation falls inside the interval: an announcement
published before 2024-08-01 whose ex-date lands on or after 2024-08-13 is outside these results
altogether. Revision 3 described the window as "over-covering" the interval without that
distinction. The two tail queries were added only to locate the 2026 interim reports, which fall
outside the main window.

## Field meanings

* `announcementTime` — epoch milliseconds. **These are UTC+08:00 midnight stamps.** Read in
  UTC+08:00, the date equals the `finalpage/<date>/` date in `adjunctUrl` in **every one of the
  438** retained records, and 437 of the 438 epochs are exactly local midnight; the single
  exception carries a time of day, not a different date (`华能国际关于持续开展"提质增效重回报"行动的公告`,
  epoch `1744072680000` = 2025-04-08 08:38 UTC+08:00, published at `finalpage/2025-04-08/`).
  Revision 3 rendered these epochs in **UTC**, which shifts every date back one day, and then
  read the shift as the platform having announced each filing a day before its publication path.
  **That reading was an artefact and is withdrawn.** Worked examples: `1759161600000` is
  2025-09-29 16:00 UTC = **2025-09-30 00:00 UTC+08:00**; `1760371200000` is 2025-10-13 16:00 UTC
  = **2025-10-14 00:00 UTC+08:00**; E-5's `1726761600000` is **2024-09-20 00:00 UTC+08:00**,
  matching its publication date.
* `secCode` — the securities code **as stored with that announcement**. For this BSE issuer the
  stored value changes from `832000` to `920000` partway through the series: the last announcement
  stored under `832000` is dated **2025-09-30** and the first under `920000` **2025-10-14** (both
  UTC+08:00). **This is a change in platform metadata and nothing more.** Revision 3 turned it
  into a narrowed effective-date bracket for **G-g**; that is withdrawn. A platform's
  per-announcement code tagging can lag the exchange action or be maintained retrospectively, so
  **no interval of legal effectiveness follows from these two dates**. G-g stays unknown.
* `announcementTitle` — the platform's title string. Note that the keyword scan behind
  `../REPORT.md` §4.4 was applied to **these strings only**, never to document bodies.
* `adjunctUrl` — a path relative to `https://static.cninfo.com.cn/`.

## The two derived files

`derived_920000_announcement_titles.txt` and `derived_600011_announcement_titles.txt` are
**derived**, not primary. They were **regenerated** by `G1-DOC-20260909-R3` from these same
retained JSON responses — no network access — because their revision-3 form carried only the
misleading UTC date. Each line is now
`<mark> <UTC+08:00 date> (UTC <UTC date>) <secCode> | <title> | <adjunctUrl>`, sorted, one line
per announcement, with a leading `*` when the title contains any of
`分派 分红 派息 送股 转增 配股 股本 权益 利润分配 年度报告 半年度报告`. The **UTC+08:00 column is the
announcement date**; the UTC column is shown only so the raw epoch's UTC rendering is not
mistaken for a second, earlier date. The JSON responses are authoritative; if the two ever
disagree, the JSON governs.

## What these responses do and do not establish

* They **do** establish what the official disclosure platform holds for these two issuers with
  publication dates in the stated ranges, completely paginated, and they **did** yield the
  documents that closed G-a, G-b and G-c — each of which stands on the retained document itself,
  not on the enumeration.
* They **do not** establish that no document exists on some other official host; they are a scan
  of **titles**, not of document bodies; and their `seDate` filter is on **publication** dates,
  so they do not reach a pre-window announcement with an in-interval implementation. Taken
  together, that is why they cannot establish whole-interval absence of a bonus/conversion/rights
  event (`../REPORT.md` §4.5), and why **G-e stays open**.
* They **do not** yield an effective-date bracket for the `832000 → 920000` change; the `secCode`
  field is platform metadata (see above).
* They are **not** a statement about any vendor's price basis.
