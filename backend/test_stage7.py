import json
import time
from datetime import datetime, timedelta
from app.storage.sqlite_store import SQLiteStore
from app.config import settings
from app.agent_control.outcome_labeling import OutcomeLabelingService

store = SQLiteStore(settings.database_path)
store.init()

with store.connect() as conn:
    # insert fake learning samples
    conn.execute("DELETE FROM agent_learning_samples")
    conn.execute("DELETE FROM agent_learning_outcomes")

    # Sample 1: old symbol sample (should get labeled)
    # Assume 000001 (Ping An Bank) - should have data
    conn.execute("""
        INSERT INTO agent_learning_samples (source_task_id, sample_type, symbol, label, created_at)
        VALUES (1, 'decision', 'SZ000001', 'buy', date('now', '-10 days'))
    """)
    s1_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Sample 2: system-health sample (old, should be stable)
    conn.execute("""
        INSERT INTO agent_learning_samples (source_task_id, sample_type, symbol, label, created_at)
        VALUES (2, 'system_health', '__no_symbol__', 'good', date('now', '-10 days'))
    """)
    s2_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    # Sample 3: recent symbol sample (should be pending)
    conn.execute("""
        INSERT INTO agent_learning_samples (source_task_id, sample_type, symbol, label, created_at)
        VALUES (3, 'decision', 'SZ000001', 'buy', date('now', '-1 days'))
    """)
    s3_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

svc = OutcomeLabelingService()

print("Labeling symbol sample...")
out1 = svc.label_sample(s1_id, horizon_days=5)
print(json.dumps(out1, indent=2, ensure_ascii=False))

print("Labeling system-health sample...")
out2 = svc.label_sample(s2_id, horizon_days=5)
print(json.dumps(out2, indent=2, ensure_ascii=False))

print("Labeling recent samples (idempotency check)...")
res = svc.label_recent(limit=10, horizon_days=5)
print(json.dumps(res, indent=2, ensure_ascii=False))

print("Summary...")
summary = svc.summary()
print(summary.model_dump_json(indent=2))

