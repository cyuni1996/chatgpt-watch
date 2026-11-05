import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import setup_watch as setup
import download_release as release


class SetupTests(unittest.TestCase):
    def test_device_selection_excludes_offline_and_unauthorized(self):
        output = 'List of devices attached\none\tdevice\ntwo\toffline\nthree\tunauthorized\n'
        self.assertEqual(['one'], setup.connected_devices(output))

    def test_multiple_devices_require_explicit_selection(self):
        with patch.object(setup.subprocess, 'run') as run:
            run.return_value.stdout = 'a\tdevice\nb\tdevice\n'
            with self.assertRaises(ValueError): setup.select_device('adb')
            self.assertEqual('b', setup.select_device('adb', 'b'))
            with self.assertRaises(ValueError): setup.select_device('adb', 'untrusted')

    def test_install_only_attempts_nondestructive_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            apk = Path(tmp) / 'sample.apk'; apk.write_bytes(b'PK-demo')
            with patch.object(setup, 'checked') as call:
                setup.install('adb', 'watch', apk)
                self.assertEqual(['adb', '-s', 'watch', 'install', '-r', apk.resolve()], call.call_args.args[0])
                self.assertNotIn('uninstall', call.call_args.args[0])
            with self.assertRaises(ValueError): setup.install('adb', 'watch', Path(tmp) / 'missing.apk')

    def test_start_rejects_fake_caller_before_running_any_command(self):
        with patch.object(setup.os, 'name', 'nt'), patch.object(setup, 'checked') as call:
            with self.assertRaises(ValueError): setup.start('made-up')
            call.assert_not_called()

    def test_sdk_environment_has_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(Path(tmp), setup.sdk_root({'ANDROID_HOME': tmp}))

    def test_checksum_requires_one_exact_asset_name(self):
        digest = 'ab' * 32
        self.assertEqual(digest, release.expected_hash(digest + '  sample.apk', 'sample.apk'))
        for contents in ['', digest + '  other.apk', (digest + ' sample.apk\n') * 2]:
            with self.assertRaises(ValueError): release.expected_hash(contents, 'sample.apk')

    def test_download_rejects_wrong_hash_without_creating_apk(self):
        assets = [{'name': name, 'browser_download_url': 'https://github.com/' + release.REPOSITORY + '/releases/download/v0.13.0/' + name}
                  for name in [release.APK_NAME, 'SHA256SUMS']]
        meta = json.dumps({'tag_name': 'v0.13.0', 'assets': assets}).encode()
        with tempfile.TemporaryDirectory() as tmp, patch.object(release, 'read_url') as read:
            read.side_effect = [meta, ('ab' * 32 + '  ' + release.APK_NAME).encode(), b'PK-wrong']
            with self.assertRaises(ValueError): release.download(directory=tmp)
            self.assertEqual([], list(Path(tmp).iterdir()))

    def test_successful_download_is_atomic_and_cached(self):
        import hashlib
        content = b'PK-fictional-APK'
        checksums = (hashlib.sha256(content).hexdigest() + '  ' + release.APK_NAME).encode()
        meta = json.dumps({'tag_name': 'v0.13.0', 'assets': [
            {'name': name, 'browser_download_url': 'https://github.com/' + release.REPOSITORY + '/releases/download/v0.13.0/' + name}
            for name in [release.APK_NAME, 'SHA256SUMS']]}).encode()
        with tempfile.TemporaryDirectory() as tmp, patch.object(release, 'read_url') as read:
            read.side_effect = [meta, checksums, content, meta, checksums]
            first = release.download(directory=tmp)
            self.assertEqual(content, first.read_bytes())
            self.assertEqual(first, release.download(directory=tmp))
            self.assertEqual(5, read.call_count)

    def test_external_asset_and_invalid_tag_are_rejected(self):
        with patch.object(release, 'read_url') as read:
            with self.assertRaises(ValueError): release.download('../main')
            read.assert_not_called()
            read.return_value = json.dumps({'tag_name': 'v0.13.0', 'assets': [
                {'name': 'SHA256SUMS', 'browser_download_url': 'https://example.com/secret'}]}).encode()
            with self.assertRaises(ValueError): release.download()


if __name__ == '__main__':
    unittest.main()
