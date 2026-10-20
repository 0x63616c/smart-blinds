// Retained compact enclosure, original continuation of the compact fit study.
// Units mm; X across wall, Y upwards, Z away from wall. Default is trimmed pins.
// Motor geometry and PCB placements remain provisional. No physical qualification.
use <compact_direct.scad>
part="assembly";
$fn=40;
W=115; H=174; D=71;
pcb_x=99; pcb_y=3; pcb_z=8; pcb_t=1.6; pcb_h=68.5; pcb_depth=54;
include <retained_buttons.scad>
case_screws=[[12,120],[103,120],[12,166],[103,166]];
wall_screws=[[45,103],[106,107.5],[45,166]];
pack_holes=[[8.8,10],[86.8,10],[8.8,106],[86.8,106]];
pack_mounts=[[77,116]];
pack_cleats=[[32.8,11.5],[58.8,11.5]];
service_slide=2.5; service_forward=72; mount_tool_d=8;
cleat_stem=[4,3,4.8]; cleat_head=[8,4,1.6]; cleat_head_z=[7.8,9.4];
catch_floor_z=[3.4,7.5]; pocket_roof_z=[10.4,12];
pocket_slot_width=4.6; pocket_entry_y=[6.7,11.3];
pack_header_origin=[100.6,58.02,53.675];
pack_free_y=[76.09,88.79]; pack_bend_centre=[93.89,88.79]; pack_bend_r=11.71;
encoder_transition_y=46.5; encoder_bundle=2.2;
encoder_board_corridor=[46,40,51,45.1];
controller_mounts=[[102.5,9],[102.5,97]];
board_origin=[4.8,6]; board_size=[86,104];
// Drawing upper rim envelope plus an independent fit gap. These are capture
// stops, not a claim of preload or solder unloading across holder tolerances.
holder_rim_height=16.1; holder_contact_gap=0.2;
holder_foot_width=3; holder_foot_length=1.6;
holder_foot_x=[-9.5,6.5]; holder_foot_y=[15.6,94.6];
wall_head_ceiling=8.2; wall_pocket_roof=1.2;
wall_head_pocket_y=[98.5,105]; // ±2 mm wall slot plus 2.5 mm cassette release.
spacer_relief_xy=[13.3,99.5,69,4]; // Allowed track band plus 0.5 mm edge margin.
spacer_relief_depth=0.3;
wire_od=1.85; // Molex2147561061 maximum; no clamp-grip diameter inferred.
wire_zs=[45.5,47.7,49.9,52.1,54.3,56.5];
module box(p,s){translate(p)cube(s);}
module zz(p,d,h){translate(p)cylinder(d=d,h=h);}
module rr(p,s,r=4){translate(p)rounded(s,r);}
module path_box(points,width=3){for(i=[0:len(points)-2])hull()for(p=[points[i],points[i+1]])translate(p)cube([width,width,width],center=true);}
module hex_hole(p,h=2.8,d=6.6){translate(p)cylinder(d=d,h=h,$fn=6);}
module case_pillar(p){difference(){
 zz([p[0],p[1],3],8,D-8.3);
 zz([p[0],p[1],D-13.2],3.4,8);
 hex_hole([p[0],p[1],D-10.1]);
 box([p[0]-3.3,p[1],D-10.1],[6.6,5,2.8]);
}}
// Two integral load-bearing cleats; the cassette slides down 2.5 mm to capture.
module cassette_cleats(){for(p=pack_cleats){
 box([p[0]-cleat_stem[0]/2,p[1]-cleat_stem[1]/2,2.9],
  [cleat_stem[0],cleat_stem[1],cleat_stem[2]+.1]);
 box([p[0]-cleat_head[0]/2,p[1]-cleat_head[1]/2,cleat_head_z[0]],cleat_head);
}}
module catch_pocket_solids(){for(p=pack_cleats)
 box([p[0]-6.1,4.6,4.5],[12.2,12.2,pocket_roof_z[1]-4.5]);}
