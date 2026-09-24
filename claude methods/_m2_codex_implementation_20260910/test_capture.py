import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ths_m2_capture',HERE/'capture.py')
c=importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

def plan():
    entries=[('SH000300','USZI399300',0),('SH000001','USHI1A0001',0)]
    entries += [(s,h,a) for s,h in [('SH600011','USHA600011'),('BJ920000','USTM920000')] for a in (0,1,2)]
    return {'kind':'qualification','max_attempts':8,'live_trading':False,'database_access':False,
        'authorization':'User instructed Codex to continue until M2 completion; isolated market evidence only.',
        'jobs':[{'id':i,'symbol':s,'host_full_code':h,'payload':{'market':1,'security':{'hostFullCode':h},
        'startTimeUtc':'2022-08-23T16:00:00Z','endTimeUtc':'2026-09-04T15:59:59.999Z','limit':5000,
        'fields':['full_code','security_name','open','high','low','latest','transaction_volume','transaction_amount','date_time'],
        'period':7,'adjustment':a}} for i,(s,h,a) in enumerate(entries,1)]}

class TestCapture(unittest.TestCase):
    def write_plan(self,d,p):
        path=Path(d)/'plan.json'
        raw=json.dumps(p).encode()
        path.write_bytes(raw)
        return path,hashlib.sha256(raw).hexdigest()

    def test_fixed_plan_eight_single_native_identifiers(self):
        with tempfile.TemporaryDirectory() as d:
            path,pin=self.write_plan(d,plan())
            self.assertEqual(len(c.read_plan(path,pin)['jobs']),8)

    def test_mutation_of_each_request_boundary_rejected(self):
        changes=[lambda p:p['jobs'][0]['payload'].update(codes=['000300']),
          lambda p:p['jobs'][0]['payload'].update(period=1),
          lambda p:p['jobs'][0]['payload'].update(adjustment=2),
          lambda p:p['jobs'][0]['payload']['security'].update(code='000300'),
          lambda p:p['jobs'][0].update(symbol='SH600000'),
          lambda p:p['jobs'][0]['payload'].update(market=True),
          lambda p:p['jobs'][0]['payload'].update(adjustment=False),
          lambda p:p['jobs'][0].update(id=True),
          lambda p:p.update(live_trading=True),lambda p:p.update(database_access=True),
          lambda p:p.update(max_attempts=9),lambda p:p['jobs'].pop()]
        for mutate in changes:
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as d:
                p=plan();mutate(p)
                path,pin=self.write_plan(d,p)
                with self.assertRaises(c.StopCapture):c.read_plan(path,pin)

    def test_plan_hash_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path,_=self.write_plan(d,plan())
            with self.assertRaises(c.StopCapture):c.read_plan(path,'0'*64)

    def test_failed_preflight_never_reads_credentials_or_network(self):
        with tempfile.TemporaryDirectory() as d:
            path,pin=self.write_plan(d,plan())
            with patch.object(c,'preflight',side_effect=c.StopCapture('identity')),patch.object(c,'credentials') as secret,patch.object(c,'fetch') as network:
                with self.assertRaises(c.StopCapture):c.capture(path,pin)
                secret.assert_not_called();network.assert_not_called()

    def test_generation_change_no_config_read(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);(home/'runtime').mkdir();(home/'runtime/endpoint.json').write_text('{}')
            with patch.object(c,'HOME',home),patch.object(Path,'read_bytes',autospec=True,return_value=b'{}') as reader:
                with self.assertRaises(c.StopCapture):c.credentials({'endpoint_sha256':'0'*64})
                self.assertEqual(reader.call_count,1)
                self.assertEqual(reader.call_args.args[0].name,'endpoint.json')

    def test_trading_flags_and_token_redaction(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);(home/'runtime').mkdir();(home/'runtime/endpoint.json').write_text('{}')
            secret='a'*64
            (home/'config.json').write_text(json.dumps({'localAccessToken':secret,'enableTradeTools':True,'enableAutomatedTradeApi':False,'preferredPort':17180}))
            with patch.object(c,'HOME',home):
                with self.assertRaises(c.StopCapture) as result:c.credentials({'endpoint_sha256':c.sha(b'{}')})
                self.assertNotIn(secret,str(result.exception))

    def test_one_shot_claim_no_token_or_network(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'qualification_capture').mkdir()
            path,pin=self.write_plan(d,plan())
            with patch.object(c,'HERE',root),patch.object(c,'preflight',return_value={}),patch.object(c,'credentials') as secret,patch.object(c,'fetch') as network:
                with self.assertRaises(FileExistsError):c.capture(path,pin)
                secret.assert_not_called();network.assert_not_called()

if __name__=='__main__':unittest.main()
