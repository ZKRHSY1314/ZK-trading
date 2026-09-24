"""Restart budget for scripts/ensure_stack.ps1: stop restart storms, fail closed.

ensure_stack.ps1 is meant to run every few minutes from a scheduled task. A
component that dies on every start (a held lock, a broken dependency, a bad
upstream) would otherwise trigger a whole-stack stop/start on every run. This
helper keeps a small attempt log in ``<root>/logs/ensure_stack_restarts.json``
and answers one question before ensure_stack stops anything: may it restart now?

* ``decide``  prints ``{"action": "restart" | "suppress", ...}``; exit 0 when a
              restart is allowed, 3 when it is suppressed. It never writes.
* ``record``  appends one attempt outcome (``started`` / ``failed``).

An unreadable, oversized or malformed log, or one holding entries dated in the
future, suppresses restarts (exit 3) instead of being treated as empty: an
operator reviews and removes the file. A failed upstream *cycle* never reaches
this helper; ensure_stack only restarts on a dead/unverified process or a
configuration mismatch, and a fresh heartbeat with a failed status passes.

Stdlib only; writes nothing except the attempt log.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 'ensure_stack_restarts.v1'
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAX_RESTARTS = 3
DEFAULT_WINDOW_SECONDS = 3600
MAX_ENTRIES = 50
CLOCK_SKEW_SECONDS = 60
OUTCOMES = ('started', 'failed')
EXIT_ALLOWED = 0
EXIT_SUPPRESSED = 3


def _parse_time(value) -> datetime:
    stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('naive timestamp')
    return stamp


def load_state(path: Path) -> tuple[list[dict] | None, str | None]:
    """Return (attempts, problem). A problem means: do not trust, do not restart."""
    if not path.exists():
        return [], None
    try:
        if path.stat().st_size > 256_000:
            return None, 'state_file_oversized'
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None, 'state_file_unreadable'
    if not isinstance(payload, dict) or payload.get('schema_version') != SCHEMA_VERSION:
        return None, 'state_file_schema_mismatch'
    attempts = payload.get('attempts')
    if not isinstance(attempts, list):
        return None, 'state_file_malformed'
    for attempt in attempts:
        if not isinstance(attempt, dict) or attempt.get('outcome') not in OUTCOMES:
            return None, 'state_file_malformed'
        try:
            _parse_time(attempt.get('at'))
        except (TypeError, ValueError):
            return None, 'state_file_malformed'
    return attempts, None


def decide(path: Path, now: datetime, *, max_restarts: int = DEFAULT_MAX_RESTARTS,
           window_seconds: int = DEFAULT_WINDOW_SECONDS) -> dict:
    attempts, problem = load_state(path)
    base = {'schema_version': 'ensure_stack_restart_decision.v1', 'checked_at': now.isoformat(),
            'max_restarts': max_restarts, 'window_seconds': window_seconds, 'state_file': str(path)}
    if problem:
        return {**base, 'action': 'suppress', 'reason': problem, 'attempts_in_window': None}
    window_start = now - timedelta(seconds=window_seconds)
    stamps = [_parse_time(attempt['at']) for attempt in attempts]
    if any(stamp > now + timedelta(seconds=CLOCK_SKEW_SECONDS) for stamp in stamps):
        return {**base, 'action': 'suppress', 'reason': 'state_file_future_timestamp',
                'attempts_in_window': None}
    recent = sorted(stamp for stamp in stamps if stamp >= window_start)
    if len(recent) >= max_restarts:
        next_allowed = recent[len(recent) - max_restarts] + timedelta(seconds=window_seconds)
        return {**base, 'action': 'suppress', 'reason': 'restart_budget_exhausted',
                'attempts_in_window': len(recent), 'next_allowed_at': next_allowed.isoformat()}
    return {**base, 'action': 'restart', 'reason': None, 'attempts_in_window': len(recent)}


def record(path: Path, now: datetime, outcome: str, *, profile: str | None = None) -> dict:
    if outcome not in OUTCOMES:
        raise ValueError(f'unknown outcome: {outcome!r}')
    attempts, problem = load_state(path)
    if problem:
        # Never silently replace a log we could not read; the operator must look at it.
        raise RuntimeError(problem)
    attempts = [*attempts, {'at': now.isoformat(), 'outcome': outcome, 'profile': profile}][-MAX_ENTRIES:]
    payload = {'schema_version': SCHEMA_VERSION, 'attempts': attempts}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('decide', 'record'))
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--outcome', choices=OUTCOMES)
    parser.add_argument('--profile')
    parser.add_argument('--max-restarts', type=int, default=DEFAULT_MAX_RESTARTS)
    parser.add_argument('--window-seconds', type=int, default=DEFAULT_WINDOW_SECONDS)
    args = parser.parse_args(argv)
    if args.max_restarts < 1 or args.window_seconds < 60:
        parser.error('--max-restarts must be >= 1 and --window-seconds >= 60')
    path = args.project_root.resolve() / 'logs' / 'ensure_stack_restarts.json'
    now = datetime.now(timezone.utc)
    if args.command == 'record':
        if not args.outcome:
            parser.error('record requires --outcome')
        try:
            record(path, now, args.outcome, profile=args.profile)
        except RuntimeError as exc:
            print(json.dumps({'recorded': False, 'reason': str(exc)}))
            return EXIT_SUPPRESSED
        print(json.dumps({'recorded': True, 'outcome': args.outcome}))
        return EXIT_ALLOWED
    decision = decide(path, now, max_restarts=args.max_restarts, window_seconds=args.window_seconds)
    print(json.dumps(decision))
    return EXIT_ALLOWED if decision['action'] == 'restart' else EXIT_SUPPRESSED


if __name__ == '__main__':
    raise SystemExit(main())
