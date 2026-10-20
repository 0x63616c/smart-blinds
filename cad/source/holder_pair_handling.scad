// Integrated handling/backing geometry. Included by compact_retained.scad.
// Temporary catches are never the installed electrical-safety restraint.
pair_side_clearance=0.4;
pair_seam_expansion=0.2;
pair_catch_release=1.3;
pair_partial_shell_release=8;
pair_shell_travel=35;
// Provisional handling-only catches and approved-land pair_backing study.
// Geometric candidate only; no clip strength, deflection or loaded-handling approval.
pair_backing_lands=[[15.8,31,23.8,81],[41.8,31,49.8,81],[67.8,31,75.8,81]];
module pair_arm_left_lower(delta=0){
 // A kinematic displacement envelope only, not a strain/force model.
 for(i=[0:23])hull()for(j=[i,i+1])let(t=1-j/24,dx=-delta*t*t*(3-2*t))
  box([3.4+dx,10+j,31.6],[1,.2,5]);
 box([3.4,32.5,31.6],[2.7,2.5,5]);
 translate([-delta,0,0]){
  box([3.4,9.5,28.8],[1,1,10.6]);
  // Only the small tip contacts the already reserved bare corner face.
  box([3.4,9.5,28.8],[1.9,1,.6]);box([5.3,9.5,28.8],[.6,1,1]);
  box([3.4,9.5,38.8],[1.9,1,.6]);box([5.3,9.5,38.4],[.6,1,1]);
 }
}
module pair_captures(delta=0){for(right=[false,true],upper=[false,true])
 translate([right?95.6:0,upper?116:0,0])
 mirror([right?1:0,0,0])mirror([0,upper?1:0,0])pair_arm_left_lower(delta);
}
module pair_backing(){
 for(r=pair_backing_lands){box([r[0],r[1],31.6],[r[2]-r[0],r[3]-r[1],1.9]);box([r[0],r[1],34.7],[r[2]-r[0],r[3]-r[1],1.9]);}
 // Cross-links are recessed 0.3 mm from each PCB. No new contact land is assumed.
 for(y=[31,79]){box([7.3,y,31.9],[81,2,1.6]);box([7.3,y,34.7],[81,2,1.6]);}
}
module pair_edge_stops(){for(y=[4.6,110.2])box([42,y,29.7],[5,1.2,8.8]);
 box([42,4.6,31.6],[5,2,5]);box([42,109.4,31.6],[5,2,5]);
}
module cassette_spacer(delta=0){union(){cassette_spacer_base();pair_backing();pair_captures(delta);pair_edge_stops();}}
module pair_boards(){carrier_board(30);carrier_board(36.6);}

// Shell insertion/release candidate. No installed retention qualification.
module pair_reflect(right=false,upper=false){
 translate([right?95.6:0,upper?116:0,0])
 if(right&&upper)mirror([1,0,0])mirror([0,1,0])children();
 else if(right)mirror([1,0,0])children();
 else if(upper)mirror([0,1,0])children();
 else children();
}
module pair_shell_reliefs(){
 for(r=[false,true],u=[false,true])pair_reflect(r,u){
  // Slot at the shell mating edge, leaving the lower/upper wall continuous.
  box([3.1,9.2,31.3],[1.9,26.1,5.6]);
  // Small corner-post scallop admits the handling hook, not its structural load.
  box([3.1,9.2,28.5],[3.1,1.6,11.2]);
 }
 // Registration stops; end walls remain closed away from the joining seam.
 for(y=[4.4,110])box([41.7,y,29.4],[5.6,1.6,9.4]);
}
module pair_expanded_outline(z,h,offset=0){
 hull()for(x=[8.8,86.8],y=[10,106])translate([x,y,z])cylinder(r=5.4+offset,h=h);
}
module pair_enlarged_cavity(z,h){
 hull()for(x=[8.8,86.8],y=[10,106])translate([x,y,z])cylinder(r=4+pair_side_clearance,h=h);
}
module pair_seam_band(front=false){
 z=front?34.3:29.8;h=front?4.1:4.2;
 difference(){pair_expanded_outline(z,h,pair_seam_expansion);pair_expanded_outline(z-.01,h+.02,-.05);}
}
module pair_fit_relief(){difference(){
 pair_enlarged_cavity(29.8,8.6);
 // Extend 0.02 mm inside the former wall boundary to avoid coincident sliver faces.
 hull()for(x=[8.8,86.8],y=[10,106])translate([x,y,29.7])cylinder(r=3.98,h=8.8);
}}
module cassette_rear(){difference(){union(){cassette_rear_base();pair_seam_band();}pair_shell_reliefs();pair_fit_relief();}}
module cassette_front(open_port=true){difference(){
 union(){cassette_front_base();pair_seam_band(true);}pair_shell_reliefs();pair_fit_relief();
 // Prewired pigtail enters from the shell seam before its existing tie bars close.
 if(open_port)box([90.7,99,34.2],[1.6,3,23.8]);
}}
module pair_fixed(){cassette_spacer();insulating_barrier();carrier_contents();}
module pair_clearance(){difference(){pair_fixed();
 // Intended board seating planes, checked independently by the retained builder.
 for(z=[30,38.2])box([0,0,z-.01],[116,175,.02]);
}}
module pair_release_tools(){
 // Conservative 3 mm insulated flat-ended pusher corridor from either side.
 for(r=[false,true],u=[false,true])pair_reflect(r,u)
  box([-8,8.7,28.3],[13.0,2.6,11.6]);
}
module pair_swept_shell(front=true,open_port=true){
 // Exact translational sweep with a 0.01 mm radial conservative enlargement.
 // Minkowski sum preserves cavities that a hull of the entire shell would fill.
 translate([-.005,-.005,front?0:-pair_shell_travel])minkowski(){
  if(front)cassette_front(open_port);else cassette_rear();cube([.01,.01,pair_shell_travel]);
 }
}
