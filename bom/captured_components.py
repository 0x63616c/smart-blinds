#!/usr/bin/env python3
"""Price the actual captured main/carrier components from dated catalog evidence.

This deliberately excludes missing design items, order rounding and manufacturing.
It never fetches live prices or treats overseas inventory as reserved SMT stock.
"""
from collections import Counter, defaultdict
from decimal import Decimal
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from generate_schematics import board_graph

BOARDS = {
    'main': 'hw/layouts/blind-main/main-test/main-test.kicad_pcb',
    'pack_primary': 'hw/layouts/blind-pack-primary/primary-test/primary-test.kicad_pcb',
    'pack_companion': 'hw/layouts/blind-pack-companion/companion-test/companion-test.kicad_pcb',
}


def component_catalog(props, where):
    """Exact picked-part fields own procurement; reject contradictory aliases."""
    code = props['LCSC']
    mpn = props['Partnumber']
    for name in ('lcsc_id', 'LCSC Part'):
        alias = props.get(name, '').strip()
        if alias and alias != code:
            raise ValueError(f'Conflicting supplier alias at {where}: {name}={alias}, LCSC={code}')
    return code, mpn


def build():
    evidence = {}
    for path in sorted((ROOT / 'bom').glob('*sourcing*.json')):
        data = json.loads(path.read_text())
        rows = data if isinstance(data, list) else data.get('parts', [])
        if isinstance(data, dict) and 'header' in data:
            rows = [*rows, data['header']]
        for row in rows:
            if 'price_breaks' not in row:
                continue
            code = row['lcsc']
            if code not in evidence or row['observed_utc'] > evidence[code][0]['observed_utc']:
                evidence[code] = row, str(path.relative_to(ROOT))
    counts = defaultdict(Counter)
    mpns = {}
    references = defaultdict(lambda: defaultdict(list))
    hashes = {}
    bare_features = {}
    for board, relative in BOARDS.items():
        path = ROOT / relative
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        bare_features[board] = []
        for ref, component in board_graph(path).items():
            props = component['properties']
            if 'exclude_from_bom' in component['attributes']:
                if props.get('LCSC') or props.get('Partnumber'):
                    raise ValueError(f'Purchased part unexpectedly excluded: {board}/{ref}')
                bare_features[board].append(dict(reference=ref, address=props['atopile_address'],
                                                  footprint=component['footprint']))
                continue
            code, mpn = component_catalog(props, f'{board}/{ref}')
            if code in mpns and mpns[code] != mpn:
                raise ValueError(f'Conflicting manufacturer part for {code}')
            mpns[code] = mpn; counts[code][board] += 1
            references[code][board].append(ref)
    lines = []
    totals = {2: Decimal(0), 8: Decimal(0)}
    for code in sorted(counts):
        row, source = evidence[code]
        if row['mpn'] != mpns[code] or row['currency'] != 'USD':
            raise ValueError(f'Sourcing identity/currency differs: {code}')
        breaks = row['price_breaks']
        if not isinstance(breaks, list) or not all(isinstance(b, dict) for b in breaks):
            raise ValueError(f'Unresolved catalog price data: {code}')
        line = dict(lcsc=code, mpn=mpns[code], counts=dict(counts[code]), references=dict(references[code]),
                    source=source, observed_utc=row['observed_utc'], url=row['url'], batches={})
        for units in totals:
            # Aggregate raw component demand across boards. A manufacturer's quote
            # may split procurement by assembly job; this does not assume it won't.
            qty = sum(counts[code].values()) * units
            prices = {Decimal(str(b['productPrice'])) for b in breaks
                      if b['startNumber'] <= qty and (b['endNumber'] == -1 or qty <= b['endNumber'])}
            if len(prices) != 1:
                raise ValueError(f'Missing/ambiguous price for {code} at {qty}')
            unit = prices.pop(); cost = unit * qty; totals[units] += cost
            line['batches'][str(units)] = dict(quantity=qty, unit_price_usd=str(unit), extension_usd=str(cost))
        lines.append(line)
    result = dict(status='Captured components only; not an order-ready BOM or manufacturing quote', currency='USD',
                  board_source_sha256=hashes, counts_by_board={b: sum(c[b] for c in counts.values()) for b in BOARDS},
                  non_purchased_circuit_features=bare_features,
                  unique_part_numbers=len(counts), batch_totals_usd={str(k):str(v) for k,v in totals.items()},
                  exclusions=['PCB fabrication, setup, feeders, stencil, X-ray and assembly',
                              'Procurement rounding, attrition, minimum quantities and per-job price differences',
                              'Cell/motor inventory, cable harnesses and any remaining uncaptured circuitry',
                              'Enclosure, fasteners, transmission, insulation, charger/cable, tools, shipping and tax'],
                  lines=lines)
    stream=io.StringIO(); writer=csv.writer(stream, lineterminator="\n")
    writer.writerow(['LCSC','MPN','Main qty','Primary pack qty','Companion pack qty','2 units qty','2 units USD','8 units qty','8 units USD','Catalog URL'])
    for line in lines:
        writer.writerow([line['lcsc'],line['mpn'],line['counts'].get('main',0),line['counts'].get('pack_primary',0),
                         line['counts'].get('pack_companion',0),
                         line['batches']['2']['quantity'],line['batches']['2']['extension_usd'],
                         line['batches']['8']['quantity'],line['batches']['8']['extension_usd'],line['url']])
    return {'bom/captured-components.json':json.dumps(result,indent=2)+'\n', 'bom/captured-components.csv':stream.getvalue()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    outputs=build()
    for name,contents in outputs.items():
        p=ROOT/name
        if args.check:
            if not p.exists() or p.read_text()!=contents:raise ValueError(f'Stale captured BOM: {name}')
        else:p.write_text(contents)
    d=json.loads(outputs['bom/captured-components.json'])
    print(json.dumps({k:d[k] for k in ['status','counts_by_board','unique_part_numbers','batch_totals_usd']},indent=2))

if __name__=='__main__':main()
