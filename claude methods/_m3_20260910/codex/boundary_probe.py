"""Synthetic execution-boundary probe. Does not touch any production path."""
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import unittest


class BoundaryProbe(unittest.TestCase):
    def test_real_side_effect_entrypoints_rejected(self):
        # Even if the harness were defective these targets cannot alter a pre-existing
        # dataset: memory-only SQLite, an unconnected socket, an inert child, and a
        # new synthetic filename. Never test file-write denial on a frozen artifact.
        marker = Path(__file__).with_name('boundary_probe_should_not_exist.txt')
        self.assertFalse(marker.exists())
        actions = {
            'sqlite': lambda: sqlite3.connect(':memory:'),
            'socket': lambda: socket.socket(),
            'subprocess': lambda: subprocess.Popen([sys.executable, '-B', '-c', 'pass']),
            'write_outside': lambda: marker.write_text('synthetic boundary probe', encoding='utf-8'),
        }
        for name, action in actions.items():
            with self.subTest(name=name), self.assertRaises(PermissionError):
                action()
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
