import json
from pathlib import Path
import tempfile
import unittest
from computer_runtime import prepare_runtime


class ComputerRuntimeTests(unittest.TestCase):
    def test_copied_project_creates_independent_credentials_and_history_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            legacy=base/'connection.json';legacy.write_text('{"token":"legacy-secret","unknown":123}')
            original=legacy.read_bytes()
            da,a,_,_=prepare_runtime(base,key='machine-a',name='A',caller='caller-a')
            db,b,_,_=prepare_runtime(base,key='machine-b',name='B',caller='caller-b')
            self.assertNotEqual(da,db)
            for key in ('computerId','token','certificateSha256'):self.assertNotEqual(a[key],b[key])
            self.assertEqual(original,legacy.read_bytes())
            self.assertEqual('caller-a',a['callerThreadId'])

    def test_restart_retains_identity_unknown_settings_and_updates_explicit_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,a,_,_=prepare_runtime(tmp,key='same',name='first',caller='caller')
            a['unknown']='retain';(path/'connection.json').write_text(json.dumps(a))
            _,b,_,_=prepare_runtime(tmp,key='same',name='renamed')
            for key in ('computerId','token','certificateSha256','callerThreadId'):self.assertEqual(a[key],b[key])
            self.assertEqual('retain',b['unknown']);self.assertEqual('renamed',b['computerName'])


if __name__=='__main__':unittest.main()
