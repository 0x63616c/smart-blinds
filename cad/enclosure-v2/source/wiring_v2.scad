// Render-only chord decimation. Verification uses every centreline point in data/.
include <wire_arrays.scad>
module display_path(ps,d){for(j=[0:4:len(ps)-2])hull()for(k=[j,min(j+4,len(ps)-1)])translate(ps[k])sphere(d=d,$fn=8);}
module protected_fan(){for(i=[0:5])color([[.87,.28,.12],[.15,.16,.17],[.22,.57,.87],[.24,.7,.32],[.9,.64,.15],[.64,.32,.75]][i])display_path(pack_paths[i],1.85);}
module controller_motor_tails(){for(p=motor_paths)color([.85,.26,.12])display_path(p,1.85);}
module fixed_motor_tails(){for(p=motor_fixed_paths)color([.7,.22,.14])display_path(p,1.85);}
module encoder_cable(){color([.8,.64,.20])display_path(encoder_complete_path,2.5);}
module parked_cables(){for(p=parked_motor_paths)color([.7,.22,.14])display_path(p,1.85);color([.8,.64,.2])display_path(parked_encoder_path,2.5);}
