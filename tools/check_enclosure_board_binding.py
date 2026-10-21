#!/usr/bin/env python3
"""Fail closed unless a native artifact and all approved current inputs agree.

Pure standard-library file checks. This does not run KiCad, regenerate approval,
prove fit, or replace the complete enclosure checks. The independent reviewed
manifest compensates for the old native receipt's incomplete input inventory;
it is not represented as a manifest captured by that historical native build.
"""
from pathlib import Path, PurePosixPath
import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
import sys

SCHEMA = 'smart-blinds.enclosure-native-inputs.v2'
RUNTIME = 'hw/routing/clean-main'
BINDING = RUNTIME + '/source-binding.json'
HELPERS = ('tools/build_clean_main.py', 'tools/package_clean_main.py',
           'tools/kicad_sexpr.py', 'tools/generate_schematics.py')
MANIFEST = 'approved-native-inputs.json'
CONTRACT = 'parameters/enclosure-v2.json'


class BindingError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(detail)


def require(condition, code, detail):
    if not condition:
        raise BindingError(code, detail)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def safe_file(root, name):
    require(isinstance(name, str), 'unsafe_path', 'Expected a relative file path')
    p = PurePosixPath(name)
    require(not p.is_absolute() and p.parts and all(x not in ('.', '..') for x in p.parts)
            and str(p) == name and '\\' not in name,
            'unsafe_path', 'Noncanonical relative path: ' + name)
    path = root / name
    require(path.resolve().is_relative_to(root), 'unsafe_path', 'Path escapes root: ' + name)
    require(path.is_file(), 'missing_file', 'Required file is missing: ' + str(path))
    return path


def read_json(raw, label):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'invalid_json', 'Duplicate JSON key in ' + label)
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=unique)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BindingError('invalid_json', label + ': ' + str(exc)) from exc
    require(isinstance(result, dict), 'invalid_json', 'Expected object: ' + label)
    return result


class Reads:
    def __init__(self):
        self.files = {}

    def read(self, path):
        path = Path(path).absolute()
        require(path.is_file(), 'missing_file', 'Required file is missing: ' + str(path))
        data = path.read_bytes()
        current = {'resolved': str(path.resolve()), 'sha256': digest(data), 'bytes': len(data)}
        require(path not in self.files or self.files[path] == current,
                'input_changed', 'Input changed during checks: ' + str(path))
        self.files[path] = current
        return data

    def json(self, path):
        return read_json(self.read(path), str(path))

    def unchanged(self):
        for path in list(self.files):
            self.read(path)


def runtime_files(repo):
    folder = repo / RUNTIME
    require(folder.is_dir(), 'missing_file', 'Missing clean-main runtime tree')
    result = set(HELPERS)
    for path in folder.rglob('*'):
        if '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
            continue
        require(not path.is_symlink(), 'unsafe_path', 'Runtime symlinks are not approved: ' + str(path))
        if path.is_file():
            result.add(path.relative_to(repo).as_posix())
    for name in result:
        safe_file(repo, name)
    return result


def inventory(board):
    """Count only immediate native board nodes, not strings or nested drawings."""
    try:
        text = board.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise BindingError('invalid_board', 'Board is not UTF-8') from exc
    stack, counts, end, roots = [], {'footprints': 0, 'rear_vias': 0}, 0, 0
    for m in re.finditer(r'\s*(\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+)', text):
        require(not text[end:m.start()].strip(), 'invalid_board', 'Unsupported board syntax')
        end = m.end(); token = m[1]
        if token == '(':
            if not stack:
                roots += 1
                require(roots == 1, 'invalid_board', 'Multiple board roots')
            stack.append(None)
        elif token == ')':
            require(bool(stack) and stack[-1] is not None, 'invalid_board', 'Unbalanced or empty node')
            stack.pop()
        else:
            require(bool(stack), 'invalid_board', 'Token outside board')
            if stack[-1] is None:
                require(not token.startswith('"'), 'invalid_board', 'Quoted node tag')
                stack[-1] = token
                if len(stack) == 1:
                    require(token == 'kicad_pcb', 'invalid_board', 'Not a KiCad board')
                elif len(stack) == 2 and token in ('footprint', 'via'):
                    counts['footprints' if token == 'footprint' else 'rear_vias'] += 1
    require(not stack and roots == 1 and not text[end:].strip(), 'invalid_board', 'Incomplete board')
    return counts


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def board_tree(board):
    """Small checked reader; never executes board contents or imports KiCad."""
    inventory(board)  # Validate root, balance, quoted strings and syntax first.
    stack = [[]]
    for match in re.finditer(r'\s*(\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+)', board.decode()):
        token = match[1]
        if token == '(':
            node = []; stack[-1].append(node); stack.append(node)
        elif token == ')':
            stack.pop()
        else:
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    return stack[0][0]


