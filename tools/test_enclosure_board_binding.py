#!/usr/bin/env python3
"""Pure-file fail-closed controls; no native processes or approval regeneration.

Synthetic fixtures deliberately reapprove altered inputs only to isolate deeper
rejection conditions. That helper never writes a real reviewed manifest.
Optional real arguments verify the unchanged 03a6 checkpoint using a temporary
package, so the frozen original is never modified.
"""
from pathlib import Path
import argparse
import json
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

import check_enclosure_board_binding as gate

OBSERVED = []


def put_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def board_bytes(vias=120, footprints=206):
    return ('(kicad_pcb (version 20260101)\n' +
            ''.join(f'(footprint "test:R" (at {n} 1) (property "Reference" "R{n}"))\n'
                    for n in range(footprints)) +
            ''.join(f'(via (at {n} 2) (size .6) (drill .3) (layers "F.Cu" "B.Cu"))\n'
                    for n in range(vias)) +
            '(segment (start 0 0) (end 1 0) (width .2) (layer "In2.Cu") (net "usb_dp") (uuid "s1"))\n'
            '(segment (start 1 0) (end 2 0) (width .2) (layer "In2.Cu") (net "usb_dp") (uuid "s2"))\n'
            '(segment (start 20 0) (end 21 0) (width .2) (layer "In2.Cu") (net "usb_dp") (uuid "s3"))\n'
            '(segment (start 1 0) (end 1 1) (width .2) (layer "In2.Cu") (net "usb_dm") (uuid "s4"))\n'
            '(segment (start 1 0) (end 1 -1) (width .2) (layer "F.Cu") (net "usb_dp") (uuid "s5"))\n'
            '(segment (start 1.001 0) (end 2.001 0) (width .2) (layer "In2.Cu") (net "usb_dp") (uuid "s6"))\n)\n').encode()


