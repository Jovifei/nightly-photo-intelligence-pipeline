"""Generated artifact fixtures only. These are NOT new S3/S20 model evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence_audit import (ARTIFACTS, CASE_IDS, COMPLETE, COUNTERS, TOP, AuditError,
                            audit_release, canonical, digest, inspect_payload,
                            load_release, read_regular, safe_relative, strict_json)
from negative_space import measure_bbox_empty_area


def fixture_payload():
    identity = dict(model_name='qwen3.5:9b', full_local_digest='a' * 64,
                    size_bytes=123, quantization_level='Q4_K_M', capabilities=['vision'], ollama_version='0.33.3')
    objects = {name: {} for name in TOP}
    objects['ollama_identity.json'] = identity
    fixtures, first, records = [], [], {}
    identity_sha = digest(canonical(identity))
    for n, case in enumerate(CASE_IDS):
        profile = 'strict' if n < 10 else 'observation' if n < 18 else 'negative' if n == 18 else 'unsupported'
        fixtures.append(dict(case_id=case, width=100, height=100, acceptance_profile=profile, image_sha256='b' * 64))
        boxes = [] if profile == 'negative' else [dict(x_min=0, y_min=0, x_max=20, y_max=100)]
        metrics = measure_bbox_empty_area(boxes, 100, 100)
        facts = dict(case_id=case, image_sha256='b' * 64, person_boxes=boxes,
                     fact_ids=['fact-person-count'], person_count=len(boxes),
                     negative_space_metrics={k: v for k, v in metrics.items() if k.endswith('_ratio')})
        facts['fact_digest'] = digest(canonical(facts, False))
        first.append(facts)
        analysis = dict(case_id=case, input_fact_digest=facts['fact_digest'],
                        story_candidates=dict(safe='safe', narrative='narrative', dynamic='dynamic'))
        director = dict(case_id=case, input_fact_digest=facts['fact_digest'],
                        reasoning_based_on_fact_ids=facts['fact_ids'],
                        director_prompts=dict(standard='standard', dramatic='dramatic', plan_b='plan b', technical='technical'))
        bundle = dict(bundle_type='SYNTHETIC_VALIDATION', case_id=case, image_sha256='b' * 64,
                      checksums=dict(vision_facts_sha256=digest(canonical(facts)),
                                     reasoning_sha256=digest(canonical(analysis)),
                                     director_prompt_sha256=digest(canonical(director))))
        for name, data in zip(ARTIFACTS, (analysis, facts, director, bundle)):
            objects[f'cases/{case}/{name}'] = data
        raw = dict(case_id=case, input_fact_digest=facts['fact_digest'], reasoning_based_on_fact_ids=facts['fact_ids'])
        binding = dict(raw_response_sha256=digest(canonical(raw)), model_identity_sha256=identity_sha,
                       authoritative_fact_digest=facts['fact_digest'], echoed_fact_digest=facts['fact_digest'],
                       echo_match=True, fact_reference_valid=True, validation_status='PASS', forbidden_field_count=0, errors=[])
        for group in (('qwen', 'qwen-repeat') if n < 5 else ('qwen',)):
            objects[f'diagnostics/{group}/{case}/raw_response.json'] = copy.deepcopy(raw)
            objects[f'diagnostics/{group}/{case}/binding_validation.json'] = copy.deepcopy(binding)
        records[case] = dict(raw_response_sha256=digest(canonical(raw)),
                             binding_evidence_sha256=digest(canonical(binding)), validation_status='PASS')
    objects['fixture_manifest.json'] = dict(fixtures=fixtures)
    objects['synthetic_bundle_index.json'] = dict(bundle_count=20, cases=[dict(case_id=c) for c in CASE_IDS])
    objects['checkpoint.json'] = dict(status='COMPLETE', completed_cases=list(CASE_IDS), bundle_count=20,
                                     qwen_repeat_case_ids=list(CASE_IDS[:5]), qwen_case_records=records,
                                     model_identity=identity_sha, manifest_sha256=digest(canonical(objects['fixture_manifest.json'])),
                                     reviewed_commit='c' * 40)
    objects['validation_summary.json'] = dict(result=COMPLETE, bundle_count=20, s20_execution_status='PERFORMED_SYNTHETIC_ONLY',
                                              production_bundle_release='NOT_CREATED', hard_counts=dict.fromkeys(COUNTERS, 0),
                                              gpu=dict(peak_mib=11000), reviewed_commit='c' * 40)
    objects['runtime_metrics.json'] = dict(gpu=dict(peak_mib=11000))
    objects['cleanup_evidence.json'] = dict(qwen_unloaded=True, torchvision_resident_roles=[])
    for name in ('acceptance_report.json', 'repeatability_report.json'):
        objects[f'diagnostics/{name}'] = {}
    objects['diagnostics/visual_facts_first.json'] = first
    objects['diagnostics/visual_facts_second.json'] = copy.deepcopy(first)
    for name in ('binding_validation_1.json', 'binding_validation_2.json'):
        objects[f'diagnostics/qwen-probe/{name}'] = dict(model_identity_sha256=identity_sha)
    for name in ('raw_response_1.json', 'raw_response_2.json', 'probe_summary.json'):
        objects[f'diagnostics/qwen-probe/{name}'] = {}
    return {name: canonical(value) for name, value in objects.items()}


def checksum_files(files):
    files = {k: v for k, v in files.items() if k != 'CHECKSUMS.sha256'}
    checks = ''.join(f'{digest(files[name])}  {name}\n' for name in sorted(files)).encode()
    return dict(files, **{'CHECKSUMS.sha256': checks})


def write_fixture(root, files):
    files = checksum_files(files)
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return digest(files['CHECKSUMS.sha256'])


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'synthetic-release'
        self.root.mkdir()
        self.files = fixture_payload()
        self.anchor = write_fixture(self.root, self.files)

    def mutate(self, path, update):
        value = strict_json(self.files[path])
        update(value)
        self.files[path] = canonical(value)
        self.anchor = write_fixture(self.root, self.files)

    def test_positive_exact_149_files_and_no_false_runtime_claim(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        report = audit_release(self.root, self.anchor)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(report['file_count'], 149)
        self.assertEqual(report['nonempty_story_and_prompt_cases'], 20)
        self.assertEqual(report['bbox_proxy_semantic_difference_cases'], [])
        self.assertEqual(report['live_resume'], 'NOT_EXECUTED')
        self.assertFalse(report['production_authorization'])

    def test_regular_file_read_ignores_platform_volatile_ctime(self):
        path = self.root / 'cases/n2b2-s20-01/analysis.json'
        original = path.lstat()

        class StatProxy:
            def __init__(self, stat_result, ctime_ns):
                self._stat_result = stat_result
                self.st_ctime_ns = ctime_ns

            def __getattr__(self, name):
                return getattr(self._stat_result, name)

        with patch('evidence_audit.os.fstat', side_effect=[StatProxy(original, 2), StatProxy(original, 2)]):
            self.assertEqual(read_regular(path), self.files[path.relative_to(self.root).as_posix()])

    def test_no_network_or_model_runtime_imports(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            self.assertEqual(audit_release(self.root, self.anchor)['case_count'], 20)
        code = Path(__file__).with_name('evidence_audit.py').read_text()
        self.assertNotIn('import torch', code)
        self.assertNotIn('import sqlite', code)
        self.assertNotIn('import urllib', code)

    def test_mandatory_trusted_checksum_anchor(self):
        for value in ('', 'f' * 64, 'z' * 64):
            with self.assertRaises(AuditError):
                audit_release(self.root, value)

    def test_hash_tamper(self):
        (self.root / 'cleanup_evidence.json').write_text('{}')
        with self.assertRaisesRegex(AuditError, 'FILE_HASH_MISMATCH'):
            audit_release(self.root, self.anchor)

    def test_unlisted_file(self):
        (self.root / 'extra.json').write_text('{}')
        with self.assertRaisesRegex(AuditError, 'FILE_SET_MISMATCH'):
            audit_release(self.root, self.anchor)

    def test_missing_file(self):
        (self.root / 'cleanup_evidence.json').unlink()
        with self.assertRaisesRegex(AuditError, 'FILE_SET_MISMATCH'):
            audit_release(self.root, self.anchor)

    def test_duplicate_checksum(self):
        path = self.root / 'CHECKSUMS.sha256'
        path.write_bytes(path.read_bytes() + path.read_bytes().splitlines(keepends=True)[0])
        with self.assertRaisesRegex(AuditError, 'DUPLICATE'):
            audit_release(self.root, digest(path.read_bytes()))

    def test_unsafe_checksum_paths_are_rejected(self):
        for value in ('../a.json', '/a.json', 'a//b.json', 'a/./b.json', 'a\\b.json', 'x:stream.json', 'CON.json', 'a./b.json', 'a /b.json', 'a/../../b.json'):
            self.assertFalse(safe_relative(value))
        self.assertTrue(safe_relative('cases/n2b2-s20-01/analysis.json'))

    def test_duplicate_json_members_and_nonfinite(self):
        for value in (b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'):
            with self.assertRaises(AuditError):
                strict_json(value)

    def test_resigned_internal_bundle_tamper(self):
        self.mutate('cases/n2b2-s20-01/reference_bundle.json', lambda x: x['checksums'].update(reasoning_sha256='0' * 64))
        with self.assertRaisesRegex(AuditError, 'BUNDLE_INNER_CHECKSUM'):
            audit_release(self.root, self.anchor)

    def test_nonzero_and_missing_counters(self):
        for counters in ({}, dict.fromkeys(COUNTERS, False), dict.fromkeys(COUNTERS, 1)):
            self.mutate('validation_summary.json', lambda x: x.update(hard_counts=counters))
            with self.assertRaisesRegex(AuditError, 'COUNTER'):
                audit_release(self.root, self.anchor)

    def test_gpu_peak_is_required_finite_numeric_and_under_limit(self):
        for peak in (None, True, '11000', -1, 11501, 11500.1):
            self.mutate('validation_summary.json', lambda x: x.update(gpu=dict(peak_mib=peak)))
            with self.assertRaisesRegex(AuditError, 'GPU_PEAK_INVALID'):
                audit_release(self.root, self.anchor)

    def test_gpu_runtime_summary_contradiction(self):
        self.mutate('runtime_metrics.json', lambda x: x.update(gpu=dict(peak_mib=1)))
        with self.assertRaisesRegex(AuditError, 'GPU_EVIDENCE_CONTRADICTION'):
            audit_release(self.root, self.anchor)

    def test_saved_identity_mismatch(self):
        self.mutate('ollama_identity.json', lambda x: x.update(ollama_version='future'))
        with self.assertRaisesRegex(AuditError, 'SAVED_IDENTITY_MISMATCH'):
            audit_release(self.root, self.anchor)

    def test_unknown_fact_reference(self):
        self.mutate('cases/n2b2-s20-01/director_prompt.json', lambda x: x.update(reasoning_based_on_fact_ids=['invented']))
        with self.assertRaisesRegex(AuditError, 'UNKNOWN_FACT_REFERENCE'):
            audit_release(self.root, self.anchor)

    def test_fact_hash_and_round_mismatch(self):
        self.mutate('cases/n2b2-s20-01/vision_facts.json', lambda x: x.update(person_count=99))
        with self.assertRaisesRegex(AuditError, 'FACT_DIGEST'):
            audit_release(self.root, self.anchor)

    def test_repeated_fact_bytes_mismatch(self):
        self.mutate('diagnostics/visual_facts_second.json', lambda x: x[0].update(person_count=99))
        with self.assertRaisesRegex(AuditError, 'FACT_REPEAT_MISMATCH'):
            audit_release(self.root, self.anchor)

    def test_checkpoint_response_hash_mismatch(self):
        self.mutate('checkpoint.json', lambda x: x['qwen_case_records'][CASE_IDS[0]].update(raw_response_sha256='0' * 64))
        with self.assertRaisesRegex(AuditError, 'CHECKPOINT_RESPONSE_HASH'):
            audit_release(self.root, self.anchor)

    def test_qwen_false_binding_not_accepted(self):
        self.mutate('diagnostics/qwen/n2b2-s20-01/binding_validation.json', lambda x: x.update(echo_match=False))
        with self.assertRaisesRegex(AuditError, 'QWEN_BINDING'):
            audit_release(self.root, self.anchor)

    def test_wrong_case_count(self):
        self.mutate('synthetic_bundle_index.json', lambda x: x.update(bundle_count=19))
        with self.assertRaisesRegex(AuditError, 'INDEX_CASE_SET'):
            audit_release(self.root, self.anchor)

    def test_duplicate_repeat_case_ids(self):
        self.mutate('checkpoint.json', lambda x: x.update(qwen_repeat_case_ids=[CASE_IDS[0]] * 5))
        with self.assertRaisesRegex(AuditError, 'REPEAT_CASE_SET'):
            audit_release(self.root, self.anchor)

    def test_failure_summary_never_allowed_with_complete(self):
        self.files['failure_summary.json'] = b'{}'
        self.anchor = write_fixture(self.root, self.files)
        with self.assertRaisesRegex(AuditError, 'LAYOUT'):
            audit_release(self.root, self.anchor)

    def test_production_bundle_rejected(self):
        self.mutate('cases/n2b2-s20-01/reference_bundle.json', lambda x: x.update(bundle_type='PRODUCTION'))
        with self.assertRaisesRegex(AuditError, 'BUNDLE_SCOPE'):
            audit_release(self.root, self.anchor)

    def test_unload_missing(self):
        self.mutate('cleanup_evidence.json', lambda x: x.update(qwen_unloaded=False))
        with self.assertRaisesRegex(AuditError, 'UNLOAD'):
            audit_release(self.root, self.anchor)

    def test_symlink_file_and_root_rejected_without_reading_target(self):
        path = self.root / 'cleanup_evidence.json'
        outside = Path(self.temp.name) / 'outside.json'
        outside.write_text('{}')
        path.unlink()
        try:
            path.symlink_to(outside)
        except OSError as exc:
            if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows symlink creation requires SeCreateSymbolicLinkPrivilege')
            raise
        with self.assertRaisesRegex(AuditError, 'REPARSE'):
            load_release(self.root, self.anchor)
        alias = Path(self.temp.name) / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(AuditError, 'REPARSE'):
            load_release(alias, self.anchor)

    def test_hardlink_rejected(self):
        path = self.root / 'cleanup_evidence.json'
        os.link(path, Path(self.temp.name) / 'hardlink.json')
        with self.assertRaisesRegex(AuditError, 'NON_REGULAR'):
            audit_release(self.root, self.anchor)

    def test_size_bound(self):
        with patch('evidence_audit.MAX_FILE_BYTES', 10):
            with self.assertRaisesRegex(AuditError, 'SIZE_LIMIT'):
                load_release(self.root, self.anchor)

    def test_mutation_during_audit_is_detected(self):
        from evidence_audit import inspect_payload as real_inspect
        def mutate_then_report(files, anchor):
            report = real_inspect(files, anchor)
            (self.root / 'cleanup_evidence.json').write_text('{}')
            return report
        with patch('evidence_audit.inspect_payload', side_effect=mutate_then_report):
            with self.assertRaises(AuditError):
                audit_release(self.root, self.anchor)

    def test_cli_has_safe_errors(self):
        proc = subprocess.run([sys.executable, str(Path(__file__).with_name('evidence_audit.py')),
                               '--evidence-root', str(self.root / 'private-missing'),
                               '--checksums-sha256', self.anchor], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn(str(self.root), proc.stdout + proc.stderr)
        self.assertFalse(json.loads(proc.stdout)['production_authorization'])


if __name__ == '__main__':
    unittest.main()
