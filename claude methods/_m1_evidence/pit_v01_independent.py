import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")
q = lambda s,p=(): list(c.execute(s,p))

print("### 0. SANITY: universe of stock decisions")
print("A0 pairs:", q("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions WHERE scope='stock')"))
print("A1 distinct subjects:", q("SELECT COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock'"))
print("A2 distinct decision_ids:", q("SELECT COUNT(DISTINCT decision_id) FROM forecast_decisions WHERE scope='stock'"))
print("A3 cutoff range:", q("SELECT MIN(decision_cutoff),MAX(decision_cutoff) FROM forecast_decisions WHERE scope='stock'"))
print("A4 one cutoff per decision_id?:",
      q("SELECT COUNT(*) FROM (SELECT decision_id FROM forecast_decisions WHERE scope='stock' GROUP BY decision_id HAVING COUNT(DISTINCT decision_cutoff)>1)"))

print("\n### 1. Is 'subject' a stock? index / non-stock contamination")
print("B0 subject prefixes:", q("SELECT substr(subject,1,2) p, COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock' GROUP BY 1"))
print("B1 subjects w/ index-like board codes (SH000*/SZ399*/SH880*/BJ*):",
      q("""SELECT COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock'
           AND (subject LIKE 'SH000%' OR subject LIKE 'SZ399%' OR subject LIKE 'SH880%' OR subject LIKE 'SZ899%')"""))
print("B2 subject codes distinct list sample:", [r[0] for r in q("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock' ORDER BY subject LIMIT 12")])

print("\n### 2. Independent recompute: normalized-timestamp join (NOT their raw string compare)")
# normalize: cutoff 'YYYY-MM-DDTHH:MM:SS.ffffffZ' -> 'YYYY-MM-DD HH:MM:SS' to match created_at
c.executescript("")  # no-op; keep read-only
base = """
WITH d AS (
  SELECT DISTINCT decision_id, subject,
         decision_cutoff AS raw_cut,
         substr(decision_cutoff,1,10) AS cut_date,
         replace(substr(decision_cutoff,1,19),'T',' ') AS cut_ts
  FROM forecast_decisions WHERE scope='stock'
),
b AS (
  SELECT symbol, trade_date, created_at
  FROM daily_bar_cache
  WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
)
"""
print("C0 total (pair,bar) joins with trade_date<=cut_date:",
      q(base+"SELECT COUNT(*) FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date"))
print("C1 (pair,bar) LATE-ARRIVAL joins  (created_at>cut_ts, normalized):",
      q(base+"SELECT COUNT(*) FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date AND b.created_at>d.cut_ts"))
print("C2 (pair,bar) LATE-ARRIVAL joins  (their RAW string compare created_at>raw_cut):",
      q(base+"SELECT COUNT(*) FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date AND b.created_at>d.raw_cut"))
print("C3 DISTINCT bar-rows implicated (normalized):",
      q(base+"SELECT COUNT(*) FROM (SELECT DISTINCT b.symbol,b.trade_date FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date AND b.created_at>d.cut_ts)"))
print("C4 DISTINCT bar-rows implicated (their raw compare):",
      q(base+"SELECT COUNT(*) FROM (SELECT DISTINCT b.symbol,b.trade_date FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date AND b.created_at>d.raw_cut)"))
print("C5 total bar-rows for the 90 subjects (all dates):",
      q("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN (SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock')"))
print("C6 PAIRS flagged (normalized) / total:",
      q(base+"SELECT COUNT(*) FROM (SELECT DISTINCT d.decision_id,d.subject FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date AND b.created_at>d.cut_ts)"))
print("C7 PAIRS flagged (their raw compare) / total:",
      q(base+"SELECT COUNT(*) FROM (SELECT DISTINCT d.decision_id,d.subject FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date AND b.created_at>d.raw_cut)"))
print("C8 DISTINCT SUBJECTS flagged (normalized):",
      q(base+"SELECT COUNT(DISTINCT d.subject) FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date AND b.created_at>d.cut_ts"))
print("C9 DISTINCT DECISION_IDS flagged (normalized):",
      q(base+"SELECT COUNT(DISTINCT d.decision_id) FROM d JOIN b ON b.symbol=d.subject AND b.trade_date<=d.cut_date AND b.created_at>d.cut_ts"))

print("\n### 3. Forward-bar look-ahead (their probe B) recomputed independently")
print("D0 (pair,bar) where trade_date>cut_date AND created_at<=cut_ts:",
      q(base+"SELECT COUNT(*) FROM d JOIN b ON b.symbol=d.subject AND b.trade_date>d.cut_date AND b.created_at<=d.cut_ts"))
print("D1 (pair,bar) where trade_date>cut_date at all (present now):",
      q(base+"SELECT COUNT(*) FROM d JOIN b ON b.symbol=d.subject AND b.trade_date>d.cut_date"))
c.close()
