import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_public_tree as check


class PublicTreeTests(unittest.TestCase):
    def test_real_secret_formats_detected_without_returning_the_value(self):
        value = 'ghp_' + 'A' * 36
        hits = check.findings('example.py', ('TOKEN="' + value + '"').encode())
        self.assertIn(('github-token', 1), hits)
        self.assertNotIn(value, repr(hits))

    def test_runtime_file_rejected_even_when_content_is_empty(self):
        self.assertIn(('private-file', 0), check.findings('.local/computers/example/connection.json', b'{}'))
        self.assertIn(('private-file', 0), check.findings('release.jks', b''))

    def test_private_identifiers_match_text_and_binary_case_insensitively(self):
        self.assertIn(('private-identifier', 1), check.findings('README.md', b'Private-PC', ['private-pc']))
        self.assertIn(('private-identifier', 0), check.findings('image.png', b'\0Private-PC', ['private-pc']))

    def test_examples_and_reviewed_assets_are_allowed(self):
        self.assertEqual([], check.findings('README.md', b'https://chat.example.com C:/path/to/sdk'))
        self.assertEqual([], check.findings('app/src/main/res/drawable-nodpi/dragon_chat.webp', b'RIFF\0WEBP'))
        self.assertIn(('unreviewed-binary', 0), check.findings('private.png', b'PNG\0'))

    def test_tracked_mode_reads_staged_blob_not_worktree(self):
        calls = []
        def fake_git(*args):
            calls.append(args)
            return b'100644 blob-id 0\tREADME.md\0' if args[0] == 'ls-files' else b'staged content'
        with patch.object(check, 'git', fake_git):
            self.assertEqual([('README.md', b'staged content')], list(check.entries(tracked=True)))
        self.assertIn(('cat-file', 'blob', 'blob-id'), calls)

    def test_only_exact_synthetic_url_in_named_test_is_exempted(self):
        fake = ('https://' + 'user:pass' + '@watch.example.com').encode()
        self.assertEqual([], check.findings('bridge/test_connections.py', fake))
        other = ('https://' + 'real-user:real-password' + '@example.com').encode()
        self.assertIn(('url-password', 1), check.findings('bridge/test_connections.py', other))
        self.assertIn(('url-password', 1), check.findings('configuration.py', fake))

    def test_history_scans_deleted_blob_and_deduplicates_unchanged_versions(self):
        def fake_git(*args):
            if args[0] == 'rev-list': return b'new\nold\n'
            if args[0] == 'ls-tree':
                return b'100644 blob kept\tREADME.md\0' + (b'100644 blob secret\told.key\0' if args[-1] == 'old' else b'')
            return b'private data' if args[-1] == 'secret' else b'overview'
        with patch.object(check, 'git', fake_git):
            values = list(check.entries(history=True))
        self.assertEqual(2, len(values))
        self.assertIn(('old.key', b'private data'), values)


if __name__ == '__main__':
    unittest.main()