module catch_pocket_voids(){for(p=pack_cleats){
 // Closed roof faces the cell cavity. Only the rear entry/slot is open.
 box([p[0]-4.7,5.6,catch_floor_z[1]],[9.4,9.8,pocket_roof_z[0]-catch_floor_z[1]]);
 box([p[0]-4.3,pocket_entry_y[0],catch_floor_z[0]-.2],
  [8.6,pocket_entry_y[1]-pocket_entry_y[0],catch_floor_z[1]-catch_floor_z[0]+.3]);
 box([p[0]-pocket_slot_width/2,9,catch_floor_z[0]-.2],
  [pocket_slot_width,4.3,catch_floor_z[1]-catch_floor_z[0]+.3]);
}}
module retained_backplate(){difference(){union(){
 rounded([W,H,3]);
 box([5,114,3],[99,55,3]);
 for(p=case_screws)case_pillar(p);
 cassette_cleats();
 // Wall washers sit on reinforced pads; load path is independent of the cover.
 for(p=wall_screws)zz([p[0],p[1],0],12,6);
 }
 for(p=wall_screws){
  hull()for(dy=[-2,2])zz([p[0],p[1]+dy,-.1],4.8,6.2);
  hull()for(dy=[-2,2])zz([p[0],p[1]+dy,3],10,3.1);
 }
 // Drive fixtures retain the existing replaceable clamps and bearing pod.
 for(p=[[25,127],[25,157],[65,127],[65,157],[95.5,128],[95.5,156]]){
  zz([p[0],p[1],-.1],3.4,6.2);hex_hole([p[0],p[1],-.1]);
 }
 for(p=concat(pack_mounts,controller_mounts)){
  zz([p[0],p[1],-.1],3.4,6.6);hex_hole([p[0],p[1],.2],2.6);
 }
 // Do not trap the upper cassette ear inside the raised motor deck.
 box([73,111.3,3],[8.3,11,3.5]);
 // The full wall-slot adjustment pocket also needs its 2.5 mm release sweep.
 box([37.2,113.8,3],[15.6,1.5,3.1]);
}}
module retained_cover(){difference(){union(){
 difference(){
  rr([0,0,3.4],[W,H,D-3.4],12);
  rr([2.4,2.4,3.3],[W-4.8,H-4.8,D-5.7],9.6);
  // Rear-open chain slot lets the cover slide forward off a continuous chain.
  box([83.2,H-2.5,3.3],[7,3,47.1]);
  box([97.5,-.1,30],[10,3,15]);
  for(y=button_ys)zz([button_x,y,D-2.5],10.3,2.6);
 }
 front_guides();
 // Bury boss ends inside the front skin; no coincident exterior faces.
 for(p=case_screws)zz([p[0],p[1],D-5],8,4.8);
 }
 for(p=case_screws){zz([p[0],p[1],D-5.1],3.4,5.2);zz([p[0],p[1],D-3],6.2,3.1);}
 for(y=[20,60])zz([button_x,y,D-6],2.4,4.4);
}}
module carrier_board(z){difference(){
 rr([4.8,6,z],[86,104,1.6],4);
 for(p=pack_holes)zz([p[0],p[1],z-.1],3.4,1.8);
}}
module cassette_outline(z,h){rr([3.4,4.6,z],[88.8,106.8,h],5.4);}
module cassette_inner(z,h){rr([4.8,6,z],[86,104,h],4);}
module pack_ear(p){hull(){zz([p[0],p[1],3],6,3.4);box([p[0]-3,109,3.4],[6,2,3]);}}
module holder_end_combs(front=false){
 // Integral ribs and four plastic-only contact feet per holder. Their end zones
 // avoid the metal contact strip and cell ends in the supplier family model.
 contact_z=front?38.2+holder_rim_height+holder_contact_gap:30-holder_rim_height-holder_contact_gap;
 for(y=holder_foot_y){
  box([7.0,y,front?62.9:4.5],[77.6,holder_foot_length,3.1]);
  for(x=[19.8,45.8,71.8],dx=holder_foot_x)
   box([x+dx,y,front?contact_z:4.5],
       [holder_foot_width,holder_foot_length,front?66-contact_z:contact_z-4.5]);
 }
}
module wall_head_pocket_outer(){hull()for(y=wall_head_pocket_y)
 zz([45,y,4.5],15,wall_head_ceiling+wall_pocket_roof-4.5);}
