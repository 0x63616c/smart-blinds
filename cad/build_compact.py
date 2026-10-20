#!/usr/bin/env python3
"""Build/check the compact direct-support prototype; stdlib plus OpenSCAD."""
import argparse, hashlib, json, math, subprocess
from pathlib import Path
from build import inspect_stl
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'source/compact_direct.scad'
PARTS=['rear_lower','rear_upper','front_lower','front_upper','bearing_block','retainer','wheel','guard','plunger','button_guide']
COLLISIONS=['guard_wheel','wheel_bearing_block','pack_drive','pack_controller','pack_shell','button_guides','button_shell','antenna_usb_wires']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(out,part,mode='trimmed',preview=False):
    c=['openscad','-o',str(out),'-D',f'part="{part}"','-D',f'tail_mode="{mode}"']
    if preview:c+=['--preview','--imgsize=1400,1200','--camera=0,0,0,22,0,25,500','--autocenter','--viewall','--projection=o','--colorscheme=Tomorrow']
    else:c+=['--export-format=binstl']
    return c+[str(SRC)]
def run(out,part,mode='trimmed',preview=False,expect_empty=False):
    p=subprocess.run(command(out,part,mode,preview),capture_output=True,text=True)
    if 'ERROR:' in p.stderr or 'WARNING:' in p.stderr:raise RuntimeError(p.stderr)
    if expect_empty:
        if p.returncode and 'Current top level object is empty' in p.stderr:
            if out.exists():out.unlink()
            print(f'{part}/{mode}: no nominal intersection',flush=True);return
        raise RuntimeError(f'Unexpected intersection or failed check {part}: {p.stderr}')
    if p.returncode or 'ERROR:' in p.stderr:raise RuntimeError(p.stderr)
    print(f'{part}/{mode}: generated',flush=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--render',action='store_true');ap.add_argument('--export',action='store_true');ap.add_argument('--intersections',action='store_true');a=ap.parse_args()
    inputs=[SRC,ROOT/'source/compact_buttons.scad',Path(__file__).resolve(),ROOT/'build.py'];snapshot={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    gen=ROOT/'generated';dest=ROOT/'exports/compact-direct-fit';dest.mkdir(parents=True,exist_ok=True)
    ev={'status':'Compact shared-shaft prototype; gearbox radial-load and button-travel qualification required', 'source_sha256':snapshot, 'meshes':[], 'nominal_intersections':[], 'options':[], 'front_button_interface':{'switch_mpn':'TS-1081S-AC01326','switch_body_mm':[3.5,3,1.3],'actuator_axis_above_pcb_mm':.8,'free_gap_nominal_mm':.15,'mechanical_stop_travel_nominal_mm':.4,'nominal_maximum_switch_displacement_mm':.25,'button_collision_test_travel_mm':.39,'limits':'Nominal geometry only; printed tolerance stack, no-preload, actuation and allowable switch overtravel require qualification.'}}
    for mode,gap,tail in [('trimmed',5,1.5),('untrimmed',12,4.5)]:
        dims=[115,174,66+gap];barrier_clearance=(gap-1-2*tail)/2
        ev['options'].append({'mode':mode,'case_mm':dims,'wall_area_cm2':dims[0]*dims[1]/100,'volume_cm3':math.prod(dims)/1000,'opposed_board_gap_mm':gap,'maximum_tail_and_fillet_protrusion_mm':tail,'barrier_mm':1,'clearance_each_side_of_barrier_mm':barrier_clearance})
        if barrier_clearance<.5:raise RuntimeError('Insufficient declared barrier clearance')
        if a.intersections:
            for c in COLLISIONS:
                run(dest/f'collision-{c}-{mode}.stl','collision_'+c,mode,expect_empty=True)
                ev['nominal_intersections'].append({'pair':c,'mode':mode,'intersection':'empty'})
    if a.render:
        for part in ['assembly','closed','exploded','drive','buttons']:run(gen/f'compact-direct-{part}.png',part,preview=True)
        run(gen/'compact-direct-untrimmed.png','assembly','untrimmed',True)
    if a.export:
        for part in PARTS:
            path=dest/f'{part}.stl';run(path,part);m=inspect_stl(path);ev['meshes'].append(m)
            if not m['closed_edge_mesh'] or m['connected_shells']!=1 or m['bounds_mm'][0][2]<-.01:raise RuntimeError(f'Invalid single print mesh {m}')
    if snapshot!={str(p.relative_to(ROOT)):sha(p) for p in inputs}:raise RuntimeError('Sources changed during build; no evidence published')
    ev['source_snapshot_verified_unchanged']=True
    ev['limits']=['Only named nominal intersections are tested. Holes, tolerances, strength, heat, insulation, RF and function require further work.','Pack bars, case and controller support are allocation geometry, not fully fastened manufacturing parts.','Motor shaft dimensions are seller illustration; shaft fit and radial load capability remain unverified.','Trimmed version requires quoted or manual trimming with inspection; no free JLC trimming service is assumed.']
    tmp=gen/'compact-direct-verification.json.tmp';tmp.write_text(json.dumps(ev,indent=2)+'\n');tmp.replace(gen/'compact-direct-verification.json')
    print('Compact source checks completed; no physical qualification claimed.')
if __name__=='__main__':main()
