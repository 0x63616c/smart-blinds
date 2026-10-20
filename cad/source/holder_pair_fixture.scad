// Reusable workshop-only paired loading fixture and tray-bearing support.
// No physical loading/retention/force qualification. Protected pigtail is space-only.
use <compact_retained.scad>
use <compact_direct.scad>
part="tray_stage";
$fn=40;
flip=false;
comb_lift=0;
combs=true;
fixture_base_size=[106,124,6];
fixture_translation=[5.2,4,5.4];
fixture_turn_axis=[47.8,0,34.1];
fixture_turn_bounds=[[3.2,-0.2,-10.6],[92.4,185,63.2]];
fixture_turn_lift=100;
fixture_maximum_height=62.5;
fixture_upper_approach_offset=-25;
fixture_pad_release=0.4;
fixture_parking_min=[32,130,26];
fixture_parking_size=[54,55,36];
// Provisional reusable fixture for an already wired empty pair.
// Temporary catches are workshop handling features, never the installed restraint.
module box(p,s){translate(p)cube(s);}
module zz(p,d,h){translate(p)cylinder(d=d,h=h);}
module pose(){translate(fixture_translation)
 if(flip)translate(fixture_turn_axis)rotate([0,180,0])translate(-fixture_turn_axis)children();
 else children();}
module base(){difference(){union(){
 rounded(fixture_base_size,4);
 // Four bare corner faces are symmetric when the pair is turned over.
 for(x=[14,92],y=[14,110]){
  zz([x,y,5.9],7.6,29.5);zz([x,y,35.3],3,1.7);
  // Brace only toward the outside of the holder envelopes.
  hull(){zz([x,y,6],7.6,1);zz([x<50?5:101,y,6],7.6,1);zz([x,y,28],7.6,1);}
 }
 // Independent comb pillars; no clamp load is carried by printed catches.
 for(x=[4,102],y=[13,111])zz([x,y,5.9],8,55.3);
 // One indexing pin per comb selects primary or companion after the 4 mm shift.
 for(y=[13,111]){box([0,y-3,59.8],[8,8.2,1.4]);zz([4,y+4,61.1],2.1,1.4);}
 }
 // Shallow post scallops admit the temporary hook tips.
 for(x=[10.2,94.8],y=[14,110])box([x-.3,y-.8,33.9],[1.8,1.6,1.6]);
 for(x=[4,102],y=[13,111]){
  zz([x,y,48.9],3.4,12.4);
  translate([x,y,52.6])cylinder(d=6.6,h=2.8,$fn=6);
  box([x<50?-2:102,y-3.3,52.6],[6,6.6,2.8]);
 }
}}
module comb(index=0){
 y=index==0?13:111;fy=index==0?19.6:98.6;
 translate([flip?4:0,0,comb_lift])difference(){union(){
  box([-3,y-3,61.2],[110,6,4]);box([-3,y-3,61.2],[10,11.3,4]);
  for(x=[25,51,77],dx=[-9.5,6.5]){
   box([x+dx,min(y,fy),61.2],[3,abs(y-fy)+1.6,4]);
   box([x+dx,fy,59.9],[3,1.6,1.4]);
  }
 }
 for(x=[4,102])hull()for(dx=[0,-4])zz([x+dx,y,61.1],3.4,4.2);
 for(x=[0,4])zz([x,y+4,61.1],2.5,4.2);
 // Workshop-only orientation cues next to the two keyed settings.
 for(mark=[[0,"C"],[4,"P"]])translate([mark[0],y+6.5,64.7])linear_extrude(.6)text(mark[1],size=1.5,halign="center",valign="center");
 }
}
module whole_holder_bounds(){for(x=[19.8,45.8,71.8]){
 box([x-12.75,14,5],[25.5,83.8,25]);box([x-12.75,14,38.2],[25.5,83.8,25]);
}}
module loaded_pair(){cassette_spacer();insulating_barrier();carrier_contents();}
module fixture(){base();if(combs){comb(0);comb(1);}}
module cell_at(x,z){translate([x,20,z])rotate([-90,0,0])cylinder(d=21.45,h=71);}
module upper_path(){
 for(x=[19.8,45.8,71.8]){
  hull(){cell_at(x,50.925);cell_at(x,90.925);}
  for(a=[0:2:18])hull()for(aa=[a,a+2])
   translate([x,93.8,50.925])rotate([-aa,0,0])translate([0,-70.8,0])
    rotate([-90,0,0])cylinder(d=21.45,h=71);
 }
}
module load_path(){if(flip)translate([0,0,68.2])mirror([0,0,1])upper_path();else upper_path();}