def segment_chains(board):
    """Only exact shared endpoints of straight segments on one net/layer.

    No tolerance, crossing/overlap, pad, via, arc, zone or layer-change inference.
    This normalizes native missing-connection representatives, not connectivity.
    """
    segments, parent, endpoints = {}, {}, {}
    def one(node, tag):
        values = [n for n in node if isinstance(n, list) and n and n[0] == tag]
        require(len(values) == 1, 'invalid_board', 'Expected one segment ' + tag)
        return values[0][1:]
    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]; key = parent[key]
        return key
    for node in board_tree(board)[1:]:
        if not isinstance(node, list) or node[0] != 'segment':
            continue
        uuid, layer, net = (one(node, tag)[0] for tag in ('uuid', 'layer', 'net'))
        require(uuid not in segments, 'invalid_board', 'Duplicate segment UUID')
        try:
            start, end = (tuple(Decimal(v) for v in one(node, tag)) for tag in ('start', 'end'))
        except InvalidOperation as exc:
            raise BindingError('invalid_board', 'Non-numeric segment endpoint') from exc
        require(len(start) == len(end) == 2 and all(v.is_finite() for v in start + end),
                'invalid_board', 'Invalid segment endpoint')
        segments[uuid] = dict(net=net, layer=layer, start=start, end=end)
        parent[uuid] = uuid
        for point in (start, end):
            key = (net, layer, point)
            if key in endpoints:
                parent[find(uuid)] = find(endpoints[key])
            else:
                endpoints[key] = uuid
    groups = {}
    for uuid in segments:
        groups.setdefault(find(uuid), []).append(uuid)
    for uuid, value in segments.items():
        value['chain'] = sorted(groups[find(uuid)])
    return segments


