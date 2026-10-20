// Fresh compact candidate: shared motor shaft plus an outboard bearing.
// This reduces, but does not eliminate, radial load carried by the motor gearbox.
// X across wall/shaft, Y up, Z out from wall. All dimensions millimetres.
part="assembly"; // assembly, closed, exploded, drive, buttons, bearing_block, retainer, wheel, guard, plunger, button_guide
button_orientation="front"; // right-angle SMT switches; side is the earlier comparison.
$fn=56;
tail_mode="trimmed"; // trimmed: <=1.5 mm measured protrusion; untrimmed: <=4.5 mm.
pack_gap=tail_mode=="trimmed"?5:12;
W=115; H=174; D=66+pack_gap; shaft_offset_z=7;
pcb_x=101.5; pcb_y=3; pcb_z=20; pcb_t=1.6; pcb_h=75; pcb_depth=35; component_h=8;
module_h=3.1; module_l=25.5; module_w=18; antenna_l=6.5; antenna_clearance=15;
antenna_y=pcb_y+pcb_h-antenna_l;
include <compact_buttons.scad>
upper_pcb_z=31.6+pack_gap; loaded_front_z=upper_pcb_z+1.6+25;
body_z=28; ay0=140; az=body_z+shaft_offset_z; wx=86.7; r=6/(2*sin(15));
module ax(d,l){rotate([0,90,0])cylinder(d=d,h=l);}
module ay(d,l){rotate([-90,0,0])cylinder(d=d,h=l);}
module rounded(s,r0=12){hull()for(x=[r0,s[0]-r0],y=[r0,s[1]-r0])translate([x,y,0])cylinder(r=r0,h=s[2]);}
module bolt(l=10){color([.62,.64,.65])union(){cylinder(d=3,h=l);translate([0,0,l])cylinder(d=5.5,h=3);}}
module nut(h=2.7,d=6.6){cylinder(d=d,h=h,$fn=6);}
module backplate(){difference(){union(){rounded([W,H,3]);translate([5,114,3])cube([99,55,3]);}for(p=[[10,109],[105,109],[57.5,163]])translate([p[0],p[1],-.1])hull()for(y=[-3,3])translate([0,y,0])cylinder(d=4.8,h=6.2);for(p=[[25,ay0-15],[25,ay0+15],[65,ay0-15],[65,ay0+15],[95.5,ay0-14],[95.5,ay0+14]]){translate([p[0],p[1],-.1])cylinder(d=3.4,h=6.2);translate([p[0],p[1],-.1])nut(2.8);}}}
module shell(){
 difference(){
  union(){
   difference(){
    translate([0,0,3.4])rounded([W,H,D-3.4]);
    translate([2.4,2.4,3.3])rounded([W-4.8,H-4.8,D-5.7],9.6);
    for(z=[az-r,az+r])translate([wx-3.5,H-2.5,z-3.7])cube([7,3,7.4]);
    translate([100,-.1,30])cube([10,3,15]);
    if(button_orientation=="front")for(y=button_ys)translate([button_x,y,D-2.5])cylinder(d=10.3,h=2.6);
    else for(y=[28,52])translate([W-2.5,y,40])ax(10.5,3);
   }
   if(button_orientation=="front")front_guides();
  }
  if(button_orientation=="front")for(y=[20,60])translate([button_x,y,D-6])cylinder(d=2.4,h=4.4);
 }
}
module holder(){color([.12,.13,.14])difference(){translate([-12.75,0,0])cube([25.5,83.8,16.1]);translate([-11,2.5,2])cube([22,78.8,20]);translate([-14,17,8])cube([28,50,12]);}color([.72,.73,.74])for(y=[1.5,80])translate([-8,y,2])cube([16,1,14]);color([.32,.47,.38])translate([0,6,12.725])ay(21.25,70.8);}
module pack(){
 // Two single-sided boards. Components are reservations, not routed carrier circuitry.
 color([.07,.075,.08])for(z=[30,upper_pcb_z])difference(){
  translate([3,6,z])rounded([86,104,1.6],4);
  // Edge notches reserve clearance for the case-supported retaining-bar feet.
  for(y=[34,78]){
   translate([2.9,y-.3,z-.1])cube([2.4,6.6,1.8]);
   translate([85.7,y-.3,z-.1])cube([3.4,6.6,1.8]);
  }
 }
 for(x=[18,44,70]){translate([x,14,30])mirror([0,0,1])holder();translate([x,14,upper_pcb_z+1.6])holder();}
 color([.77,.67,.4])difference(){
  translate([3,6,31.6+pack_gap/2-.5])rounded([86,104,1],4);
  for(y=[34,78]){
   translate([2.9,y-.3,31.6])cube([2.4,6.6,pack_gap]);
   translate([85.7,y-.3,31.6])cube([3.4,6.6,pack_gap]);
  }
 }
 color([.9,.48,.15,.6])translate([12,101,upper_pcb_z+1.6])cube([66,8,6]);
 // Four raw group rails remain permanently enclosed in the insulated cassette.
 color([.68,.45,.18])for(x=[18,36,54,72])translate([x,106,31.6])cube([3,2,pack_gap]);
 // Visible retention allocations: smooth bars, case-supported feet, and captive screws.
 color([.84,.86,.82])for(y=[34,78]){translate([3,y,loaded_front_z+.7])cube([87,6,2]);translate([3,y,3])cube([2,6,loaded_front_z-2.3]);translate([86,y,3])cube([3,6,loaded_front_z-2.3]);}
 color([.8,.81,.77])for(x=[7,83],y=[10,106])translate([x-3,y-3,3])cube([6,6,25]);
}
module antenna_keepout(){translate([pcb_x+pcb_t-antenna_clearance,antenna_y-antenna_clearance,pcb_z-antenna_clearance])cube([module_h+2*antenna_clearance,antenna_l+2*antenna_clearance,module_w+2*antenna_clearance]);}
module usb_metal(){translate([pcb_x+pcb_t,0,pcb_z+13])cube([3.4,8,9]);}
module controller(show_keepout=true){
 color([.07,.075,.08])translate([pcb_x,pcb_y,pcb_z])cube([pcb_t,pcb_h,pcb_depth]);
 color([.12,.65,.72,.35])translate([pcb_x+pcb_t,pcb_y+7,pcb_z])cube([component_h,pcb_h-7-antenna_l-antenna_clearance,pcb_depth]);
 // Antenna at upper end clears underside USB; actual footprint/ground still follows electrical placement.
 color([.66,.67,.68])translate([pcb_x+pcb_t,pcb_y+pcb_h-module_l,pcb_z])cube([module_h,module_l-antenna_l,module_w]);
 color([.16,.4,.8,.75])translate([pcb_x+pcb_t,antenna_y,pcb_z])cube([1,antenna_l,module_w]);
 if(show_keepout)color([.16,.4,.8,.12])antenna_keepout();
 color([.73,.75,.75])usb_metal();
 if(button_orientation=="front")front_button_hardware();
 else{
  color([.84,.86,.82])for(y=[28,52])translate([105.5,y,40])ax(5,8);
  color([.95,.96,.94])for(y=[28,52])translate([113,y,40])ax(9.9,3);
 }
}
module lower(d){wing=d/2+5;difference(){union(){translate([-5,-19,6])cube([10,38,4]);intersection(){translate([-5,0,body_z])ax(d+8,10);translate([-5,-d,6])cube([10,2*d,body_z-6]);}for(y=[-wing,wing])translate([-5,y-4,body_z-5])cube([10,8,5]);}translate([-5.1,0,body_z])ax(d,10.2);for(y=[-15,15])translate([0,y,5.9])cylinder(d=3.4,h=4.2);for(y=[-wing,wing]){translate([0,y,body_z-5.1])cylinder(d=3.4,h=5.3);translate([0,y,body_z-5.1])nut();}}}
module upper(d){wing=d/2+5;difference(){union(){intersection(){translate([-5,0,body_z])ax(d+8,10);translate([-5,-d,body_z+.8])cube([10,2*d,d]);}for(y=[-wing,wing])translate([-5,y-4,body_z+.8])cube([10,8,5]);}translate([-5.1,0,body_z])ax(d,10.2);for(y=[-wing,wing])translate([0,y,body_z])cylinder(d=3.4,h=7);}}
module drive_base(){difference(){translate([5,114,3])cube([99,55,3]);for(x=[25,65],y=[ay0-15,ay0+15])translate([x,y,2.9])cylinder(d=3.4,h=3.2);for(y=[ay0-14,ay0+14])translate([95.5,y,2.9])cylinder(d=3.4,h=3.2);}}
module bearing_block(){difference(){union(){translate([0,-18,6])cube([8,36,6]);translate([0,-6,11.9])cube([5,12,az-11.8]);hull(){translate([0,0,az])ax(18,5);translate([0,-20,az])ax(8,5);translate([0,-12,az-16])ax(8,5);}for(y=[-10.5,10.5])translate([0,y,az])ax(7,5);}
 translate([-.1,0,az])ax(8.6,5.2);translate([1.8,0,az])ax(10.2,3.3);
 for(y=[-10.5,10.5]){translate([-.1,y,az])ax(2.9,5.2);translate([-.1,y,az])rotate([0,90,0])nut(2.4,5.9);}
 for(v=[[-20,0],[-12,-16]]){translate([-.1,v[0],az+v[1]])ax(3.4,5.2);translate([2.3,v[0],az+v[1]])rotate([0,90,0])nut(2.8);}
 for(y=[-14,14])translate([4,y,5.9])cylinder(d=3.4,h=6.2);
}}
module retainer(){difference(){union(){ax(18,3);for(y=[-10.5,10.5])translate([0,y,0])ax(7,3);}translate([-.1,0,0])ax(8.6,3.2);for(y=[-10.5,10.5])translate([-.1,y,0])ax(2.9,3.2);}}
module wheel(){difference(){union(){ax(27,8);ax(30,.8);translate([7.2,0,0])ax(30,.8);}
 for(a=[0:30:330])translate([4,r*cos(a),r*sin(a)])sphere(d=5,$fn=24);
 translate([3.1,0,0])difference(){ax(32,1.8);translate([-.1,0,0])ax(20.8,2);}
 rotate([105,0,0])translate([-.1,0,0])rotate([0,90,0])linear_extrude(8.2)intersection(){circle(d=6.25);translate([-5,-5])square([10,7.45]);}
 rotate([15,0,0]){translate([4,0,0])cylinder(d=2.8,h=16);translate([4,0,5.1])nut(2.3,5.9);translate([1.1,0,5.1])cube([5.8,9,2.3]);}
}}
module guard(){difference(){union(){intersection(){difference(){translate([81.2,ay0,az])ax(37,10.3);translate([81.1,ay0,az])ax(33,10.5);}translate([81,ay0-21,az-21])cube([11,22,42]);}for(v=[[-20,0],[-12,-16]])translate([88.5,ay0+v[0],az+v[1]])ax(8,3);}for(v=[[-20,0],[-12,-16]])translate([88.4,ay0+v[0],az+v[1]])ax(3.4,3.2);}}
module chain(){color([.74,.76,.75]){for(z=[az-r,az+r]){translate([wx,ay0,z])ay(1,60);for(y=[ay0+6:6:ay0+60])translate([wx,y,z])sphere(d=4.5,$fn=16);}for(a=[0:30:180])translate([wx,ay0-r*sin(a),az+r*cos(a)])sphere(d=4.5,$fn=16);for(a=[0:30:150])hull()for(t=[a,a+30])translate([wx,ay0-r*sin(t),az+r*cos(t)])sphere(d=1,$fn=8);}}
module drive(){
 color([.85,.87,.83])drive_base();
 color([.6,.62,.63]){translate([12,ay0,body_z])ax(33,22);translate([34,ay0,body_z])ax(37,42);translate([76,ay0,az])ax(12,6);translate([82,ay0,az])ax(6,15.5);}
 color([.14,.15,.16])translate([8,ay0,body_z])ax(33,4);
 color([.9,.5,.12,.45])translate([3,ay0-8,body_z-8])cube([5,16,16]);
 for(i=[0:1])let(x=i==0?25:65,d=i==0?33.4:37.4){color([.86,.88,.84])translate([x,ay0,0]){lower(d);upper(d);}for(y=[ay0-d/2-5,ay0+d/2+5])translate([x,y,body_z-6.2])bolt(12);}
 color([.86,.88,.84])translate([91.5,ay0,0])bearing_block();color([.9,.91,.88])translate([96.5,ay0,az])retainer();
 color([.65,.67,.68])difference(){translate([93.5,ay0,az])ax(10,3);translate([93.4,ay0,az])ax(6,3.2);}
 color([.22,.24,.25])translate([82.7,ay0,az])wheel();color([.85,.87,.83])guard();chain();
 for(x=[25,65],y=[ay0-15,ay0+15])translate([x,y,.2])bolt(10);
 for(y=[ay0-14,ay0+14])translate([95.5,y,.2])bolt(12);
 for(v=[[-20,0],[-12,-16]])translate([98.5,ay0+v[0],az+v[1]])rotate([0,-90,0])bolt(10);
 color([.64,.66,.67])for(y=[ay0-10.5,ay0+10.5]){translate([91.5,y,az])ax(2.5,8);translate([99.5,y,az])ax(4.5,2.5);}

}
module wiring(){color([.65,.16,.12])for(p=[[[85,106,40],[96,98,57]],[[96,98,57],[107,86,57]],[[107,86,57],[107,73,57]],[[6,ay0,28],[6,113,28]],[[6,113,28],[6,113,50]],[[6,113,50],[96,113,57]],[[96,113,57],[107,86,57]]])hull()for(v=p)translate(v)sphere(d=3);}
if(part=="collision_guard_wheel")intersection(){guard();translate([82.7,ay0,az])wheel();}
else if(part=="collision_wheel_bearing_block")intersection(){translate([91.5,ay0,0])bearing_block();translate([82.7,ay0,az])wheel();}
else if(part=="collision_pack_drive")intersection(){pack();drive();}
else if(part=="collision_pack_controller")intersection(){pack();controller(false);}
else if(part=="collision_pack_shell")intersection(){pack();shell();}
else if(part=="collision_button_guides")intersection(){for(y=button_ys)front_plunger(y,button_travel-.01);union(){front_guides();button_guide_bar();}}
else if(part=="collision_button_shell")intersection(){for(y=button_ys)front_plunger(y,button_travel-.01);shell();}
else if(part=="collision_antenna_usb_wires")intersection(){antenna_keepout();union(){usb_metal();wiring();front_button_hardware();}}
else if(part=="bearing_block")translate([0,24,-6])bearing_block();
else if(part=="rear_lower")translate([5,28,-6])lower(33.4);
else if(part=="rear_upper")translate([5,28,-body_z-.8])upper(33.4);
else if(part=="front_lower")translate([5,28,-6])lower(37.4);
else if(part=="front_upper")translate([5,28,-body_z-.8])upper(37.4);
else if(part=="retainer")rotate([0,-90,0])retainer();
else if(part=="wheel")rotate([0,-90,0])wheel();
else if(part=="guard")translate([0,0,-81.2])rotate([0,-90,0])guard();
else if(part=="plunger")translate([0,0,D+1.2])rotate([180,0,0])translate([-button_x,-button_ys[0],0])front_plunger(button_ys[0]);
else if(part=="button_guide")translate([-button_x+4.6,-17,-D+5.5+button_travel+2])button_guide_bar();
else if(part=="buttons")button_section();
else if(part=="drive")drive();
else if(part=="closed"){color([.94,.95,.93])shell();color([.86,.88,.84])backplate();controller(false);chain();}
else{color([.86,.88,.84])backplate();pack();drive();controller();wiring();if(part=="exploded")translate([W+20,0,0])color([.94,.95,.93])shell();}
