// Adjustable front buttons for the retained enclosure. Original printable design.
// No maximum switch overtravel is inferred: set first closure at the positive stop.
button_x=pcb_x+pcb_t+.8;
button_ys=[28,52];
button_travel=.40;
switch_setback=.30;
switch_tip_z=pcb_z+pcb_depth+.75-switch_setback;
button_screw_tip=62.60; // assembly setting, NOT an immutable manufactured dimension
module front_switch(y){
 color([.16,.17,.18])translate([pcb_x+pcb_t,y-1.75,pcb_z+pcb_depth-3-switch_setback])cube([1.3,3.5,3]);
 color([.73,.74,.75])for(yy=[y-2.3,y+1.75])translate([pcb_x+pcb_t,yy,pcb_z+pcb_depth-2.6-switch_setback])cube([.15,.55,2.2]);
 color([.42,.43,.44])translate([button_x-.35,y-.8,pcb_z+pcb_depth-switch_setback])cube([.7,1.6,.75]);
 color([.16,.17,.18])for(z=[pcb_z+pcb_depth-2.4-switch_setback,pcb_z+pcb_depth-.6-switch_setback])translate([pcb_x+pcb_t-.5,y,z])rotate([0,90,0])cylinder(d=.6,h=.5);
}
module front_plunger(y,press=0){translate([button_x,y,-press])difference(){
 union(){
  translate([0,0,65.5])cylinder(d=7.5,h=1.3);
  translate([0,0,66.8])cylinder(d=6,h=4.2);
  translate([0,0,70.2])cylinder(d=9.9,h=.8);
 }
 translate([0,0,65.4])cylinder(d=2.4,h=5.8);
 // The captive upper nut is side-loaded before the cover's guide surrounds it.
 translate([0,0,66.8])rotate([0,0,30])cylinder(d=4.95,h=1.75,$fn=6);
 translate([0,-2.15,66.8])cube([3.2,4.3,1.75]);
 translate([0,0,68.4])cylinder(d=4.2,h=2.8);
 // Jam nut bears on this recessed shoulder, leaving the flange as the stop.
 translate([0,0,65.4])cylinder(d=5.2,h=.4);
 for(x=[-3.5,3.5])translate([x,0,69.5])cylinder(d=1.55,h=1.6);
}}
module button_face(y,press=0){translate([button_x,y,-press])difference(){union(){
 translate([0,0,71])cylinder(d=9.9,h=1.2);
 // Cosmetic press-fit pins carry no switch or case load.
 for(x=[-3.5,3.5])translate([x,0,69.6])cylinder(d1=1.25,d2=1.6,h=1.5);
}
 translate([0,0,70.9])cylinder(d=4.5,h=.7);
}}
module button_adjuster(y,press=0,tip=button_screw_tip){color([.64,.66,.68])translate([button_x,y,-press]){
 translate([0,0,tip])cylinder(d=2,h=6);
 difference(){translate([0,0,tip+6])cylinder(d=3.8,h=2);translate([0,0,tip+7])cylinder(d=1.75,h=1.1,$fn=6);}
 for(z=[64.2,66.8])difference(){translate([0,0,z])rotate([0,0,30])cylinder(d=4.62,h=1.6,$fn=6);translate([0,0,z-.1])cylinder(d=2,h=1.8);}
}}
module front_guides(){difference(){
 union(){
  for(y=button_ys)translate([button_x,y,66.8])cylinder(d=13,h=1.9);
  for(y=[20,60])translate([button_x,y,65.1])cylinder(d=5.5,h=3.6);
 }
 for(y=button_ys)translate([button_x,y,66.7])cylinder(d=6.4,h=2.1);
 for(y=[20,60]){
  translate([button_x,y,65])cylinder(d=2.4,h=4.3);
  translate([button_x,y,65])cylinder(d=4.7,h=1.9,$fn=6);
 }
}}
module button_guide_bar(){difference(){
 translate([button_x-4.6,17,63.1])cube([9.2,46,2]);
 for(y=button_ys){
  translate([button_x,y,63])cylinder(d=2.4,h=2.2);
  // Captures the lower nut; at full press its bottom is63.8, above floor63.5.
  translate([button_x,y,63.5])cylinder(d=5.2,h=1.7);
 }
 for(y=[20,60])translate([button_x,y,63])cylinder(d=2.4,h=2.2);
}}
module front_button_hardware(){
 for(y=button_ys){front_switch(y);color([.95,.96,.94]){front_plunger(y);button_face(y);}button_adjuster(y);}
 color([.84,.86,.82])button_guide_bar();
 color([.65,.67,.68])for(y=[20,60]){
  translate([button_x,y,63.1])cylinder(d=2,h=6);
  translate([button_x,y,61.1])cylinder(d=3.8,h=2);
  translate([button_x,y,65.2])cylinder(d=4.5,h=1.6,$fn=6);
 }
}
module button_section(){intersection(){
 union(){color([.94,.95,.93])retained_cover();front_button_hardware();
  color([.07,.075,.08])translate([pcb_x,17,pcb_z+pcb_depth-7])cube([pcb_t,46,7]);}
 translate([button_x-4.8,17,48])cube([4.8,46,D-46+1.3]);
}}
