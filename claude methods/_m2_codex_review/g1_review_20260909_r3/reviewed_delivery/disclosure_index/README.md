# Retained official disclosure-index responses (round 3)

Everything in this folder is a **raw response body from the official disclosure platform
`www.cninfo.com.cn`**, retained unmodified, plus two **derived** text renderings clearly
labelled as such. These responses are the evidence behind the completeness statements in
`../REPORT.md` §4 (G-e) and §6, and behind the narrowed code-change bracket for **G-g**.

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

Two behaviours of the endpoint are recorded because they shaped the method:

* **`column` is effectively ignored once `stock` carries a valid `orgId`.** `column=bse`,
  `column=third` and `column=neeq` each returned `totalRecordNum 0` for `920000`, while
  `column=sse` and `column=szse` both returned the issuer's full set (identical payloads).
  `column=sse` was used for both issuers. The zero results are an artefact of the parameter,
  **not** an absence of filings.
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

The `seDate` window `2024-08-01~2026-07-31` deliberately **over-covers** the task interval
`2024-08-13 … 2026-07-23` at both ends. The two tail queries were added only to locate the
2026 interim reports, which fall outside that window.

## Field meanings

* `announcementTime` — epoch milliseconds; rendered in the derived files as a UTC date. It is
  the platform's announcement date and is typically **one day before** the `finalpage/<date>/`
  publication path in `adjunctUrl`.
* `secCode` — the securities code **as stored with that announcement**. For this BSE issuer the
  stored value changes from `832000` to `920000` partway through the series, which is what
  narrows **G-g**.
* `announcementTitle` — the platform's title string.
* `adjunctUrl` — a path relative to `https://static.cninfo.com.cn/`.

## The two derived files

`derived_920000_announcement_titles.txt` and `derived_600011_announcement_titles.txt` are
**derived**, not primary: each line is `<mark> <UTC date> <secCode> | <title> | <adjunctUrl>`,
sorted, one line per announcement, with a leading `*` when the title contains any of
`分派 分红 派息 送股 转增 配股 股本 权益 利润分配 年度报告 半年度报告`. The JSON responses are
authoritative; if the two ever disagree, the JSON governs.

## What these responses do and do not establish

* They **do** establish what the official disclosure platform holds for these two issuers over
  the stated date ranges, completely paginated.
* They **do not** establish that no document exists on some other official host, and they are
  **not** a statement about any vendor's price basis. A title-keyword scan is a scan of titles,
  not of document bodies.