module wall_head_pocket_void(){hull()for(y=wall_head_pocket_y)
 zz([45,y,3.2],12.6,wall_head_ceiling-3.2);}
module cassette_rear(){difference(){union(){
 difference(){cassette_outline(3.4,30.6);cassette_inner(4.6,29.5);}
 // These compression posts carry board/holder forces to the cassette floor.
 for(p=pack_holes)zz([p[0],p[1],4.5],7.6,25.5);
 // End lands support FR4 adjacent to (not on) the contact solder joints.
 difference(){
  box([8.8,8,28.5],[78,3,1.5]);
  for(x=[19.8,45.8,71.8])box([x-4,7.9,28.4],[8,3.2,1.7]);
 }
 box([8.8,100,28.5],[78,3,1.5]);
 // Join the interrupted middle support lands to the lower side wall.
 for(x=[32.8,58.8])box([x-1.6,5.5,28.5],[3.2,2.7,1.5]);
 for(p=pack_mounts)pack_ear(p);
 catch_pocket_solids();
 holder_end_combs(false);
 for(p=pack_holes)zz([p[0],p[1],3],7.6,.5);
 // A closed raised pocket clears the wall-screw pad below the upper end band.
 wall_head_pocket_outer();
 }
 wall_head_pocket_void();
 catch_pocket_voids();
 for(p=pack_holes){
  zz([p[0],p[1],4],3.4,30.1);hex_hole([p[0],p[1],4.6]);
  box([p[0]-3.3,p[1]<50?4.5:106,4.6],[6.6,p[1]<50?5.5:5.5,2.8]);
 }
 for(p=pack_mounts)zz([p[0],p[1],2.9],3.4,3.6);
}}
module spacer_frame(z,h){difference(){
 union(){
  difference(){cassette_inner(z,h);rr([7.8,9,z-.1],[80,98,h+.2],2);}
  for(p=pack_holes)zz([p[0],p[1],z],7.6,h);
  for(y=[10.5,100.5])box([8.8,y,z],[78,2,h]);
 }
 for(p=pack_holes)zz([p[0],p[1],z-.1],3.4,h+.2);
 // Four permanently enclosed raw-group strap channels, not a user connector.
 for(x=[20,38,56,74])box([x-2,104,z-.1],[4,4,h+.2]);
}}
module cassette_spacer(){difference(){
 spacer_frame(31.6,5);
 // 1.2 mm slot captures a separate 1 mm unclad insulating sheet.
 rr([6.1,7.3,33.5],[83.4,101.4,1.2],3);
 // Companion B.Cu covered tracks may cross beneath its outward F.Cu support.
 // Keep corner posts and the upper end frame; no pad/via/tail is allowed here.
 rr([spacer_relief_xy[0],spacer_relief_xy[1],31.59],
    [spacer_relief_xy[2],spacer_relief_xy[3],spacer_relief_depth+.01],.5);
}}
module insulating_barrier(){difference(){
 rr([6.3,7.5,33.6],[83,101,1],3);
 for(p=pack_holes)zz([p[0],p[1],33.5],8,1.2);
 for(x=[20,38,56,74])box([x-2.3,103.8,33.5],[4.6,5,1.2]);
}}
module cassette_front(){difference(){union(){
 difference(){cassette_outline(34.3,33);cassette_inner(34.2,31.7);}
 for(p=pack_holes)zz([p[0],p[1],38.2],7.6,27.8);
 // Smooth ribs retain cells without pushing on their wrapper corners.
 for(y=[34,78])box([4.8,y,63.9],[86,6,2.1]);
 holder_end_combs(true);
 // Keep the upper component/header band free; the four posts support its corners.
 difference(){box([8.8,8,38.2],[78,3,1.5]);box([13.8,7.9,38.1],[68,3.2,1.7]);}
 // Raised inline-motor connector tray, outside the closed raw-tap cavity.
 // It joins the upper side wall; straps release before cassette servicing.
 box([44,110.9,52],[28.5,15.1,1.7]);
 // Integral strain-retention bars; two cable ties retain the protected pigtail.
 // Bars attach to the lid independently of the contact solder joints.
 for(x=[73,79])box([x,101.5,43],[3,3,23]);
 }
 for(p=pack_holes){zz([p[0],p[1],38.1],3.4,29.3);zz([p[0],p[1],64.3],6.2,3.1);}
 // Two strap stations around the inline motor connector reservation.
 for(x=[50.5,68.5],y=[112.1,123.6])box([x-1.5,y,51.9],[3,1.7,1.9]);
 // Six protected wires in one vertical row pass below the upper corner post.
 box([90.7,99,44],[1.6,3,14]);
}}
module connector_envelope(mated=true){
 // Dual-row Micro-Fit430450600 header; drawing datum matches interface JSON.
 color([.13,.14,.15])box([pack_header_origin[0],pack_header_origin[1]+.51,pack_header_origin[2]-6.325],[8.77,9.91,12.65]);
 color([.6,.62,.64])box([pack_header_origin[0],pack_header_origin[1]-1.82,pack_header_origin[2]-3.325],[1,2.33,6.65]);
 if(mated)color([.4,.41,.42,.6]){
  // Clearance envelope includes housing tolerances and its latch excursion.
  box([pack_header_origin[0],pack_header_origin[1]+10.42,pack_header_origin[2]-5.1],[11.35,7.65,10.2]);
  // Receptacle's below-plane interference is kept beyond the PCB upper edge.
  box([99.8,pack_header_origin[1]+15.69,pack_header_origin[2]-5.1],[.8,2.38,10.2]);
 }
}
module pack_wire_fan(){for(z=wire_zs)translate([72,100.5,z])ax(wire_od,20.2);}
module pack_ties(){
 // Model the wrap region as polymer only, not conductive material.
 color([.13,.14,.15])for(x=[74.5,80.5])difference(){
  box([x-1.25,99.3,42.7],[2.5,5.5,17.6]);
  box([x-1.35,99.7,43.1],[2.7,4.7,16.8]);
 }
}
module carrier_contents(){
 color([.07,.075,.08]){carrier_board(30);carrier_board(36.6);}
 for(x=[19.8,45.8,71.8]){translate([x,14,30])mirror([0,0,1])holder();translate([x,14,38.2])holder();}
 color([.9,.48,.15,.6]){box([16,101,38.2],[20,8,3]);box([54,101,38.2],[28,8,3]);}
 color([.65,.3,.1])for(x=[20,38,56,74])box([x-1,105,31.6],[2,2,5]);
 color([.1,.1,.1])pack_wire_fan();
}
module pack_fasteners(include_mounts=true){color([.6,.62,.64]){
 for(p=pack_holes){zz([p[0],p[1],4.3],3,60);zz([p[0],p[1],64.3],5.5,3);hex_hole([p[0],p[1],4.7],2.4,6.35);}
 if(include_mounts)for(p=pack_mounts){zz([p[0],p[1],.4],3,6);zz([p[0],p[1],6.4],5.5,3);}
}}
module cassette(explode=0,show_front=true,mounting=true){
 color([.86,.88,.84])cassette_rear();carrier_contents();
 color([.8,.82,.77])cassette_spacer();color([.77,.67,.4])insulating_barrier();
 if(show_front)translate([0,0,explode])color([.9,.91,.88])cassette_front();
 if(show_front&&explode==0){pack_ties();color([.13,.14,.15])inline_motor_ties();}
 if(explode==0)pack_fasteners(mounting);
}
module controller_frame(){difference(){union(){
 // Open-backed edge frame. Metal clamps sit beyond the antenna's Z keepout.
 box([96.2,4,6],[2.8,76,2]);
 for(y=[4,64])box([96.2,y,62],[2.8,y==4?12:16,2]);
 for(y=[4,78])box([96.2,y,6],[2.8,2,58]);
 for(y=[12,67.5])box([96.2,y-4,61],[2.8,8,7.4]);
 for(p=controller_mounts){hull(){zz([p[0],p[1],3],7,3.3);box([96.2,p[1]-3,3],[2.8,6,3.3]);}
  box([96.2,p[1]-3,3],[2.8,6,5]);}
 // Back rail connects the upper mounting foot without metal near the antenna.
 box([96.2,78,6],[2.8,24,2]);
 }
 for(p=controller_mounts){zz([p[0],p[1],2.9],3.4,3.5);translate([p[0],p[1],4.3])cylinder(d1=3.4,d2=6.4,h=2.1);}
 for(y=[12,67.5]){translate([96.1,y,65.5])ax(2.9,3);translate([96.1,y,65.5])rotate([0,90,0])cylinder(d=5.9,h=2,$fn=6);}
}}
module controller_clip(){difference(){union(){
 // Front lip overlaps only the 1 mm board-edge land, with no board hole.
 box([100.6,-4,61],[2,8,7.4]);
 // A rounded tongue keys into the board-edge notch, reacting USB axial loads.
 box([99,-.5,61],[1.7,1,1]);
 for(y=[-.5,.5])translate([99,y,61.5])ax(1,1.7);
 }
 translate([100.5,0,65.5])ax(2.9,2.2);
}}
module controller_notches(){for(y=[12,67.5])hull()for(yy=[y-.6,y+.6],z=[61.4,62.1])translate([98.9,yy,z])ax(1.2,1.8);}
module controller_pcb(){difference(){union(){box([99,3,8],[1.6,68.5,54]);box([99,.46,32.3],[1.6,2.54,10.4]);}controller_notches();}}
// HRO TYPE-C-31-M-12: NPTH line to mouth6.25; NPTH to recommended edge5.79.
module retained_usb(){box([100.6,0,33.03],[3.26,7.35,8.94]);}
module retained_antenna_keepout(){box([85.6,56.5,-1.5],[33.1,36.5,48]);}
module retained_controller(){
 color([.83,.85,.81])controller_frame();
 color([.07,.075,.08])controller_pcb();
 // A 9 mm component envelope admits the 7.7 mm nominal bulk capacitor.
 color([.1,.6,.68,.35])difference(){
  box([100.6,10,8],[9,46.5,54]);
  for(y=[12,67.5])box([100.5,y-4,60],[10,8,3]);
  box([100.5,52.5,13.5],[10,26,18]);
 }
 color([.65,.67,.68])box([100.6,52.5,13.5],[3.1,19,18]);
 color([.2,.4,.8,.7])box([100.6,71.5,13.5],[1,6.5,18]);
 color([.7,.72,.72])retained_usb();front_button_hardware();
 connector_envelope();color([.22,.23,.24])signal_headers();
 color([.86,.88,.84])for(y=[12,67.5])translate([0,y,0])controller_clip();
 color([.6,.62,.64])for(y=[12,67.5]){translate([94.6,y,65.5])ax(2.5,8);translate([102.6,y,65.5])ax(4.5,2.5);}
}
// The old study's duplicate deck ends at Z6; omit its zero-thickness top face.
module retained_drive(){translate([0,2,0])intersection(){drive();box([0,110,6.001],[115,94,65]);}}
module pack_cable_envelopes(){
 // 12.7 mm relaxed wire region after the dual-row housing; no early bend/tie.
 box([102.85,pack_free_y[0],49.425],[5.5,pack_free_y[1]-pack_free_y[0],8.5]);
 // An 11.71 mm nominal radius bend turns into the cassette side port. The fan widens
 // only once it is beyond the radio keepout in Y.
 for(i=[0:11])hull()for(j=[i,i+1])let(a=j*90/12,
  x=pack_bend_centre[0]+pack_bend_r*cos(a), y=pack_bend_centre[1]+pack_bend_r*sin(a),
  fan=max(0,(y-97)/(100.5-97)), z=53.675-2.675*fan,
  height=8.5+4.9*fan, width=5.5-3.65*fan,
  sx=width*cos(a)+.4, sy=width*sin(a)+.4)box([x-sx/2,y-sy/2,z-height/2],[sx,sy,height]);
 // One vertical row of insulated wires passes between the holder end and post.
 box([72,99.575,44.575],[pack_bend_centre[0]-72,1.85,12.85]);

}
module inline_motor_envelope(){box([46.8,114.75,53.9],[25.5,8.5,11.2]);}
module inline_motor_ties(){for(x=[50.5,68.5])difference(){
 box([x-1.25,112.2,51.7],[2.5,13,13.8]);
 box([x-1.35,112.6,52.1],[2.7,12.2,13]);
}}
module signal_headers(){
 // PicoBlade body/mated allocations; actual PCB footprints belong to electronics.
 box([100.6,41.225,48.8],[3.6,10.55,5.2]);
 box([100.6,49,33.85],[3.6,5.2,9.3]);
}
module motor_cables(){
 inline_motor_envelope();
 for(i=[0:1])let(z=58.4+2.2*i,run_z=61.8+2.2*i){
  // Straight relaxed regions, 12.7 mm at each end of the inline pair.
  path_box([[34.1,119,z],[46.8,119,z]],wire_od);
  path_box([[72.3,119,z],[85,119,z]],wire_od);
  for(a=[0:7])hull()for(b=[a,a+1])let(t=b*90/8)
   translate([85+9.2*sin(t),109.8+9.2*cos(t),z])sphere(d=wire_od,$fn=12);
  path_box([[94.2,109.8,z],[94.2,105,run_z],[94.2,43,run_z],
   [94.2,37.5,50+6*i],[100.6,37.5,50+6*i]],wire_od);
  path_box([[34.1,119,z],[28,113.7,z],[22,113.7,59.5]],wire_od);
 }
}
module encoder_cables(){
 // 2.2 mm square four-wire allocation; actual 28 AWG cable OD/bend remains open.
 path_box([[103,encoder_transition_y,54],[110,encoder_transition_y,57],[110,encoder_transition_y,66.2],
  [110,113.1,66.2],[28,113.1,66.2],[22,113.7,59.5]],encoder_bundle);
}
module home_cable_allocation(){
 // Deliberately ends in the upper service bay: reference-sensor mount not frozen.
 path_box([[103,49,38.5],[110,49,38.5],[110,49,63.7],[110,110,63.7]],2.2);
}
module motor_rear_bundle(){
 // The two power and four encoder wires share one bundled reservation here,
 // rather than counting overlapping single-wire paths as separate free space.
 // 4.2 mm square bundle fits the narrow bay with only0.2 mm nominal Y margins.
 path_box([[22,113.7,59.5],[5.8,113.7,59.5],[5.8,113.7,28],[5.8,134,28]],4.2);
}
module cable_envelopes(){pack_cable_envelopes();motor_cables();encoder_cables();home_cable_allocation();motor_rear_bundle();}
module mounting_hardware(){color([.6,.62,.64]){
 for(p=case_screws){zz([p[0],p[1],58],3,10);zz([p[0],p[1],68],5.5,3);hex_hole([p[0],p[1],61],2.4,6.35);}
 for(p=controller_mounts){zz([p[0],p[1],.3],3,4.3);translate([p[0],p[1],4.6])cylinder(d1=3,d2=6,h=1.7);}
}}
module cassette_service_envelope(slide=0,forward=0){
 // Contains the entire closed cassette, boards/cells, closure heads and tray.
 // Linear expansion is a continuous conservative sweep along one axis.
 box([3.4,4.6+slide,3],[88.8,106.8,64.3+forward]);
 hull()for(y=wall_head_pocket_y)zz([45,y+slide,3],15,6.4+forward);
 for(p=pack_mounts)box([p[0]-3,109+slide,3],[6,10,3.4+forward]);
 box([44,110.9+slide,52],[28.5,15.1,1.7+forward]);
 box([46.8,114.75+slide,53.9],[25.5,8.5,11.2+forward]);
}
module cassette_slide_envelope(){
 box([3.4,4.6,3],[88.8,106.8+service_slide,64.3]);
 hull()for(y=[wall_head_pocket_y[0],wall_head_pocket_y[1]+service_slide])zz([45,y,3],15,6.4);
 for(p=pack_mounts)box([p[0]-3,109,3],[6,10+service_slide,3.4]);
 box([44,110.9,52],[28.5,15.1+service_slide,1.7]);
 box([46.8,114.75,53.9],[25.5,8.5+service_slide,11.2]);
}
module assembly(){color([.84,.86,.82])retained_backplate();cassette(0,false);retained_drive();retained_controller();color([.7,.15,.1,.7])cable_envelopes();mounting_hardware();}
if(part=="backplate")retained_backplate();
else if(part=="cover")translate([0,0,D])rotate([180,0,0])retained_cover();
else if(part=="cassette_rear")translate([0,0,-3])cassette_rear();
else if(part=="cassette_front")translate([0,0,67.3])rotate([180,0,0])cassette_front();
else if(part=="cassette_spacer")translate([0,0,-31.6])cassette_spacer();
else if(part=="barrier")translate([0,0,-33.6])insulating_barrier();
else if(part=="barrier_outline")projection(cut=true)translate([0,0,-34.1])insulating_barrier();
else if(part=="controller_frame")translate([0,0,-96.2])rotate([0,-90,0])controller_frame();
else if(part=="button_plunger")translate([0,0,71])rotate([180,0,0])translate([-button_x,-28,0])front_plunger(28);
else if(part=="button_face")translate([0,0,72.2])rotate([180,0,0])translate([-button_x,-28,0])button_face(28);
else if(part=="button_guide")translate([-button_x+4.6,-17,-63.1])button_guide_bar();
else if(part=="buttons")button_section();
else if(part=="controller_clip")translate([0,0,102.6])rotate([0,90,0])controller_clip();
else if(part=="cassette")cassette(25);
else if(part=="closed"){color([.95,.96,.94])retained_cover();color([.84,.86,.82])retained_backplate();front_button_hardware();translate([0,2,0])chain();mounting_hardware();}
else if(part=="exploded"){assembly();translate([0,0,85])color([.9,.91,.88])cassette_front();translate([135,0,0])color([.95,.96,.94])retained_cover();}
else if(part=="collision_cassette_contents")intersection(){carrier_contents();difference(){union(){cassette_rear();cassette_front();cassette_spacer();insulating_barrier();}for(z=[30,31.6,36.6,38.2])box([0,0,z-.01],[116,175,.02]);}}
else if(part=="collision_cassette_controller")intersection(){cassette();retained_controller();}
else if(part=="collision_cassette_drive")intersection(){cassette();retained_drive();}
else if(part=="collision_cassette_cover")intersection(){cassette();retained_cover();}
else if(part=="collision_case_pillars_drive")intersection(){for(p=case_screws)case_pillar(p);retained_drive();}
else if(part=="collision_controller_cover")intersection(){union(){controller_frame();controller_pcb();retained_usb();connector_envelope();for(y=[12,67.5])translate([0,y,0])controller_clip();}retained_cover();}
else if(part=="collision_connector_pcb")intersection(){connector_envelope();intersection(){controller_pcb();box([99.01,-1,0],[1.58,80,70]);}}
else if(part=="collision_connector_frame")intersection(){connector_envelope();union(){controller_frame();for(y=[12,67.5])translate([0,y,0])controller_clip();}}
else if(part=="collision_controller_buttons")intersection(){union(){controller_frame();controller_pcb();for(y=[12,67.5])translate([0,y,0])controller_clip();}union(){button_guide_bar();for(y=button_ys)front_plunger(y);}}
else if(part=="collision_button_guides")intersection(){
 union(){retained_cover();button_guide_bar();}
 union(){for(y=button_ys){front_plunger(y,button_travel-.01);button_adjuster(y,button_travel-.01);}}
}
else if(part=="collision_button_adjuster")intersection(){
 union(){front_plunger(28);button_face(28);}
 union(){for(tip=[62.5,62.9])button_adjuster(28,0,tip);}
}
else if(part=="collision_signal_header_buttons")intersection(){signal_headers();union(){button_guide_bar();for(y=button_ys)front_plunger(y);}}
else if(part=="collision_connector_buttons")intersection(){
 connector_envelope();
 union(){front_button_hardware();for(y=button_ys)box([100,y-2.4,58.6],[2.1,4.8,3.95]);}
}
else if(part=="collision_signal_wires_switches")intersection(){
 union(){encoder_cables();home_cable_allocation();}
 union(){for(y=button_ys){front_switch(y);box([100,y-2.4,58.6],[2.1,4.8,3.95]);}}
}
else if(part=="collision_wiring_controller")intersection(){cable_envelopes();union(){controller_frame();button_guide_bar();for(y=[12,67.5])translate([0,y,0])controller_clip();}}
else if(part=="collision_controller_keys")intersection(){controller_pcb();intersection(){union(){controller_frame();for(y=[12,67.5])translate([0,y,0])controller_clip();}box([99.01,2,7],[1.58,77,56]);}}
else if(part=="collision_rf_metal")intersection(){retained_antenna_keepout();union(){retained_usb();connector_envelope();cable_envelopes();pack_fasteners();mounting_hardware();for(y=[12,67.5])translate([94.6,y,65.5])ax(5.9,10.5);}}
else if(part=="collision_wiring_drive")intersection(){cable_envelopes();difference(){retained_drive();box([3,133,20],[5,17,16]);}}
else if(part=="collision_wiring_cover")intersection(){cable_envelopes();retained_cover();}
else if(part=="collision_wiring_cassette")intersection(){cable_envelopes();union(){cassette_rear();cassette_front();cassette_spacer();}}
else if(part=="collision_wiring_pillars")intersection(){cable_envelopes();for(p=case_screws)case_pillar(p);}
// Remove only the intended Z3 seating plane; do not mistake coincident faces for penetration.
else if(part=="collision_cassette_backplate")intersection(){cassette();difference(){retained_backplate();box([-1,-1,2.99],[117,176,.02]);}}
else if(part=="collision_mount_tool")intersection(){
 // Ordinary straight 8 mm tool corridor; cover is removed for service.
 for(p=pack_mounts)zz([p[0],p[1],9.5],mount_tool_d,90);
 union(){cassette_rear();cassette_front();retained_drive();controller_frame();
  for(p=case_screws)case_pillar(p);connector_envelope();}
}
else if(part=="collision_mount_head")intersection(){
 for(p=pack_mounts)zz([p[0],p[1],6.41],5.5,2.99);
 union(){cassette_rear();cassette_front();retained_drive();controller_frame();}
}
else if(part=="collision_wall_head")intersection(){
 // Continuous central slot-adjustment plus release sweep; nominal seat is Z3.
 hull()for(y=wall_head_pocket_y)zz([45,y,3.01],9,4.99);
 cassette_rear();
}
else if(part=="collision_wall_roof_missing")difference(){
 // Positive thickness control expressed as an empty missing-material result.
 hull()for(y=wall_head_pocket_y)zz([45,y,wall_head_ceiling+.01],12.4,wall_pocket_roof-.02);
 cassette_rear();
}
else if(part=="collision_holder_combs")intersection(){
 union(){holder_end_combs(false);holder_end_combs(true);}
 carrier_contents();
}
else if(part=="collision_spacer_relief")intersection(){
 box([13.8,100,31.61],[68,3,.28]);cassette_spacer();
}
else if(part=="collision_spacer_section_missing")difference(){
 // Preserve 1.6 mm nominal section beneath the barrier slot; ignore boundary faces.
 box([13.8,100.51,31.91],[68,1.98,1.58]);cassette_spacer();
}
else if(part=="collision_spacer_barrier")intersection(){cassette_spacer();insulating_barrier();}
else if(part=="collision_cleat_engagement"){
 // Sample actual pocket sliding/lifting; intersect each pose before unioning.
 for(p=concat([for(y=[0,.625,1.25,1.875,2.5])[0,y,0]],
              [for(z=[1,2,3,4,5,6,7])[0,2.5,z]]))intersection(){
  translate(p)cassette_rear();
  difference(){retained_backplate();box([-1,-1,2.99],[117,176,.02]);}
 }
}
else if(part=="capture_engaged")intersection(){
 // Positive control: lifting 1 mm without the release slide must hit the heads.
 translate([0,0,1])cassette_rear();cassette_cleats();
}
else if(part=="collision_service_drive")intersection(){
 union(){cassette_slide_envelope();cassette_service_envelope(service_slide,service_forward);}
 retained_drive();
}
else if(part=="collision_service_controller")intersection(){
 union(){cassette_slide_envelope();cassette_service_envelope(service_slide,service_forward);}
 union(){retained_controller();for(p=case_screws)case_pillar(p);}
}
else if(part=="cleat_section"){
 color([.65,.72,.63])intersection(){retained_backplate();box([26,3,0],[6.8,17,15]);}
 color([.89,.90,.86])intersection(){cassette_rear();box([26,3,0],[6.8,17,15]);}
}
else if(part=="mounts"){color([.84,.86,.82])retained_backplate();color([.8,.83,.77,.6])cassette_rear();}
else assembly();
