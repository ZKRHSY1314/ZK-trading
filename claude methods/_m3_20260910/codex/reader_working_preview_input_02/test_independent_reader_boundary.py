"""Independent M3-02 configuration and connection-log checks; no database I/O.

All unauthorized work is intercepted with mocks before any file/database action.
These tests inspect the current reader API, not actual market data or reviews.
"""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('m3_reader_boundary_target', ROOT / 'backend/app/research/m3_frozen_reader.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class UnexpectedIO(RuntimeError):
    pass


class FakeConnection:
    def enable_load_extension(self, flag):
        assert flag is False

    def execute(self, *args):
        return self

    def fetchone(self):
        return (1,)

    def set_authorizer(self, callback):
        self.authorizer = callback

    def close(self):
        pass


class TestIndependentReaderBoundaries(unittest.TestCase):
    def test_real_reconcile_rejects_a_widened_price_cutoff_before_connecting(self):
        altered = replace(m.FROZEN_M2, price_max_date='2026-09-04')
        with mock.patch.object(m, 'load_json', return_value={'scopes': [], 'suspension_ledger': []}), \
             mock.patch.object(m, 'ReadOnlyStore', side_effect=UnexpectedIO('would open a store')) as store:
            try:
                m.reconcile(altered, m.ReadLog())
            except m.ReaderError:
                pass
            except UnexpectedIO:
                self.fail('Non-synthetic input widened the fixed development price cutoff and reached a database opener')
            self.assertEqual(store.call_count, 0)

    def test_real_run_rejects_caller_replaced_source_before_hashing_it(self):
        other = m.SourceSpec(str(ROOT / 'backend/unauthorized_fixture_source.sqlite3'), '0' * 64, kind='sqlite')
        altered = replace(m.FROZEN_M2, trading=other)
        with mock.patch.object(m, 'load_labels', return_value=None), \
             mock.patch.object(m, 'verify_source', side_effect=UnexpectedIO('would read a caller-chosen source')) as verify:
            try:
                m.run_development(ROOT / 'claude methods/_m3_20260910/claude_02/nonexistent_independent_test_output', altered)
            except m.ReaderError:
                pass
            except UnexpectedIO:
                self.fail('Caller-owned source/hash can reach verification without enforcing the fixed real-source allowlist')
            self.assertEqual(verify.call_count, 0)

    def test_store_construction_does_not_perform_file_io(self):
        with mock.patch.object(m, 'verify_source', side_effect=UnexpectedIO('constructor read')) as verify:
            try:
                m.ReadOnlyStore(m.FROZEN_M2.trading, m.ReadLog(), 'trading')
            except UnexpectedIO:
                self.fail('ReadOnlyStore constructor performs file reads before entering the explicit read scope')
            self.assertEqual(verify.call_count, 0)

    def test_nested_connections_keep_each_stores_own_after_hash(self):
        log = m.ReadLog()
        def verified(source):
            return dict(path=source.path, sha256=source.sha256, bytes=source.bytes)
        with mock.patch.object(m, 'verify_source', side_effect=verified), \
             mock.patch.object(m.sqlite3, 'connect', side_effect=lambda *args, **kwargs: FakeConnection()):
            with m.ReadOnlyStore(m.FROZEN_M2.trading, log, 'trading'), m.ReadOnlyStore(m.FROZEN_M2.history, log, 'history'):
                pass
        entries = {entry['role']: entry for entry in log.connections}
        self.assertEqual(len(entries), 2)
        for role, source in (('trading', m.FROZEN_M2.trading), ('history', m.FROZEN_M2.history)):
            with self.subTest(role=role):
                self.assertEqual(entries[role].get('sha256_after'), source.sha256,
                                 'Each connection receipt must bind its own post-close hash')


if __name__ == '__main__':
    unittest.main(verbosity=2)
