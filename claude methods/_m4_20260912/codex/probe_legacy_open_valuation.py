"""Controlled probe of the exact legacy valuation method, with no app imports.

Extract the method AST unchanged; exercise it on in-memory fake ledger/frames.
This proves the method's same-day close dependence, not an end-to-end backtest.
"""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'backend/app/backtest/engine.py'
HERE = Path(__file__).resolve().parent


def main():
    source = SOURCE.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    pins = json.loads((HERE.parent / 'baseline/immutable_pins.json').read_bytes())
    assert digest == pins['backend/app/backtest/engine.py']
    tree = ast.parse(source)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'BacktestEngine')
    method = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == '_positions_value')
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), method], type_ignores=[])
    env = {}
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), 'exec'), env)
    ledger = SimpleNamespace(lots={'FIXTURE': [object()]}, quantity=lambda symbol: 100, average_cost=lambda symbol: 8)
    def value(close):
        frame = SimpleNamespace(index={'t'}, loc={'t': {'close': close}})
        return env['_positions_value'](None, ledger, {'FIXTURE': frame}, 't')
    a, b = value(10), value(20)
    assert (a, b) == (1000, 2000)
    assert SOURCE.read_bytes() == source
    result = {'passed': True, 'at_utc': datetime.now(timezone.utc).isoformat(),
              'source_sha256': digest, 'method_source_line': method.lineno,
              'exact_method_ast_used': True, 'legacy_engine_instantiated': False,
              'same_day_close_changed_only': [10, 20], 'position_values': [a, b],
              'finding': 'The exact valuation method uses same-day close. Its use in opening allocation is statically visible in engine.py; no end-to-end run is claimed.',
              'synthetic': True, 'source_unchanged': True,
              'sqlite_connections': 0, 'network_requests': 0}
    out = HERE / 'legacy_open_valuation_probe_01.json'
    assert not out.exists()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
