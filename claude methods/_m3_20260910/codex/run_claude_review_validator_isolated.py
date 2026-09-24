"""Execute the pinned delivered validator with its sole output redirected.

All source/input paths and validation logic are unchanged. Only the write to
Claude's validation_receipt.json is redirected into a new Codex-owned folder.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE.parent / 'claude_03/tools/validate_reviews.py'
ORIGINAL_RECEIPT = HERE.parent / 'claude_03/execution/validation_receipt.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    expected = sys.argv[1]
    out = Path(sys.argv[2]).resolve()
    assert sha(SOURCE) == expected
    assert sha(ROOT / 'backend/app/research/m3_labels.py') == 'e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393'
    assert out.parent == HERE and not out.exists()
    out.mkdir()
    original_receipt_sha = sha(ORIGINAL_RECEIPT)
    denied, redirected = [], []

    def audit(event, args):
        bad = event == 'sqlite3.connect' or event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.startfile'}
        if event == 'open':
            path, mode, flags = args
            writing = isinstance(mode, str) and any(c in mode for c in 'wax+') or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
            if writing and not (isinstance(path, (str, os.PathLike)) and Path(path).resolve().is_relative_to(out)):
                bad = True
        if bad:
            denied.append(event)
            raise PermissionError(event)

    sys.addaudithook(audit)
    sys.dont_write_bytecode = True
    original_write = Path.write_bytes

    def redirect_write(path, value):
        if path.resolve() == ORIGINAL_RECEIPT.resolve():
            redirected.append(str(path))
            return original_write(out / 'validation_receipt.json', value)
        return original_write(path, value)

    source_copy = SOURCE.read_bytes()
    buffer = io.StringIO()
    Path.write_bytes = redirect_write
    try:
        spec = importlib.util.spec_from_file_location('claude_review_validator_actual', SOURCE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            spec.loader.exec_module(module)
            exit_code = module.main()
    finally:
        Path.write_bytes = original_write
    assert sha(SOURCE) == expected and sha(ORIGINAL_RECEIPT) == original_receipt_sha
    result = {'passed': exit_code == 0 and not denied and len(redirected) == 1,
              'at_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': exit_code,
              'original_validator_sha256': expected, 'original_receipt_preserved_sha256': original_receipt_sha,
              'only_mutation_redirection': redirected, 'logic_or_input_overrides': False,
              'sqlite_connections': 0, 'network_requests': 0, 'denied_events': denied,
              'review_judgments_generated': 0, 'producer_sha256': sha(Path(__file__))}
    (out / 'validator_source.py').write_bytes(source_copy)
    (out / 'stdout.txt').write_text(buffer.getvalue(), encoding='utf-8')
    (out / 'execution.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    assert result['passed'], buffer.getvalue()


if __name__ == '__main__':
    main()
