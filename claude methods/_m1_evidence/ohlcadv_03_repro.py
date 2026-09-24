# Pure-arithmetic reproduction of engine.py:231-233 and the sell path, no DB, no imports from app.
print("=== BUY PATH: engine.py lines 231-233 ===")
for sym, o, h, l, c in [("SH688089",0.0,0.0,0.0,20.75),("SH688143",0.0,0.0,0.0,27.53),("SH688173",0.0,0.0,0.0,11.80)]:
    slippage = 0.002
    alloc = 100000.0
    reference_price = float(o)
    buy_price = round(reference_price * (1 + slippage), 4)
    print(f"{sym}: open={o} -> reference_price={reference_price} -> buy_price={buy_price}")
    try:
        requested_qty = int(alloc / buy_price) // 100 * 100
        print("   requested_qty =", requested_qty)
    except ZeroDivisionError as e:
        print(f"   *** ZeroDivisionError: {e}  (raised BEFORE execution.decide is called)")
    # also with alloc == 0 (no cash) -- 0.0/0.0 still raises
    try:
        int(0.0 / buy_price)
    except ZeroDivisionError as e:
        print(f"   *** even with alloc=0.0: ZeroDivisionError: {e}")

print()
print("=== SELL PATH: does holding one of these into 2024-11-06 also crash? ===")
# _exit_decision stop_loss: float(bar['low']) <= stop  -> low=0.0 <= any positive stop -> True
# price = float(bar['open']) if float(bar['open']) <= stop else stop  -> open=0.0 -> sell_price 0.0
avg_cost, stop_loss_pct = 25.00, 8.0
stop = avg_cost * (1 - stop_loss_pct/100.0)
low, high, open_, prev_close, limit_pct = 0.0, 0.0, 0.0, 27.53, 20.0
triggered = low <= stop
sell_price = open_ if open_ <= stop else stop
print(f"stop={stop}; bar.low={low} -> stop_loss triggered={triggered}; sell_price={sell_price}")
# execution.decide: side=='sell' and high <= limit_down_price*1.01 -> rejected
limit_down_price = prev_close * (1 - limit_pct/100)
print(f"limit_down_price={limit_down_price}; bar.high={high} <= limit_down*1.01={limit_down_price*1.01} "
      f"-> rejected='one_word_limit_down': {high <= limit_down_price*1.01}")
print("=> the SELL at price 0.0 is BLOCKED by execution.decide (no crash, no 0-price fill).")
print("=> only the BUY path raises, and only when a strong-tier candidate is pending at that bar.")

print()
print("=== _positions_value uses close (nonzero) -> equity not corrupted ===")
print("   qty * float(df.loc[curr_dt]['close']) = qty * 27.53  (fine)")
