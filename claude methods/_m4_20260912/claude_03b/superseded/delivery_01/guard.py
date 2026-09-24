"""Process guard for M4-03B (claude_03b): audit hook + monkeypatches.

* Writes are allowed only under claude_03b/ (any other write is denied).
* Sockets, child processes and os.system are denied.
* ``sqlite3.connect`` is denied in ``synthetic`` mode.  In ``read_phase`` mode exactly the two allowed URIs
  (``file:<posix>?mode=ro&immutable=1`` of the pinned candidate stores) may be opened, each at most once; any other
  URI, path or flag is denied.  Connections are counted so the receipt can prove "exactly two".
* Guard self-check refusals are recorded separately (``SELF_CHECK_LOG``) from denials during real work (``DENIAL_LOG``).

The real ``sqlite3.connect`` is kept for the read phase; the monkeypatch routes through ``_connect_guard`` which
consults the allowlist, so the audit hook and the monkeypatch agree.
"""
from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ALLOWED_WRITE_ROOT = HERE.resolve()
MODE = {"value": "synthetic"}
ALLOWED_URIS: dict[str, int] = {}          # uri -> remaining allowed opens
CONNECTIONS: list[dict] = []               # actual connections opened in read phase
DENIAL_LOG: list[dict] = []
SELF_CHECK_LOG: list[dict] = []
_ACTIVE_LOG = DENIAL_LOG
_REAL_CONNECT = sqlite3.connect
_INSTALLED = {"value": False}


class GuardDenied(RuntimeError):
    pass


def _deny(kind: str, detail: str) -> None:
    _ACTIVE_LOG.append({"kind": kind, "detail": detail})
    raise GuardDenied(f"denied by M4-03B guard: {kind}: {detail}")


def uri_for(path: Path) -> str:
    return "file:" + quote(path.resolve().as_posix(), safe="/:") + "?mode=ro&immutable=1"


def _is_write_mode(mode, flags) -> bool:
    if isinstance(mode, str):
        return any(ch in mode for ch in "wax+")
    if isinstance(flags, int):
        return bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))
    return False


def _audit(event: str, args: tuple) -> None:
    if event == "open":
        path, mode, flags = args[0], args[1] if len(args) > 1 else None, args[2] if len(args) > 2 else None
        if _is_write_mode(mode, flags):
            try:
                target = Path(os.fsdecode(path)).resolve() if not isinstance(path, int) else None
            except Exception:  # noqa: BLE001
                target = None
            if target is None or ALLOWED_WRITE_ROOT not in (target, *target.parents):
                _deny("write_outside_claude_03b", f"{path!r} mode={mode!r} flags={flags!r}")
    elif event == "sqlite3.connect":
        uri = args[0] if args else None
        if MODE["value"] != "read_phase" or uri not in ALLOWED_URIS:
            _deny("sqlite_connect", f"mode={MODE['value']} target={uri!r}")
    elif event.startswith("socket.") and event != "socket.__new__":
        _deny("network", f"{event} {args[:1]!r}")
    elif event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.spawn", "os.fork"):
        _deny("subprocess", f"{event} {args[:1]!r}")


def _connect_guard(database, *args, **kwargs):
    if MODE["value"] != "read_phase" or database not in ALLOWED_URIS or ALLOWED_URIS[database] <= 0 or not kwargs.get("uri"):
        _deny("sqlite_connect", f"mode={MODE['value']} target={database!r} uri_flag={kwargs.get('uri')!r}")
    ALLOWED_URIS[database] -= 1
    conn = _REAL_CONNECT(database, *args, **kwargs)
    CONNECTIONS.append({"uri": database, "isolation_level": kwargs.get("isolation_level", "default")})
    return conn


def install() -> None:
    if _INSTALLED["value"]:
        return
    sqlite3.connect = _connect_guard  # type: ignore[assignment]

    class _DeniedSocket(socket.socket):
        def __init__(self, *a, **k):
            _deny("network", "socket.socket construction")

    socket.socket = _DeniedSocket  # type: ignore[misc,assignment]
    socket.create_connection = lambda *a, **k: _deny("network", "socket.create_connection")  # type: ignore[assignment]
    subprocess.Popen = lambda *a, **k: _deny("subprocess", "subprocess.Popen monkeypatch")  # type: ignore[assignment,misc]
    subprocess.run = lambda *a, **k: _deny("subprocess", "subprocess.run monkeypatch")  # type: ignore[assignment]
    os.system = lambda *a, **k: _deny("subprocess", "os.system monkeypatch")  # type: ignore[assignment]
    sys.dont_write_bytecode = True
    sys.addaudithook(_audit)
    _INSTALLED["value"] = True


def enter_read_phase(paths: list[Path]) -> list[str]:
    """Allow exactly one connection per given store path (immutable read-only URI) and return the allowed URIs."""
    ALLOWED_URIS.clear()
    for p in paths:
        ALLOWED_URIS[uri_for(p)] = 1
    MODE["value"] = "read_phase"
    return list(ALLOWED_URIS)


def leave_read_phase() -> None:
    MODE["value"] = "synthetic"
    ALLOWED_URIS.clear()


def self_check(evidence_dir: Path) -> dict:
    """Probe every guard; denials land in SELF_CHECK_LOG, never in DENIAL_LOG."""
    global _ACTIVE_LOG
    _ACTIVE_LOG = SELF_CHECK_LOG
    probe_path = HERE.parents[2] / "m4_03b_guard_probe_should_not_exist.tmp"
    probes = {"sqlite3.connect(':memory:')": lambda: sqlite3.connect(":memory:"),
              "sqlite3.connect(unlisted file uri)": lambda: sqlite3.connect("file:" + quote((HERE / "nope.sqlite3").as_posix(), safe="/:") + "?mode=ro&immutable=1", uri=True),
              "socket.socket": lambda: socket.socket(), "subprocess.run": lambda: subprocess.run([sys.executable, "-c", "pass"]),
              "os.system": lambda: os.system("echo probe"), "write_outside_claude_03b": lambda: open(probe_path, "w", encoding="utf-8")}
    outcome = {}
    try:
        for name, probe in probes.items():
            try:
                probe()
                outcome[name] = "NOT DENIED"
            except GuardDenied:
                outcome[name] = "denied"
            except Exception as exc:  # noqa: BLE001
                outcome[name] = f"other_error:{type(exc).__name__}:{exc}"
    finally:
        _ACTIVE_LOG = DENIAL_LOG
    outcome["probe_file_created"] = probe_path.exists()
    evidence_dir.mkdir(exist_ok=True)
    inside = evidence_dir / "guard_probe_inside_claude_03b.txt"
    inside.write_text("write inside claude_03b allowed\n", encoding="utf-8")
    outcome["write_inside_claude_03b"] = "allowed" if inside.exists() else "FAILED"
    outcome["self_check_denials"] = len(SELF_CHECK_LOG)
    return outcome


def receipt() -> dict:
    return {"mode": MODE["value"], "connections_opened": list(CONNECTIONS), "denials_during_work": list(DENIAL_LOG), "self_check_denials": list(SELF_CHECK_LOG),
            "bytecode_disabled": sys.dont_write_bytecode, "allowed_write_root": str(ALLOWED_WRITE_ROOT)}


__all__ = ["GuardDenied", "install", "enter_read_phase", "leave_read_phase", "self_check", "receipt", "uri_for", "CONNECTIONS", "DENIAL_LOG", "SELF_CHECK_LOG"]
