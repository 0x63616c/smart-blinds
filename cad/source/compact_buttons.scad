// Same-controller front buttons. Dimensions from XUNPU TS-1081S-AC01326.
// Fit candidate only: actual travel/force, no preload and printed fit need qualification.
button_x=pcb_x+pcb_t+.8;
button_ys=[28,52];
button_gap=.15;
button_travel=.40;
switch_tip_z=pcb_z+pcb_depth+.75;
module front_switch(y){
 color([.16,.17,.18])translate([pcb_x+pcb_t,y-1.75,pcb_z+pcb_depth-3])cube([1.3,3.5,3]);
 color([.73,.74,.75])for(yy=[y-2.3,y+1.75])translate([pcb_x+pcb_t,yy,pcb_z+pcb_depth-2.6])cube([.15,.55,2.2]);
 color([.42,.43,.44])translate([button_x-.35,y-.8,pcb_z+pcb_depth])cube([.7,1.6,.75]);
 // AC variant locating posts extend 0.5 mm into the PCB; holes belong to the footprint.
 color([.16,.17,.18])for(z=[pcb_z+pcb_depth-2.4,pcb_z+pcb_depth-.6])translate([pcb_x+pcb_t-.5,y,z])rotate([0,90,0])cylinder(d=.6,h=.5);
}
module front_plunger(y,press=0){
 translate([button_x,y,-press])union(){
  translate([0,0,switch_tip_z+button_gap])cylinder(d=2,h=D-4.2-switch_tip_z-button_gap);
  translate([0,0,D-5.5])cylinder(d=6,h=1.3);
  translate([0,0,D-4.2])cylinder(d=5,h=4.6);
  translate([0,0,D-.8])cylinder(d=9.9,h=2);
 }
}
module front_guides(){
 difference(){
  union(){
   for(y=button_ys)translate([button_x,y,D-4.2])cylinder(d=13,h=1.9);
   for(y=[20,60])translate([button_x,y,D-5.5-button_travel])cylinder(d=5.5,h=3.2+button_travel);
  }
  for(y=button_ys)translate([button_x,y,D-4.3])cylinder(d=5.4,h=2.1);
  for(y=[20,60]){
   translate([button_x,y,D-6])cylinder(d=2.4,h=4.3);
   translate([button_x,y,D-5.6-button_travel])cylinder(d=4.7,h=1.9,$fn=6);
  }
 }
}
module button_guide_bar(){
 difference(){
  translate([button_x-4.6,17,D-5.5-button_travel-2])cube([9.2,46,2]);
  for(y=button_ys)translate([button_x,y,D-8.2])cylinder(d=2.4,h=3);
  for(y=[20,60])translate([button_x,y,D-8.2])cylinder(d=2.4,h=3);
 }
}
module front_button_hardware(){
 for(y=button_ys){front_switch(y);color([.95,.96,.94])front_plunger(y);}
 color([.84,.86,.82])button_guide_bar();
 color([.65,.67,.68])for(y=[20,60]){
  translate([button_x,y,D-7.5-button_travel])cylinder(d=2,h=6);
  translate([button_x,y,D-9.5-button_travel])cylinder(d=3.8,h=2);
  translate([button_x,y,D-5.4-button_travel])cylinder(d=4.5,h=1.6,$fn=6);
 }
}
module button_section(){
 // Cut at actuator centre; a small slice exposes travel shoulders and guide bar.
 intersection(){
  union(){color([.94,.95,.93])shell();front_button_hardware();
   color([.07,.075,.08])translate([pcb_x,17,pcb_z+pcb_depth-7])cube([pcb_t,46,7]);}
  translate([button_x-4.8,17,48])cube([4.8,46,D-46]);
 }
}
