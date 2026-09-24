import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile

HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('collect_remaining',HERE/'collect_remaining.py')
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)

class TestRemaining(unittest.TestCase):
    def test_new_guard_changes_only_past_history_operator_time_policy(self):
        old=(HERE/'preflight.ps1').read_text(encoding='utf-8-sig')
        new=(HERE/'preflight_remaining.ps1').read_text(encoding='utf-8-sig')
        line="if ($tod -ge [TimeSpan]::Parse('09:15:00') -and $tod -le [TimeSpan]::Parse('15:30:00')) { $problems += 'outside_operator_window' }"
        self.assertEqual(old.count(line),1)
        self.assertEqual(new,old.replace(line,'# Remaining pilot policy: fixed completed-history end 2026-09-04; no current-session bars accepted.'))
        self.assertEqual(c.base.sha((HERE/'preflight_remaining.ps1').read_bytes()),c.REMAINING_PREFLIGHT_PIN)

    def test_exact_frozen_partition_and_request_bounds(self):
        p=c.plan();jobs=p['jobs']
        self.assertEqual(len(jobs),48)
        self.assertEqual(len({j['symbol'] for j in jobs}|set(p['reused_qualification_jobs'])),52)
        self.assertFalse({j['symbol'] for j in jobs}&set(p['reused_qualification_jobs']))
        for j in jobs:
            self.assertEqual(j['payload']['security'],{'hostFullCode':j['host_full_code']})
            self.assertNotIn('codes',j['payload'])
            self.assertEqual(j['payload']['adjustment'],0)
            self.assertEqual(j['payload']['period'],7)
        self.assertFalse(p['live_trading']);self.assertFalse(p['database_access'])

    def test_wrong_plan_pin_no_identity_or_token_or_http(self):
        with patch.object(c,'preflight') as pre,patch.object(c.base,'credentials') as secret,patch.object(c.base,'fetch') as http:
            with self.assertRaises(c.base.StopCapture):c.capture('0'*64)
            pre.assert_not_called();secret.assert_not_called();http.assert_not_called()

    def test_identity_failure_no_credentials_or_http(self):
        p=c.plan();pin=c.base.sha(json.dumps(p,sort_keys=True,allow_nan=False).encode())
        with patch.object(c,'preflight',side_effect=c.base.StopCapture('identity')),patch.object(c.base,'credentials') as secret,patch.object(c.base,'fetch') as http:
            with self.assertRaises(c.base.StopCapture):c.capture(pin)
            secret.assert_not_called();http.assert_not_called()

    def test_existing_claim_cannot_resume(self):
        p=c.plan();pin=c.base.sha(json.dumps(p,sort_keys=True,allow_nan=False).encode())
        with tempfile.TemporaryDirectory() as d:
            here=Path(d);(here/'remaining_capture').mkdir()
            with patch.object(c,'HERE',here),patch.object(c,'plan',return_value=p),patch.object(c,'preflight',return_value={}),patch.object(c.base,'credentials') as secret,patch.object(c.base,'fetch') as http:
                with self.assertRaises(FileExistsError):c.capture(pin)
                secret.assert_not_called();http.assert_not_called()

if __name__=='__main__':unittest.main()