// Provisional temporary parking reservation, not a qualified cable fabrication drawing.
// All six protected insulated wires remain connected; raw links never open or unfold.
wire_od=1.85;
function bez(a,b,c,d,t)=[for(i=[0:2])pow(1-t,3)*a[i]+3*pow(1-t,2)*t*b[i]+3*(1-t)*t*t*c[i]+t*t*t*d[i]];
module segment(a,b){hull(){translate(a)sphere(d=wire_od);translate(b)sphere(d=wire_od);}}
module transition(){for(i=[0:5])let(
 p0=[51.8+6*i,100.8,41.2],p1=p0+[0,0,12],p3=[44+3*i,130,48+2*i],p2=p3+[0,-12,0]){
 segment([p0[0],p0[1],38.2],p0);
 for(j=[0:31])segment(bez(p0,p1,p2,p3,j/32),bez(p0,p1,p2,p3,(j+1)/32));
}}
module parking(){
 // Space for the stock pigtail's loose insulated slack and unplugged connector.
 // Actual wire-by-wire trim, coil bend radius and a load-free handling restraint remain open.
 translate(fixture_parking_min)cube(fixture_parking_size);
}
function derivative(a,b,c,d,t)=[for(i=[0:2])3*pow(1-t,2)*(b[i]-a[i])+6*(1-t)*t*(c[i]-b[i])+3*t*t*(d[i]-c[i])];
module transition_bounds(){for(i=[0:5])let(
 p0=[51.8+6*i,100.8,41.2],p1=p0+[0,0,12],p3=[44+3*i,130,48+2*i],p2=p3+[0,-12,0]){
 translate([p0[0]-wire_od/2,p0[1]-wire_od/2,38.2-wire_od/2])cube([wire_od,wire_od,3+wire_od]);
 // The control polygon of each exact Bezier subcurve bounds its complete path.
 for(j=[0:31])let(a=j/32,b=(j+1)/32,
  q0=bez(p0,p1,p2,p3,a),q3=bez(p0,p1,p2,p3,b),
  q1=q0+derivative(p0,p1,p2,p3,a)/96,q2=q3-derivative(p0,p1,p2,p3,b)/96,
  lo=[for(k=[0:2])min(q0[k],q1[k],q2[k],q3[k])-wire_od/2],
  hi=[for(k=[0:2])max(q0[k],q1[k],q2[k],q3[k])+wire_od/2])translate(lo)cube(hi-lo);
}}
module parked_harness(){transition_bounds();parking();}