class Fixture:
    def __init__(self, folder):
        folder = folder.resolve()  # macOS /var is a symlink to /private/var.
        self.repo, self.package, self.native = (folder / p for p in ('repo', 'package', 'native'))
        self.source = 'hw/layouts/test/source.kicad_pcb'
        self.library = 'hw/parts/test/test.kicad_mod'
        for name, data in ((self.source, board_bytes(vias=0)),
                           (self.library, b'(footprint "test:R")\n'),
                           (gate.RUNTIME + '/routing-records.json', b'{"route": 1}\n'),
                           (gate.RUNTIME + '/geometry.py', b'# geometry source\n'),
                           (gate.RUNTIME + '/models/example.wrl', b'# test model\n')):
            path = self.repo / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        for name in gate.HELPERS:
            p = self.repo / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('# helper\n')
        self.binding = {'source': self.source, 'files': {
            name: gate.digest((self.repo / name).read_bytes()) for name in (self.source, self.library)}}
        put_json(self.repo / gate.BINDING, self.binding)
        self.native.mkdir(); self.board = self.native / 'candidate.kicad_pcb'
        self.receipt_path = self.native / 'native.json'; self.board.write_bytes(board_bytes())
        self.project = self.native / 'candidate.kicad_pro'; self.project.write_text('{}\n')
        self.drc_path = self.native / 'drc.json'
        self.drc = dict(date='2026-10-21T12:28:30', source='candidate.kicad_pcb',
                        coordinate_units='mm', kicad_version='10.0.7', ignored_checks=[],
                        included_severities=['error', 'warning'], schematic_parity=[],
                        violations=[dict(type='footprint_type_mismatch', severity='error',
                                         description='Named retained finding', items=[dict(uuid='R0')])],
                        unconnected_items=[dict(type='unconnected_items', severity='error',
                            description='Missing connection between items', items=[
                                dict(uuid='p1', pos=dict(x=0,y=4), description='Pad 1 [usb_dp] of R0 on F.Cu'),
                                dict(uuid='s1',pos=dict(x=0,y=0),description='Track [usb_dp] on In2.Cu, length 1.0000 mm')])])
        put_json(self.drc_path, self.drc)
        self.receipt = dict(board_sha256=gate.digest(self.board.read_bytes()),
                            project_sha256=gate.digest(self.project.read_bytes()),
                            drc_sha256=gate.digest(self.drc_path.read_bytes()), remaining_connections=1,
                            retained_violations={'footprint_type_mismatch':1},
                            source_sha256=self.binding['files'][self.source], source_inputs_unchanged=True,
                            physical_checks='passed on saved filled board', fault_checks='passed')
        put_json(self.receipt_path, self.receipt)
        self.contract = {'physical_board': dict(file='data/physical-board.kicad_pcb',
                                               sha256=self.receipt['board_sha256'], footprints=206, rear_vias=120)}
        self.copied = self.package / self.contract['physical_board']['file']
        self.copied.parent.mkdir(parents=True); shutil.copyfile(self.board, self.copied)
        put_json(self.package / gate.CONTRACT, self.contract)
        self.approve_test_fixture()

    def approve_test_fixture(self):
        """Only synthetic fixture mutation isolation, never a real approval API."""
        names = gate.runtime_files(self.repo) | set(self.binding['files'])
        self.approved = dict(schema=gate.SCHEMA, basis={'kind': 'reviewed-independent-baseline'},
                             contract_sha256=gate.digest((self.package / gate.CONTRACT).read_bytes()),
                             native_board_sha256=self.contract['physical_board']['sha256'],
                             native_receipt_sha256=gate.digest(self.receipt_path.read_bytes()),
                             native_receipt_invariants={k:v for k,v in self.receipt.items() if k!='drc_sha256'},
                             drc_semantic_sha256=gate.digest(gate.canonical(gate.semantic_drc(self.drc,self.board.read_bytes())).encode()),
                             source_binding_sha256=gate.digest((self.repo / gate.BINDING).read_bytes()),
                             source_capture_sha256=self.binding['files'][self.source],
                             repo_files={p: gate.digest((self.repo / p).read_bytes()) for p in names})
        put_json(self.package / gate.MANIFEST, self.approved)

    def update_drc(self):
        put_json(self.drc_path, self.drc)
        self.receipt['drc_sha256'] = gate.digest(self.drc_path.read_bytes())
        put_json(self.receipt_path, self.receipt)

    def run(self, **changes):
        args = dict(package=self.package, repo=self.repo,
                    native_board=self.board, native_receipt=self.receipt_path)
        args.update(changes)
        return gate.check(**args)

    def source_only(self):
        return self.run(native_board=None, native_receipt=None, source_only=True)


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='enclosure-binding-test-')
        self.f = Fixture(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def reject(self, code, action=None):
        with self.assertRaises(gate.BindingError) as context:
            (action or self.f.run)()
        self.assertEqual(context.exception.code, code)
        OBSERVED.append({'control': self.id().split('.')[-1], 'rejected': True, 'error': code})

    def test_accepted_native_fixture(self):
        result = self.f.run()
        self.assertTrue(result['native_verification'])
        self.assertEqual(result['native_inventory'], dict(footprints=206, rear_vias=120))
        OBSERVED.append({'control': self._testMethodName, 'accepted': True, 'mode': result['verification_mode']})

    def test_source_only_explicit_no_native_claim(self):
        self.f.board.unlink(); self.f.receipt_path.unlink()
        result = self.f.source_only()
        self.assertFalse(result['native_verification'])
        self.assertIsNone(result['native_inventory']); self.assertIsNone(result['native_board_sha256'])
        OBSERVED.append({'control': self._testMethodName, 'accepted': True, 'mode': result['verification_mode']})

    def test_missing_native_board_no_copy_fallback(self):
        self.f.board.unlink(); self.reject('missing_file')

    def test_missing_native_receipt(self):
        self.f.receipt_path.unlink(); self.reject('missing_file')

    def test_missing_approved_manifest(self):
        (self.f.package / gate.MANIFEST).unlink(); self.reject('missing_file')

    def test_changed_native_byte(self):
        self.f.board.write_bytes(self.f.board.read_bytes() + b'\n'); self.reject('artifact_hash')

    def test_same_count_native_pose_change(self):
        self.f.board.write_bytes(self.f.board.read_bytes().replace(b'(at 0 1)', b'(at 0.25 1)', 1))
        self.assertEqual(gate.inventory(self.f.board.read_bytes()), dict(footprints=206, rear_vias=120))
        self.reject('artifact_hash')

    def test_different_receipt_rejected(self):
        self.f.receipt['unknown_field'] = 'not reviewed'; put_json(self.f.receipt_path, self.f.receipt)
        self.reject('receipt_fields')

    def test_successor_211_vias_not_rebound(self):
        self.f.board.write_bytes(board_bytes(vias=211))
        self.f.receipt['board_sha256'] = gate.digest(self.f.board.read_bytes())
        put_json(self.f.receipt_path, self.f.receipt)
        self.f.approve_test_fixture()  # isolate the active contract, not only receipt bytes
        self.reject('unreviewed_board')

    def test_211_vias_coherent_hashes_still_fail_count(self):
        self.f.board.write_bytes(board_bytes(vias=211)); shutil.copyfile(self.f.board, self.f.copied)
        sha = gate.digest(self.f.board.read_bytes())
        self.f.receipt['board_sha256'] = sha; put_json(self.f.receipt_path, self.f.receipt)
        self.f.contract['physical_board']['sha256'] = sha
        put_json(self.f.package / gate.CONTRACT, self.f.contract); self.f.approve_test_fixture()
        self.reject('actual_inventory')

    def test_all_actual_footprints_counted(self):
        self.f.contract['physical_board']['footprints'] = 205
        put_json(self.f.package / gate.CONTRACT, self.f.contract); self.f.approve_test_fixture()
        self.reject('actual_inventory')

    def test_changed_copied_board(self):
        self.f.copied.write_bytes(self.f.copied.read_bytes() + b'\n'); self.reject('copied_board_hash')

    def test_changed_active_contract(self):
        self.f.contract['physical_board']['rear_vias'] = 211
        put_json(self.f.package / gate.CONTRACT, self.f.contract); self.reject('contract_hash')

    def test_changed_route_same_count(self):
        p = self.f.repo / gate.RUNTIME / 'routing-records.json'
        p.write_text('{"route": 2}\n'); self.reject('live_input_hash')

    def test_source_only_rejects_changed_route(self):
        (self.f.repo / gate.RUNTIME / 'routing-records.json').write_text('{"route": 2}\n')
        self.reject('live_input_hash', self.f.source_only)

    def test_changed_runtime_model(self):
        (self.f.repo / gate.RUNTIME / 'models/example.wrl').write_text('# changed\n')
        self.reject('live_input_hash')

    def test_changed_source_library(self):
        (self.f.repo / self.f.library).write_text('(footprint "changed")\n'); self.reject('live_input_hash')

    def test_changed_builder(self):
        (self.f.repo / gate.HELPERS[0]).write_text('# changed\n'); self.reject('live_input_hash')

    def test_new_runtime_file(self):
        (self.f.repo / gate.RUNTIME / 'new-route.json').write_text('{}\n'); self.reject('input_coverage')

    def test_removed_runtime_file(self):
        (self.f.repo / gate.RUNTIME / 'geometry.py').unlink(); self.reject('input_coverage')

    def test_changed_source_binding(self):
        (self.f.repo / gate.BINDING).write_text('{}\n'); self.reject('source_binding_hash')

    def test_new_capture_with_stale_receipt(self):
        (self.f.repo / self.f.source).write_bytes(board_bytes(vias=1))
        self.f.binding['files'][self.f.source] = gate.digest((self.f.repo / self.f.source).read_bytes())
        put_json(self.f.repo / gate.BINDING, self.f.binding); self.f.approve_test_fixture()
        self.reject('capture_receipt')

    def test_native_checks_must_be_passed(self):
        self.f.receipt['fault_checks'] = 'not run'
        put_json(self.f.receipt_path, self.f.receipt); self.f.approve_test_fixture()
        self.reject('native_checks')

    def test_inputs_changed_native_receipt(self):
        self.f.receipt['source_inputs_unchanged'] = False
        put_json(self.f.receipt_path, self.f.receipt); self.f.approve_test_fixture()
        self.reject('native_checks')

    def test_no_native_args_is_not_source_only(self):
        self.reject('mode', lambda: self.f.run(native_board=None, native_receipt=None))

    def test_only_one_native_arg(self):
        self.reject('mode', lambda: self.f.run(native_receipt=None))

    def test_source_only_with_native_args_rejected(self):
        self.reject('mode', lambda: self.f.run(source_only=True))

    def test_native_artifact_cannot_be_package_copy(self):
        self.reject('artifact_is_copy', lambda: self.f.run(native_board=self.f.copied))

    def test_artifact_pair_must_share_directory(self):
        other = Path(self.tmp.name) / 'receipt.json'; shutil.copyfile(self.f.receipt_path, other)
        self.reject('artifact_directory', lambda: self.f.run(native_receipt=other))

    def test_contract_path_traversal(self):
        self.f.contract['physical_board']['file'] = '../native/candidate.kicad_pcb'
        put_json(self.f.package / gate.CONTRACT, self.f.contract); self.f.approve_test_fixture()
        self.reject('unsafe_path')

    def test_runtime_symlink_cannot_hide_inputs(self):
        outside = Path(self.tmp.name) / 'external'; outside.mkdir()
        (self.f.repo / gate.RUNTIME / 'hidden').symlink_to(outside, target_is_directory=True)
        self.reject('unsafe_path')

    def test_source_path_symlink_escape(self):
        p = self.f.repo / self.f.library; data = p.read_bytes(); p.unlink()
        out = Path(self.tmp.name) / 'external.kicad_mod'; out.write_bytes(data); p.symlink_to(out)
        self.reject('unsafe_path')

    def test_duplicate_approval_keys_rejected(self):
        p = self.f.package / gate.MANIFEST
        p.write_text('{"schema":"x","schema":"y"}')
        self.reject('invalid_json')

    def test_missing_wider_input_approval_rejected(self):
        del self.f.approved['repo_files'][gate.RUNTIME + '/geometry.py']
        put_json(self.f.package / gate.MANIFEST, self.f.approved); self.reject('input_coverage')

    def test_snapshot_changes_detected(self):
        original = gate.Reads.unchanged
        def change_before_final_read(reads):
            (self.f.repo / gate.RUNTIME / 'routing-records.json').write_text('{"route": 3}\n')
            original(reads)
        with patch.object(gate.Reads, 'unchanged', change_before_final_read):
            self.reject('input_changed')

    def test_inventory_ignores_nested_and_quoted_tags(self):
        value = b'(kicad_pcb (footprint "(via fake)" (property "x" "escaped \\\" (via" ) (via nested)) (via (at 1 2)))'
        self.assertEqual(gate.inventory(value), dict(footprints=1, rear_vias=1))
        OBSERVED.append({'control': self._testMethodName, 'passed': True})

    def test_inventory_rejects_incomplete_or_wrong_root(self):
        for data in (b'(kicad_pcb (via)', b'(other)', b'(kicad_pcb) (kicad_pcb)', b'"quoted"', b'(kicad_pcb ())'):
            with self.assertRaises(gate.BindingError) as context: gate.inventory(data)
            self.assertEqual(context.exception.code, 'invalid_board')
        OBSERVED.append({'control': self._testMethodName, 'passed': True, 'rejected_variants': 5})

    def test_report_date_and_endpoint_order_allowed(self):
        self.f.drc['date'] = '2026-10-22T12:29:30'
        self.f.drc['unconnected_items'][0]['items'].reverse(); self.f.update_drc()
        self.assertTrue(self.f.run()['native_verification'])
        OBSERVED.append({'control':self._testMethodName,'accepted':True})

    def test_direct_same_net_layer_chain_representative_allowed(self):
        item = self.f.drc['unconnected_items'][0]['items'][1]
        item.update(uuid='s2',pos=dict(x=1,y=0)); self.f.update_drc()
        self.assertTrue(self.f.run()['native_verification'])
        OBSERVED.append({'control':self._testMethodName,'accepted':True})

    def test_unrelated_track_representative_rejected(self):
        self.f.drc['unconnected_items'][0]['items'][1].update(uuid='s3',pos=dict(x=20,y=0))
        self.f.update_drc(); self.reject('drc_semantics')

    def test_same_endpoint_different_net_not_equivalent(self):
        self.f.drc['unconnected_items'][0]['items'][1].update(uuid='s4',pos=dict(x=1,y=0),description='Track [usb_dm] on In2.Cu, length 1.0000 mm')
        self.f.update_drc(); self.reject('drc_semantics')

    def test_same_endpoint_different_layer_not_equivalent(self):
        self.f.drc['unconnected_items'][0]['items'][1].update(uuid='s5',pos=dict(x=1,y=0),description='Track [usb_dp] on F.Cu, length 1.0000 mm')
        self.f.update_drc(); self.reject('drc_semantics')

    def test_near_endpoint_is_not_connected(self):
        self.f.drc['unconnected_items'][0]['items'][1].update(uuid='s6',pos=dict(x=1.001,y=0))
        self.f.update_drc(); self.reject('drc_semantics')

    def test_false_reported_net_rejected(self):
        self.f.drc['unconnected_items'][0]['items'][1]['description']='Track [usb_dm] on In2.Cu, length 1.0000 mm'
        self.f.update_drc(); self.reject('drc_track')

    def test_false_reported_layer_rejected(self):
        self.f.drc['unconnected_items'][0]['items'][1]['description']='Track [usb_dp] on F.Cu, length 1.0000 mm'
        self.f.update_drc(); self.reject('drc_track')

    def test_false_reported_length_rejected(self):
        self.f.drc['unconnected_items'][0]['items'][1]['description']='Track [usb_dp] on In2.Cu, length 1.1000 mm'
        self.f.update_drc(); self.reject('drc_track')

    def test_false_reported_position_rejected(self):
        self.f.drc['unconnected_items'][0]['items'][1]['pos']['x']=.01
        self.f.update_drc(); self.reject('drc_track')

    def test_report_unknown_field_preserved_and_rejected(self):
        self.f.drc['unknown_field']='not reviewed'; self.f.update_drc(); self.reject('drc_semantics')

    def test_track_unknown_field_rejected(self):
        self.f.drc['unconnected_items'][0]['items'][1]['unknown']='not reviewed'
        self.f.update_drc(); self.reject('drc_track')

    def test_true_additional_violation_rejected(self):
        self.f.drc['violations'].append(dict(type='clearance',severity='error',description='new',items=[dict(uuid='s1'),dict(uuid='s4')]))
        self.f.update_drc(); self.reject('drc_semantics')

    def test_faked_connection_count_rejected(self):
        self.f.receipt['remaining_connections']=0; put_json(self.f.receipt_path,self.f.receipt)
        self.reject('receipt_fields')

    def test_receipt_field_types_remain_exact(self):
        self.f.receipt['remaining_connections']=True; put_json(self.f.receipt_path,self.f.receipt)
        self.reject('receipt_fields')

    def test_removed_missing_connection_rejected(self):
        self.f.drc['unconnected_items']=[]; self.f.update_drc(); self.reject('drc_semantics')

    def test_missing_actual_drc_rejected(self):
        self.f.drc_path.unlink(); self.reject('missing_file')

    def test_missing_actual_project_rejected(self):
        self.f.project.unlink(); self.reject('missing_file')

    def test_actual_project_hash_required(self):
        self.f.project.write_text('{"changed":true}\n'); self.reject('project_hash')

    def test_actual_drc_hash_required(self):
        self.f.drc_path.write_text('{}\n'); self.reject('drc_hash')

    def test_ignored_check_settings_rejected(self):
        self.f.drc['ignored_checks']=['clearance']; self.f.update_drc(); self.reject('drc_semantics')


def real_control(args):
    expected = '03a6b3dc624e2cf0e83f8cfdd90f64dc52071fb2b8387deb0e22949903981e74'
    package, repo = args.real_package.resolve(), args.real_repo.resolve()
    contract_bytes = (package / gate.CONTRACT).read_bytes()
    contract = json.loads(contract_bytes); physical = contract['physical_board']
    assert physical['sha256'] == expected
    with tempfile.TemporaryDirectory(prefix='enclosure-binding-real-') as tmp:
        copy_package = Path(tmp)
        for name, source in ((gate.CONTRACT, package / gate.CONTRACT),
                             (physical['file'], package / physical['file']),
                             (gate.MANIFEST, args.approved_manifest)):
            target = copy_package / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        full = gate.check(package=copy_package, repo=repo, native_board=args.native_board,
                          native_receipt=args.native_receipt)
        source_only = gate.check(package=copy_package, repo=repo, source_only=True)
        ci = None
        if args.ci_native_board:
            ci = gate.check(package=copy_package, repo=repo, native_board=args.ci_native_board,
                            native_receipt=args.ci_native_receipt)
            assert ci['native_board_sha256'] == full['native_board_sha256']
            assert ci['native_drc_semantic_sha256'] == full['native_drc_semantic_sha256']
    assert full['native_board_sha256'] == expected
    assert full['native_inventory'] == dict(footprints=206, rear_vias=120)
    assert source_only['native_verification'] is False
    originals = [package / gate.CONTRACT, package / physical['file'], args.approved_manifest]
    return dict(passed=True, native_artifact=full, ci_native_artifact=ci, preview_guard=source_only,
                original_package_inputs={str(p.resolve()): gate.digest(p.read_bytes()) for p in originals},
                note='Frozen package was read only; checks ran against exact temporary copies. Input paths under the deleted temporary package are evidence identities, not required runtime dependencies.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('real-repo', 'real-package', 'native-board', 'native-receipt', 'ci-native-board', 'ci-native-receipt', 'approved-manifest', 'evidence'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    real_args = [args.real_repo, args.real_package, args.native_board, args.native_receipt, args.approved_manifest]
    if any(real_args) and not all(real_args): parser.error('Real control requires all five input arguments')
    if bool(args.ci_native_board) != bool(args.ci_native_receipt) or (args.ci_native_board and not all(real_args)):
        parser.error('CI comparison requires both artifact paths and all real control inputs')
    started = time.time()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    real = real_control(args) if result.wasSuccessful() and all(real_args) else None
    evidence = dict(passed=result.wasSuccessful(), tests=result.testsRun, controls=OBSERVED,
                    real_03a6_control=real, elapsed_seconds=round(time.time()-started, 3),
                    failures=[{'test': test.id(), 'traceback': trace} for test, trace in result.failures + result.errors],
                    code_sha256={p.name: gate.digest(p.read_bytes()) for p in (Path(__file__), Path(gate.__file__))},
                    limits=['Pure file checks only; no native process, CAD export or fit verification ran.',
                            'Synthetic reapproval isolates validation branches; it never approves or edits real package inputs.'])
    if args.evidence: put_json(args.evidence, evidence)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
