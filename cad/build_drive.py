#!/usr/bin/env python3
"""Build the mechanically retained drive fit prototype; no physical validation claim."""
import argparse, hashlib, json, subprocess, math
from pathlib import Path
from build import inspect_stl
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'source/drive_cartridge.scad'
PARTS=['base','rear_lower','front_lower','rear_upper','front_upper','bearing_block','bearing_retainer','wheel','guard']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(out,part,preview=False,offset=7):
    cmd=['openscad','-o',str(out),'-D',f'part="{part}"','-D',f'shaft_offset_z={offset}']
    if preview:cmd+=['--preview','--imgsize=1500,1100','--camera=0,0,0,20,0,25,500','--autocenter','--viewall','--projection=o','--colorscheme=Tomorrow']
    else:cmd+=['--export-format=binstl']
    r=subprocess.run(cmd+[str(SRC)],capture_output=True,text=True)
    if r.returncode or 'ERROR:' in r.stderr:raise RuntimeError(r.stderr)
    print(f'{part}: generated',flush=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--export',action='store_true');ap.add_argument('--render',action='store_true');a=ap.parse_args()
    files=[SRC,Path(__file__).resolve(),ROOT/'build.py'];snapshot={str(p.relative_to(ROOT)):sha(p) for p in files}
    gen=ROOT/'generated';dest=ROOT/'exports/drive-fit';dest.mkdir(parents=True,exist_ok=True)
    ev={'status':'Retained drive fit prototype, not enclosure release or load qualification','source_sha256':snapshot,'meshes':[], 'reference_enclosure_allocation_mm':[180,160,58], 'offset_scenarios_mm':[0,7], 'bought_part_dimensions':{'coupler_mm':[25,20,23],'bearing_mm':[6,14,5,15,1],'shaft_mm':[6,70],'shaft_flat_mm':5.5,'collar_mm':[6,19,9],'collar_screw_sweep_diameter_mm':22.6,'collar_boss_mm':[9,0.5],'spacer_stack_mm':[[6,8,2],[6,9,1]]}, 'limits':['Motor family geometry is provisional; exact mounting collar fits need replacement shims/brackets as required.','Purchased hardware envelopes are from manufacturer drawings; torque/current limits remain separate qualification.','No exhaustive collision, tolerance, thermal, fatigue, creep or physical acceptance claimed.']}
    checks={
      'cover_clearance_at_offset7_mm':58-2.4-(28+7+18.5),
      'motor_to_base_bolt_head_mm':math.hypot(15-2.75,28-13.2)-18.5,
      'collar_to_recessed_retainer_face_mm':124.5-(115+9),
      'coupler_to_collar_mm':115-(89+25),
      'wheel_to_guard_each_axial_mm':.5,
      'wheel_to_guard_radial_mm':(33-30)/2,
      'cord_channel_to_chord_inner_mm':(6/(2*math.sin(math.pi/12)))*math.cos(math.pi/12)-.5-10.4,
      'boss_to_coupler_mm':89-(76+6),
      'motor_shaft_coupler_insertion_mm':82+15.5-89,
      'driven_shaft_coupler_insertion_mm':89+25-106,
    }
    if any(v<=0 for v in checks.values()):raise RuntimeError(f'Failed nominal interface check: {checks}')
    ev['nominal_interface_clearances_mm']={k:round(v,3) for k,v in checks.items()}
    ev['interface_check_scope']='Named nominal interfaces only, not exhaustive CAD interference or tolerance proof.'
    if a.render:
        for p in ['assembly','exploded']:run(gen/f'drive-retained-{p}.png',p,True)
        run(gen/'drive-retained-offset0.png','assembly',True,0)
    if a.export:
        for p in PARTS:
            out=dest/f'{p}.stl';run(out,p);m=inspect_stl(out);ev['meshes'].append(m)
            if not m['closed_edge_mesh'] or m['connected_shells']!=1 or m['bounds_mm'][0][2]<-.01:raise RuntimeError(f'Invalid single print mesh: {m}')
    if snapshot!={str(p.relative_to(ROOT)):sha(p) for p in files}:raise RuntimeError('Sources changed during build; no evidence published')
    ev['source_snapshot_verified_unchanged']=True
    tmp=gen/'drive-verification.json.tmp';tmp.write_text(json.dumps(ev,indent=2)+'\n');tmp.replace(gen/'drive-verification.json')
    print('Drive source checks completed. Physical qualification remains open.')
if __name__=='__main__':main()
