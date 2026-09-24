"""R02 - read-only schema and count inventory of the two published candidate stores.

Opens ONLY the two candidate SQLite files under the published run directory, with
mode=ro URIs and PRAGMA query_only=ON. Nothing else is opened. Writes r02_db_schema.json.
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent / "_m2_codex_implementation_20260910"
RUN_ID = "ths_v2_20260910_041710_97ef9c09"
RUN = PHASE / "staging_runs" / RUN_ID / f"run_{RUN_ID}"
STORES = {"trading": RUN / "trading.sqlite3", "history": RUN / "history.sqlite3"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ro(path):
    conn = sqlite3.connect("file:" + quote(Path(path).as_posix(), safe="/:") + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hv(v):
    return hashlib.sha256(canonical(v).encode("utf-8")).hexdigest()


def main():
    out = {"run_id": RUN_ID, "stores": {}, "opened": [], "candidate_fingerprint_recomputed": None}
    files = {p.name: sha(p) for p in [STORES["trading"], STORES["history"], RUN / "candidate.json", RUN / "contract_v2.json"]}
    out["file_sha256"] = files
    out["candidate_fingerprint_recomputed"] = hv(files)
    pointer = json.load(open(PHASE / "staging_runs" / RUN_ID / "CURRENT.json", encoding="utf-8"))
    out["candidate_fingerprint_pointer"] = pointer["candidate_fingerprint"]
    out["candidate_fingerprint_match"] = out["candidate_fingerprint_recomputed"] == pointer["candidate_fingerprint"]
    out["pointer_sha256"] = sha(PHASE / "staging_runs" / RUN_ID / "CURRENT.json")
    for role, path in STORES.items():
        conn = ro(path)
        out["opened"].append(str(path))
        try:
            s = {"path": str(path), "bytes": path.stat().st_size, "sha256": files[path.name]}
            s["user_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
            s["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchall()
            s["foreign_key_check"] = conn.execute("PRAGMA foreign_key_check").fetchall()
            s["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
            objs = conn.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','view','index') ORDER BY type,name").fetchall()
            s["objects"] = [{"type": t, "name": n, "sql": q} for t, n, q in objs]
            s["counts"] = {}
            for t, n, _ in objs:
                if t in ("table", "view") and not n.startswith("sqlite_"):
                    s["counts"][n] = conn.execute(f"SELECT COUNT(*) FROM \"{n}\"").fetchone()[0]
            out["stores"][role] = s
        finally:
            conn.close()
    json.dump(out, open(HERE / "r02_db_schema.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    for role, s in out["stores"].items():
        print(f"== {role}: {s['bytes']} bytes user_version={s['user_version']} integrity={s['integrity_check']} fk={s['foreign_key_check']} journal={s['journal_mode']}")
        for o in s["objects"]:
            print(f"   {o['type']:5} {o['name']}")
        print("   counts:", s["counts"])
    print("candidate_fingerprint recomputed:", out["candidate_fingerprint_recomputed"])
    print("candidate_fingerprint pointer   :", out["candidate_fingerprint_pointer"], "match:", out["candidate_fingerprint_match"])
    print("pointer sha256:", out["pointer_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
