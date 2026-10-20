#!/usr/bin/env python3
"""Scoped SPICE checks of captured dump and latched-cutoff topologies.

No vendor models, motor measurements or thermal board model are present.
These experiments check polarity, feedback and sensitivity, not safe operation.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def run(name, template_name, replacements, measurements):
    template = (HERE / template_name).read_text()
    for key, value in replacements.items():
        template = template.replace('@' + key + '@', str(value))
    with tempfile.TemporaryDirectory(prefix='blind-regen-circuit-') as directory:
        folder = Path(directory)
        (folder / 'test.cir').write_text(template)
        process = subprocess.run(['ngspice', '-n', '-b', 'test.cir'], cwd=folder,
                                 capture_output=True, text=True, timeout=40)
        log = process.stdout + process.stderr
        if process.returncode or any(s in log.lower() for s in ['aborted', 'failed', 'timestep too small']):
            raise RuntimeError(name + ': ' + log[-2500:])
        values = {}
        for measure in measurements:
            match = re.search(r'^' + measure + r'\s*=\s*([-+\deE.]+)', log, re.M)
            if not match: raise RuntimeError(name + ' missing ' + measure + '\n' + log[-2000:])
            values[measure] = float(match[1])
        wave = (folder / 'wave.txt').read_text().splitlines()
        target = HERE / 'waves'; target.mkdir(exist_ok=True)
        # Keep compact deterministic traces for review; raw 1us samples are temporary.
        with (target / (name + '.csv')).open('w') as out:
            writer = csv.writer(out, lineterminator='\n')
            writer.writerow(wave[0].split())
            rows = wave[1:]
            stride = max(1, len(rows)//1200)
            writer.writerows(row.split() for row in rows[::stride])
            writer.writerow(rows[-1].split())
        values['simulated_through_s'] = float(wave[-1].split()[0])
    return dict(name=name, stimulus=replacements, measurements=values)


def main():
    if not shutil.which('ngspice'): raise SystemExit('ngspice required')
    results = []
    latch_measures = ['cold_ok_min', 'cold_gate_min', 'held_ok_max', 'held_gate_max',
                      'held_drive_min', 'reset_ok_min']
    for name, ramp_end in [('fast_ramp', .001001), ('normal_ramp', .002), ('slow_ramp', .041)]:
        result = run(name, 'latch.cir.in', {'RAMP_END': ramp_end}, latch_measures)
        m = result['measurements']
        assert m['cold_ok_min'] > 3 and m['cold_gate_min'] > 4.5
        assert m['held_ok_max'] < .4 and m['held_gate_max'] < .4
        assert m['held_drive_min'] > 2.5 and m['reset_ok_min'] > 3
        assert m['simulated_through_s'] == .16
        results.append(result)
    for name, current, cap, esr, lag in [
        ('dump_nominal', .5, 220e-6, .05, 30e-6),
        ('dump_stress', 2, 176e-6, .2, 100e-6),
        ('dump_late', 2, 176e-6, .2, 1e-3)]:
        result = run(name, 'dump.cir.in', {'CURRENT': current, 'CAP': cap, 'ESR': esr, 'LAG': lag},
                     ['peak_pack', 'dump_energy', 'idle_gate_max'])
        m = result['measurements']
        assert m['idle_gate_max'] < 1 and m['dump_energy'] > 0
        assert m['simulated_through_s'] == .05
        if name != 'dump_late': assert m['peak_pack'] < 18
        else: assert m['peak_pack'] > 18, 'Long-lag negative control should violate the design ceiling'
        results.append(result)
    output = dict(status='PASS of generic topology/sensitivity experiments; not physical validation',
                  models='Generic PNP; ideal threshold MOSFET switches; TLV hysteresis plus assumed RC lag; injected TMP302 hot signal',
                  template_sha256={name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                                   for name in ['dump.cir.in', 'latch.cir.in']},
                  results=results,
                  exclusions=['Actual IC propagation and startup', 'MOSFET switching SOA', 'motor energy and harness inductance',
                              'thermostat thermal transfer/delay', 'device spread/leakage and PCB contamination',
                              'sustained back-drive with open cutoff'])
    (HERE/'spice-results.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__': main()
