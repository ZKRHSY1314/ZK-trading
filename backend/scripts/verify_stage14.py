import asyncio
import json
from app.data.daily_bar_cache import DailyBarCacheService
from app.data.price_readiness import PriceReadinessService
from app.agent_control.paper_simulation_evaluation import PaperSimulationEvaluationService
from app.storage.sqlite_store import SQLiteStore
from app.config import settings

def main():
    store = SQLiteStore(settings.database_path)
    store.init()

    # Pre-check row counts
    initial_bars = store.fetch_one("SELECT COUNT(*) as c FROM daily_bar_cache")["c"]
    initial_scores = store.fetch_one("SELECT COUNT(*) as c FROM candidate_scores")["c"]
    
    print("Initial cache bars:", initial_bars)
    
    cache_svc = DailyBarCacheService(store)
    
    print("--- 1. Refreshing Daily Bars ---")
    res1 = cache_svc.refresh_bars(limit=5, days=10)
    print("Refresh 1 results:", json.dumps(res1, indent=2))
    
    bars_after_1 = store.fetch_one("SELECT COUNT(*) as c FROM daily_bar_cache")["c"]
    print("Bars after refresh 1:", bars_after_1)
    
    print("--- 2. Checking Coverage ---")
    coverage = cache_svc.get_coverage(limit=5)
    print("Coverage:", json.dumps(coverage, indent=2))
    
    if res1["results"]:
        symbol = res1["results"][0]["symbol"]
        print(f"--- 3. Inspecting bars for {symbol} ---")
        bars = cache_svc.get_bars(symbol, limit=2)
        for b in bars:
            print(b)
    
    print("--- 4. Refreshing Daily Bars Again ---")
    res2 = cache_svc.refresh_bars(limit=5, days=10)
    
    bars_after_2 = store.fetch_one("SELECT COUNT(*) as c FROM daily_bar_cache")["c"]
    print("Bars after refresh 2:", bars_after_2)
    assert bars_after_1 == bars_after_2, f"Duplication error! {bars_after_1} != {bars_after_2}"
    print("No duplication confirmed.")
    
    print("--- 5. Price Readiness ---")
    ready_svc = PriceReadinessService(store)
    res_ready = ready_svc.run_readiness_check(limit=5)
    print("Price Readiness Reports:", json.dumps(res_ready["reports"][:2], indent=2))
    
    print("--- 6. Paper Simulation Evaluation ---")
    eval_svc = PaperSimulationEvaluationService()
    res_eval = eval_svc.evaluate_recent(limit=5, horizon_days=5)
    print("Eval results:", json.dumps(res_eval, indent=2))
    
    print("--- 7. Confirming Candidate Scores Unchanged ---")
    final_scores = store.fetch_one("SELECT COUNT(*) as c FROM candidate_scores")["c"]
    assert initial_scores == final_scores, "Candidate scores changed!"
    print("Candidate scores unchanged.")

if __name__ == "__main__":
    main()
