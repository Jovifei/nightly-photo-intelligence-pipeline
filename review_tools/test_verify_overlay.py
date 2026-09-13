"""Git integrity tests in synthetic repositories; no user checkout is modified."""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from verify_overlay import ALLOWED, OVERLAY_MANIFEST, OverlayError, verify


class OverlayTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True).stdout.decode().strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.command('init', '-q')
        self.command('config', 'user.name', 'Synthetic Test')
        self.command('config', 'user.email', 'synthetic@example.invalid')
        self.command('config', 'core.autocrlf', 'false')
        (self.root / 'README.md').write_bytes(b'Frozen runtime\n')
        base_hash = hashlib.sha256((self.root / 'README.md').read_bytes()).hexdigest()
        (self.root / 'MANIFEST.sha256').write_bytes(f'{base_hash}  README.md\n'.encode())
        self.command('add', '.')
        self.command('commit', '-qm', 'Synthetic base')
        self.base = self.command('rev-parse', 'HEAD')
        for rel in ALLOWED - {OVERLAY_MANIFEST}:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'Synthetic overlay fixture\n')
        self.write_manifest()
        self.commit()

    def write_manifest(self):
        rows = ''.join(f'{hashlib.sha256((self.root / p).read_bytes()).hexdigest()}  {p}\n'
                       for p in sorted(ALLOWED - {OVERLAY_MANIFEST}))
        (self.root / OVERLAY_MANIFEST).write_bytes(rows.encode())

    def commit(self, amend=False):
        self.command('add', '.')
        self.command('commit', '-qm', 'Synthetic overlay', *(['--amend'] if amend else []))

    def check(self):
        return verify(self.root, baseline=self.base, tags={})

    def test_exact_overlay_passes_without_granting_production(self):
        report = self.check()
        self.assertEqual(report['runtime_candidate'], self.base)
        self.assertEqual(report['overlay_files'], 10)
        self.assertFalse(report['production_phase_approval'])

    def test_dirty_tree_rejected(self):
        (self.root / 'README.md').write_text('dirty')
        with self.assertRaisesRegex(OverlayError, 'DIRTY_WORKTREE'):
            self.check()

    def test_runtime_change_rejected_even_if_resigned(self):
        (self.root / 'README.md').write_text('changed')
        self.commit(amend=True)
        with self.assertRaisesRegex(OverlayError, 'FILE_SCOPE'):
            self.check()

    def test_extra_tracked_file_rejected(self):
        (self.root / 'extra.py').write_text('pass')
        self.commit(amend=True)
        with self.assertRaisesRegex(OverlayError, 'FILE_SCOPE'):
            self.check()

    def test_missing_overlay_file_rejected(self):
        (self.root / 'review_tools/README.md').unlink()
        self.commit(amend=True)
        with self.assertRaisesRegex(OverlayError, 'FILE_SCOPE'):
            self.check()

    def test_changed_tool_without_digest_update_rejected(self):
        (self.root / 'review_tools/negative_space.py').write_text('changed')
        self.commit(amend=True)
        with self.assertRaisesRegex(OverlayError, 'HASH_MISMATCH'):
            self.check()

    def test_rewritten_root_manifest_rejected(self):
        path = self.root / 'MANIFEST.sha256'
        path.write_text('0' * 64 + '  README.md\n')
        self.commit(amend=True)
        with self.assertRaisesRegex(OverlayError, 'FILE_SCOPE'):
            self.check()

    def test_multiple_descendants_are_not_implicitly_authorized(self):
        (self.root / 'review_tools/README.md').write_text('more changes')
        self.write_manifest()
        self.commit()
        with self.assertRaisesRegex(OverlayError, 'ONE_DIRECT_CHILD'):
            self.check()

    def test_tag_drift_rejected(self):
        self.command('tag', 'synthetic-approved')
        with self.assertRaisesRegex(OverlayError, 'BASELINE_TAG_DRIFT'):
            verify(self.root, baseline=self.base, tags={'synthetic-approved': self.base})


if __name__ == '__main__':
    unittest.main()