// Bounded workshop alternative: tray retained to spacer before turning.
// Load, torque, printed stiffness and safe cell handling remain unqualified.
module end_pose(upper=false){if(upper)translate([0,116,0])mirror([0,1,0])children();else children();}
module end_clamp(upper=false){
 reach=upper?30:10.5;
 end_pose(upper)difference(){union(){
  // Upper jaw contacts the existing spacer edge stop, outside either PCB.
  box([39.5,-.2,-5.2],[10,3.2,47.7]);
  box([39.5,-.2,38.5],[10,5.9,4]);
  box([39.5,-.2,-5.2],[10,reach+4.2,6]);
  zz([44.5,reach,-7.4],7,2.3);
 }
 zz([44.5,reach,-7.5],3.4,8.4);
 translate([44.5,reach,-4])cylinder(d=6.6,h=2.8,$fn=6);
 box([39.4,reach-3.3,-4],[5.2,6.6,2.8]);
 }
}
module pressure_pad(upper=false,release=0){reach=upper?30:10.5;
 end_pose(upper)translate([0,0,-release])difference(){union(){
  box([38,reach-5,1.4],[13,10,2]);
  // Side skirts and inward hooks retain the pad around the jaw.
  for(x=[38,49.9])box([x,reach-3,-7.6],[1.1,6,11]);
  box([38,reach-3,-7.6],[2.3,6,2]);box([48.7,reach-3,-7.6],[2.3,6,2]);
 }
 // One millimetre blind seat locates the screw without exposing its tip to the tray.
 zz([44.5,reach,1.3],3.4,1.1);
 }
}
module clamp_hardware(upper=false,release=0){reach=upper?30:10.5;
 end_pose(upper){
 // M3x10 nominal; .4 mm release preserves the screw/pad locating engagement.
 zz([44.5,reach,-7.6-release],3,10);zz([44.5,reach,-10.6-release],5.5,3);
 difference(){translate([44.5,reach,-3.9])cylinder(d=6.35,h=2.4,$fn=6);zz([44.5,reach,-4],3,2.6);}
 }
}
module pads(){pressure_pad();pressure_pad(true);}
module clamps(){end_clamp();end_clamp(true);}
module clamp_screws(){clamp_hardware();clamp_hardware(true);}
module cradle(){difference(){union(){
 box([0,0,-2.6],[96,124,6]);
 for(x=[6,90],y=[6,118])zz([x,y,-14],10,11.5);
 }
 // Flat tray floor bears on the broad face; slightly lower corner/ear feet recess.
 for(p=[[8.8,10],[86.8,10],[8.8,106],[86.8,106]])zz([p[0],p[1],2.9],8.2,.6);
 box([73.4,108.4,2.9],[7.2,11.2,.6]);
 // Open channels admit the two removable clamps and screw heads.
 box([37.4,-.1,-14.1],[14.2,16.2,17.6]);
 box([37.4,80,-14.1],[14.2,44.2,17.6]);
}}
module paired_and_tray(){cassette_spacer();insulating_barrier();carrier_contents();cassette_rear();}
module contact_excluded_contents(){difference(){paired_and_tray();
 // Intended spacer-top and tray-bottom contact surfaces, not clearance claims.
 box([-1,-1,38.49],[118,180,.02]);box([-1,-1,3.39],[118,180,.02]);
}}
module companion_pose(){translate(fixture_translation)translate(fixture_turn_axis)rotate([0,180,0])translate(-fixture_turn_axis)children();}
module driver_corridors(){for(upper=[false,true])end_pose(upper)zz([44.5,upper?30:10.5,-50],6,39.4);}

// Exact translational approach for loosened temporary clamps; reverse is removal.
module loosened(upper=false){end_clamp(upper);pressure_pad(upper,fixture_pad_release);clamp_hardware(upper,fixture_pad_release);}
module lower_approach(){translate([-.005,-30,-.005])minkowski(){loosened();cube([.01,30,.01]);}}
module upper_approach(){
 // Enter beside the parked harness, then slide sideways between fixture pillars.
 translate([fixture_upper_approach_offset,-.005,-.005])minkowski(){loosened(true);cube([.01,30,.01]);}
 translate([fixture_upper_approach_offset,-.005,-.005])minkowski(){loosened(true);cube([-fixture_upper_approach_offset,.01,.01]);}
}
module paths(){lower_approach();upper_approach();}

module pad_travel(){intersection(){clamps();union(){pads();pressure_pad(false,.4);pressure_pad(true,.4);}}}
module pad_hook_control(){intersection(){clamps();translate([0,0,1])pads();}}
module pad_seat_control(){intersection(){
 translate([0,0,1.05])cube([100,120,.90]);
 translate([0,.4,0]){pressure_pad(false,.4);pressure_pad(true,.4);}
 union(){clamp_hardware(false,.4);clamp_hardware(true,.4);}}}