def semantic_drc(report, board):
    """Preserve every field except date and proven representative/order noise."""
    result = json.loads(json.dumps(report))
    date = result.get('date')
    require(isinstance(date, str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d', date),
            'drc_date', 'DRC date must be an explicit ISO local timestamp')
    try:
        datetime.fromisoformat(date)
    except ValueError as exc:
        raise BindingError('drc_date', 'Invalid DRC timestamp') from exc
    del result['date']
    segments = segment_chains(board)
    for field in ('violations', 'unconnected_items', 'schematic_parity'):
        findings = result.get(field)
        require(isinstance(findings, list), 'drc_schema', 'Missing DRC finding array: ' + field)
        for finding in findings:
            require(isinstance(finding, dict) and isinstance(finding.get('items'), list),
                    'drc_schema', 'Invalid DRC finding')
            items = []
            for item in finding['items']:
                require(isinstance(item, dict) and isinstance(item.get('uuid'), str),
                        'drc_schema', 'Invalid DRC item identity')
                segment = segments.get(item.get('uuid'))
                if field == 'unconnected_items' and segment is not None:
                    require(set(item) == {'uuid', 'pos', 'description'},
                            'drc_track', 'Unexpected field on track representative')
                    require(isinstance(item['pos'], dict) and set(item['pos']) == {'x', 'y'}
                            and all(type(v) in (int, float) and math.isfinite(v) for v in item['pos'].values()),
                            'drc_track', 'Invalid track position')
                    start, end = segment['start'], segment['end']
                    expected_pos = dict(x=float(start[0]), y=float(start[1]))
                    length = math.hypot(float(end[0]-start[0]), float(end[1]-start[1]))
                    description = f"Track [{segment['net']}] on {segment['layer']}, length {length:.4f} mm"
                    require(item['pos'] == expected_pos and item['description'] == description,
                            'drc_track', 'Track position/net/layer/length disagrees with actual board')
                    item = dict(endpoint_connected_segments=segment['chain'],
                                net=segment['net'], layer=segment['layer'])
                items.append(item)
            finding['items'] = sorted(items, key=canonical)
        result[field] = sorted(findings, key=canonical)
    return result


def check(*, package, repo, native_board=None, native_receipt=None, source_only=False):
    require((source_only and native_board is None and native_receipt is None)
            or (not source_only and native_board is not None and native_receipt is not None),
            'mode', 'Choose explicit source-only mode, or supply both native artifact files')
    package, repo = Path(package).resolve(), Path(repo).resolve()
    reads = Reads()
    approved = reads.json(safe_file(package, MANIFEST))
    require(approved.get('schema') == SCHEMA, 'manifest_schema', 'Unsupported approval schema')
    basis = approved.get('basis')
    require(isinstance(basis, dict) and basis.get('kind') == 'reviewed-independent-baseline',
            'manifest_basis', 'Independent review basis is required')
    for key in ('contract_sha256', 'native_board_sha256', 'native_receipt_sha256',
                'source_binding_sha256', 'source_capture_sha256', 'drc_semantic_sha256'):
        require(valid_hash(approved.get(key)), 'manifest_hash', 'Invalid approved hash: ' + key)
    invariants = approved.get('native_receipt_invariants')
    require(isinstance(invariants, dict) and 'drc_sha256' not in invariants
            and valid_hash(invariants.get('project_sha256')),
            'manifest_receipt', 'Expected all approved receipt fields except the variable DRC hash')
    contract_path = safe_file(package, CONTRACT)
    contract_bytes = reads.read(contract_path)
    require(digest(contract_bytes) == approved.get('contract_sha256'),
            'contract_hash', 'Active contract differs from approved input manifest')
    physical = read_json(contract_bytes, CONTRACT).get('physical_board')
    require(isinstance(physical, dict), 'contract_board', 'Missing physical board contract')
    expected = physical.get('sha256')
    require(valid_hash(expected) and expected == approved.get('native_board_sha256'),
            'contract_board', 'Contract and approved native board disagree')
    for key in ('footprints', 'rear_vias'):
        require(type(physical.get(key)) is int and physical[key] >= 0,
                'contract_inventory', 'Invalid expected ' + key)
    copied_path = safe_file(package, physical.get('file'))
    copied = reads.read(copied_path)
    require(digest(copied) == expected, 'copied_board_hash', 'Copied mechanical board changed')
    copied_counts = inventory(copied)
    expected_counts = {key: physical[key] for key in copied_counts}
    require(copied_counts == expected_counts,
            'actual_inventory', 'Actual footprints/vias do not match active contract')
    actual_counts = None
    if not source_only:
        native_board, native_receipt = Path(native_board).absolute(), Path(native_receipt).absolute()
        require(native_board.resolve() != copied_path.resolve(), 'artifact_is_copy',
                'The required native artifact cannot be replaced by the package copy')
        require(native_board.parent.resolve() == native_receipt.parent.resolve(),
                'artifact_directory', 'Native board and receipt must come from one artifact directory')
        board_bytes = reads.read(native_board)
        receipt_bytes = reads.read(native_receipt)
        receipt = read_json(receipt_bytes, 'native receipt')
        actual = digest(board_bytes)
        require(actual == receipt.get('board_sha256'), 'artifact_hash', 'Actual native board does not match receipt')
        require(actual == expected, 'unreviewed_board', 'Native board needs deliberate enclosure rebinding')
        require(receipt.get('source_inputs_unchanged') is True
                and receipt.get('physical_checks') == 'passed on saved filled board'
                and receipt.get('fault_checks') == 'passed',
                'native_checks', 'Required saved-board/source/fault checks did not pass')
        # The original whole-receipt pin bound all native evidence. KiCad's DRC
        # timestamp/item representatives vary, changing only its report hash.
        # Keep every other field exact; verify the actual paired DRC hash and
        # semantic findings below, alongside the exact board/project identity.
        require(canonical({k: v for k, v in receipt.items() if k != 'drc_sha256'}) == canonical(invariants),
                'receipt_fields', 'Native receipt invariant fields changed')
        project_bytes = reads.read(native_board.with_suffix('.kicad_pro'))
        require(digest(project_bytes) == receipt['project_sha256'],
                'project_hash', 'Actual adjacent project differs from receipt')
        drc_bytes = reads.read(native_board.parent / 'drc.json')
        require(digest(drc_bytes) == receipt.get('drc_sha256'),
                'drc_hash', 'Actual adjacent DRC report differs from receipt')
        drc = read_json(drc_bytes, 'native DRC')
        drc_semantic = semantic_drc(drc, board_bytes)
        require(digest(canonical(drc_semantic).encode()) == approved['drc_semantic_sha256'],
                'drc_semantics', 'DRC findings/settings changed beyond proven report nondeterminism')
        require(len(drc['unconnected_items']) == receipt.get('remaining_connections')
                and dict(Counter(q['type'] for q in drc['violations'])) == receipt.get('retained_violations'),
                'drc_results', 'Actual DRC totals disagree with receipt')
        actual_counts = inventory(board_bytes)
        require(actual_counts == copied_counts, 'actual_inventory', 'Native/copy inventory differs')
    binding_path = safe_file(repo, BINDING)
    binding_bytes = reads.read(binding_path)
    require(digest(binding_bytes) == approved.get('source_binding_sha256'),
            'source_binding_hash', 'Current clean-main source binding changed')
    binding = read_json(binding_bytes, BINDING)
    files = binding.get('files')
    require(isinstance(files, dict) and bool(files), 'source_binding', 'Missing bound source input map')
    source = binding.get('source')
    require(isinstance(source, str) and source in files and valid_hash(files[source]),
            'source_binding', 'Capture is not bound')
    require(files[source] == approved.get('source_capture_sha256')
            and (source_only or receipt.get('source_sha256') == files[source]),
            'capture_receipt', 'Native receipt is for a different source capture')
    expected_files = runtime_files(repo) | set(files)
    manifest_files = approved.get('repo_files')
    require(isinstance(manifest_files, dict) and set(manifest_files) == expected_files,
            'input_coverage', 'Current runtime/source file inventory differs from approved manifest')
    for name in sorted(expected_files):
        wanted = manifest_files[name]
        require(valid_hash(wanted), 'manifest_hash', 'Invalid approved hash: ' + name)
        require(name not in files or files[name] == wanted,
                'source_binding', 'Approved/source binding hash differs: ' + name)
        require(digest(reads.read(safe_file(repo, name))) == wanted,
                'live_input_hash', 'Live repository input changed: ' + name)
    reads.unchanged()
    require(runtime_files(repo) | set(files) == expected_files,
            'input_changed', 'Runtime file inventory changed during checks')
    return {'passed': True, 'verification_mode': 'source-only' if source_only else 'native-artifact',
            'native_verification': not source_only,
            'status': ('Approved current source and copied board agree; no current native verification performed'
                       if source_only else 'Current native artifact matches independent approved inputs; not a fit or fabrication approval'),
            'native_board_sha256': None if source_only else actual,
            'native_receipt_sha256': None if source_only else digest(receipt_bytes),
            'native_drc_sha256': None if source_only else digest(drc_bytes),
            'native_drc_semantic_sha256': None if source_only else approved['drc_semantic_sha256'],
            'approved_manifest_sha256': digest(reads.read(package / MANIFEST)),
            'contract_sha256': digest(contract_bytes), 'source_capture_sha256': files[source],
            'source_binding_sha256': digest(binding_bytes), 'native_inventory': actual_counts,
            'copied_inventory': copied_counts,
            'repo_input_count': len(expected_files), 'inputs': {str(p): v for p, v in reads.files.items()},
            'limits': ['Historical native receipt binds capture only; the separate reviewed manifest pins the wider input closure.',
                       'Only DRC timestamp, finding/item order and verified same-net/layer exact-endpoint straight-segment representatives are normalized. No native topology is inferred.',
                       'All board-level vias are counted conservatively; this does not itself inspect layer exposure or frame contact.',
                       'The full source-bound enclosure checks and physical qualification remain required.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native-board', 'native-receipt', 'package', 'repo'):
        parser.add_argument('--' + name, required=name in ('package', 'repo'), type=Path)
    parser.add_argument('--source-only', action='store_true', help='Preview input guard only; never claims native verification')
    args = parser.parse_args()
    try:
        result = check(**vars(args))
    except (BindingError, OSError) as exc:
        print(json.dumps({'passed': False, 'error': getattr(exc, 'code', 'io_error'), 'detail': str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
