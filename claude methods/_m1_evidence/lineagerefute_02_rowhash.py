# Independent test: recompute market_history.daily_bars.row_hash from the CACHE row alone,
# using the seeder's documented algorithm. An exact match is proof of derivation.
import sqlite3, json, hashlib, math, random
from datetime import date
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
RULE_REGIME_BOUNDARY = date(2026, 7, 6)

def rebuild_from_cache(row):
    """Reimplementation of seed_market_history._normalize_bar + _row_hash (lines 1263-1330)."""
    try:
        trade_date = date.fromisoformat(str(row["trade_date"])[:10])
        prices = [float(row[f]) for f in ("open","high","low","close")]
    except (TypeError, ValueError):
        return None
    o,h,l,cl = prices
    if (not all(math.isfinite(v) for v in prices) or min(prices) < 0
        or h < max(o,cl,l) or l > min(o,cl)):
        return None
    volume = float(row["volume"]) if row["volume"] is not None else None
    amount = float(row["amount"]) if row["amount"] is not None else None
    vu = str(row["volume_unit"] or "unknown").lower()
    stable = {
        "symbol": str(row["symbol"]), "trade_date": trade_date.isoformat(),
        "adjustment_mode": "qfq", "open": o, "high": h, "low": l, "close": cl,
        "volume": volume, "amount": amount, "volume_unit": vu,
        "rule_regime": ("cn_a_share_2026_07_06_onward" if trade_date >= RULE_REGIME_BOUNDARY
                        else "cn_a_share_pre_2026_07_06"),
        "provider": str(row["source"]), "quality_status": "ready",
    }
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True,
                         separators=(",",":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

c = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
c.row_factory = sqlite3.Row
c.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")

# Stratified sample across the whole store: every 2000th row by rowid-free ordering.
SQL = """
SELECT h.symbol, h.trade_date, h.row_hash AS hist_hash, h.provider AS hist_provider,
       h.open AS h_o, h.high AS h_h, h.low AS h_l, h.close AS h_c,
       h.volume AS h_v, h.amount AS h_a, h.volume_unit AS h_vu,
       h.fetched_at, h.available_at,
       k.open, k.high, k.low, k.close, k.volume, k.amount,
       k.source, k.volume_unit, k.updated_at AS k_updated, k.created_at AS k_created
FROM main.daily_bars h
JOIN cache.daily_bar_cache k
  ON k.symbol = h.symbol AND k.trade_date = h.trade_date
WHERE h.symbol IN (SELECT symbol FROM (SELECT DISTINCT symbol FROM main.daily_bars) LIMIT -1 OFFSET 0)
  AND abs(random()) % 400 = 0
"""
rows = c.execute(SQL).fetchall()
print(f"sampled matched pairs: {len(rows):,}")

hash_match = hash_mismatch = unrebuildable = 0
val_identical = val_differs = 0
avail_eq_cache_updated = 0
mismatch_examples = []
for r in rows:
    rebuilt = rebuild_from_cache(r)
    if rebuilt is None:
        unrebuildable += 1
    elif rebuilt == r["hist_hash"]:
        hash_match += 1
    else:
        hash_mismatch += 1
        if len(mismatch_examples) < 5:
            mismatch_examples.append((r["symbol"], r["trade_date"], r["hist_hash"][:16], rebuilt[:16]))
    same = (r["h_o"]==r["open"] and r["h_h"]==r["high"] and r["h_l"]==r["low"]
            and r["h_c"]==r["close"] and r["h_v"]==r["volume"] and r["h_a"]==r["amount"]
            and r["h_vu"]==r["volume_unit"] and r["hist_provider"]==r["source"])
    val_identical += same; val_differs += (not same)
    src_upd = str(r["k_updated"] or r["k_created"] or "")
    if r["available_at"] == src_upd and r["fetched_at"] == src_upd:
        avail_eq_cache_updated += 1

n = len(rows)
print(f"\n--- row_hash reproduced from CACHE row alone ---")
print(f"  exact SHA256 match : {hash_match:,} / {n:,}  ({100*hash_match/n:.4f}%)")
print(f"  mismatch           : {hash_mismatch:,}")
print(f"  not rebuildable    : {unrebuildable:,}")
print(f"  mismatch examples  : {mismatch_examples}")
print(f"\n--- OHLCVA+provider+volume_unit byte-identical to cache ---")
print(f"  identical: {val_identical:,} / {n:,} ({100*val_identical/n:.4f}%)   differs: {val_differs:,}")
print(f"\n--- available_at & fetched_at == cache.updated_at(or created_at) ---")
print(f"  {avail_eq_cache_updated:,} / {n:,} ({100*avail_eq_cache_updated/n:.4f}%)")