module pad_head_control(){intersection(){clamps();translate([0,0,.21])clamp_screws();}}
module tray_scene(){
 color([.86,.9,.83])cradle();color([.9,.9,.85,.65])cassette_rear();
 cassette_spacer();insulating_barrier();difference(){carrier_contents();pack_wire_fan();}
 color([.7,.78,.86]){clamps();pads();}color([.5,.5,.5])clamp_screws();
 color([.85,.45,.1])transition();color([.85,.6,.15,.15])parking();}
if(part=="collision_turn_bound")difference(){
 union(){paired_and_tray();clamps();pads();clamp_screws();parked_harness();}
 box(fixture_turn_bounds[0]-.001*[1,1,1],fixture_turn_bounds[1]-fixture_turn_bounds[0]+.002*[1,1,1]);}
else if(part=="collision_clear_base")intersection(){pose()whole_holder_bounds();base();}
else if(part=="collision_clear_catches")intersection(){pose()cassette_spacer();base();}
else if(part=="collision_load_retracted")intersection(){pose()load_path();union(){base();pose()cassette_spacer();}}
else if(part=="collision_comb_contents")intersection(){pose()difference(){carrier_contents();pack_wire_fan();}union(){comb(0);comb(1);}}
else if(part=="collision_parked_fixture")intersection(){pose()parked_harness();base();}
else if(part=="collision_parked_combs")intersection(){pose()parked_harness();union(){comb(0);comb(1);}}
else if(part=="collision_clamps_contents")intersection(){union(){clamps();pads();clamp_screws();}contact_excluded_contents();}
else if(part=="collision_clamps_fixture")intersection(){companion_pose(){clamps();pads();clamp_screws();driver_corridors();}base();}
else if(part=="collision_clamps_parking")intersection(){union(){clamps();pads();clamp_screws();}parked_harness();}
else if(part=="collision_cradle_contents")intersection(){cradle();difference(){union(){paired_and_tray();clamps();pads();clamp_screws();}
 for(z=[3,3.4])box([-1,-1,z-.01],[118,180,.02]);}}
else if(part=="collision_primary_loading")intersection(){upper_path();union(){cassette_spacer();cassette_rear();clamps();pads();clamp_screws();cradle();}}
else if(part=="collision_paths_contents")intersection(){paths();union(){contact_excluded_contents();parked_harness();}}
else if(part=="collision_paths_fixture")intersection(){companion_pose()paths();base();}
else if(part=="collision_pad_travel")pad_travel();
else if(part=="collision_rear_shell_fixture")intersection(){companion_pose()pair_swept_shell(false);base();}
else if(part=="pad_hook_control")pad_hook_control();
else if(part=="pad_seat_control")pad_seat_control();
else if(part=="pad_head_control")pad_head_control();
else if(part=="base")base();
else if(part=="lower_comb")translate([0,0,65.2])rotate([180,0,0])comb(0);
else if(part=="upper_comb")translate([0,0,65.2])rotate([180,0,0])comb(1);
else if(part=="lower_clamp")translate([0,0,49.5])rotate([0,90,0])end_clamp();
else if(part=="upper_clamp")translate([0,0,49.5])rotate([0,90,0])end_clamp(true);
else if(part=="cradle")translate([0,0,3.4])rotate([180,0,0])cradle();
else if(part=="lower_pad")translate([0,0,3.4])rotate([180,0,0])pressure_pad();
else if(part=="upper_pad")translate([0,0,3.4])rotate([180,0,0])pressure_pad(true);
else if(part=="tray_stage")tray_scene();
else if(part=="pad_detail"){
 color([.65,.75,.88])end_clamp();color([.9,.6,.2])pressure_pad();color([.5,.5,.5])clamp_hardware();
 color([.88,.9,.85,.6])intersection(){union(){cassette_rear();cassette_spacer();}box([36,0,0],[18,18,44]);}}
else{color([.86,.9,.83]){base();if(part!="open"){comb(0);comb(1);}}
 pose(){difference(){loaded_pair();pack_wire_fan();}color([.85,.45,.1])transition();color([.85,.6,.15,.15])parking();}}
