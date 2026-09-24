"""Read-only inventory of a SQLite file for backup, recovery and rollback checks.

Records the file's SHA-256 and size, a hash of its schema, and a row count per
table, so the same file can be compared before and after a controlled start or
a restore. Opens the database with ``mode=ro`` and ``query_only``; never creates
a database, never writes to it, never imports the application.

    python backend/scripts/db_inventory.py --database trading_local.sqlite3 --label before

``--label`` writes ``<project-root>/logs/db_inventory_<label>.json`` (and nothing
else); without it the inventory is only printed. Run it with the stack stopped:
a live writer (or a WAL file) makes the byte hash a moving target.
Exit codes: 0 inventory produced, 2 unavailable/invalid input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABEL = re.compile(r'^[a-z0-9_-]{1,40}$')


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(path: Path, *, time_budget_seconds: float = 120.0) -> dict:
    path = Path(path)
    if not path.is_file():
        return {'status': 'unavailable', 'database': str(path), 'reason': 'not_a_file'}
    sidecars = {suffix: path.with_name(path.name + suffix).exists() for suffix in ('-wal', '-shm', '-journal')}
    before = file_sha256(path)
    connection = None
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
        connection.execute('PRAGMA query_only=ON')
        deadline = time.monotonic() + time_budget_seconds
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        schema_rows = connection.execute(
            "SELECT type, name, COALESCE(sql, '') FROM sqlite_master ORDER BY type, name").fetchall()
        tables = [name for kind, name, _ in schema_rows if kind == 'table' and not name.startswith('sqlite_')]
        counts = {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in tables}
        user_version = connection.execute('PRAGMA user_version').fetchone()[0]
    except sqlite3.Error as exc:
        return {'status': 'unavailable', 'database': str(path), 'reason': type(exc).__name__}
    finally:
        if connection is not None:
            connection.close()
    after = file_sha256(path)
    schema_hash = hashlib.sha256(json.dumps(schema_rows, ensure_ascii=False).encode('utf-8')).hexdigest()
    return {
        'schema_version': 'db_inventory.v1',
        'status': 'ok' if before == after else 'changed_during_inventory',
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'database': str(path),
        'size_bytes': path.stat().st_size,
        'sha256': after,
        'sidecar_files_present': sidecars,
        'schema_sha256': schema_hash,
        'user_version': user_version,
        'table_count': len(tables),
        'row_counts': counts,
        'read_only': True,
    }


def compare(before: dict, after: dict) -> dict:
    """Row-count and schema differences between two inventories of the same file."""
    tables = sorted(set(before.get('row_counts', {})) | set(after.get('row_counts', {})))
    changed = {name: {'before': before['row_counts'].get(name), 'after': after['row_counts'].get(name)}
               for name in tables
               if before.get('row_counts', {}).get(name) != after.get('row_counts', {}).get(name)}
    return {'bytes_identical': before.get('sha256') == after.get('sha256'),
            'schema_identical': before.get('schema_sha256') == after.get('schema_sha256'),
            'row_count_changes': changed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--label', help='write logs/db_inventory_<label>.json ([a-z0-9_-]{1,40})')
    parser.add_argument('--compare-with', type=Path, help='an earlier inventory JSON to diff against')
    args = parser.parse_args(argv)
    if args.label is not None and not LABEL.match(args.label):
        parser.error('--label must match [a-z0-9_-]{1,40}')
    result = inventory(args.database)
    if args.compare_with is not None:
        try:
            earlier = json.loads(args.compare_with.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            parser.error('--compare-with is not a readable inventory')
        result['comparison'] = compare(earlier, result)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.label is not None and result.get('status') in {'ok', 'changed_during_inventory'}:
        target = args.project_root.resolve() / 'logs' / f'db_inventory_{args.label}.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(encoded + '\n', encoding='utf-8')
        temporary.replace(target)
    print(encoded)
    return 0 if result.get('status') == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
