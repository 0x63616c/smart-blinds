// Source assembly study, not a physical acceptance. Proper inward PCB pose.
use <enclosure_case_v2.scad>
use <controller_frame_v2.scad>
use <protected_cassette_v2.scad>
use <front_buttons_v2.scad>
use <cosmetic_plug_v2.scad>
use <drive_v2.scad>
use <usb_preview_v2.scad>
use <wiring_v2.scad>
part="assembly";
optional_plugs=false;
module b(p,s){translate(p)cube(s);}
module mounted_board(){
 color([.045,.045,.045])controller_board();
 // Reviewed drawing envelopes for prominent components; not a complete native
 // populated PCB render. All206 actual poses are independently screened.
 color([.18,.19,.20])b([101.43,62.01,47.175],[8.77,9.91,12.65]);
 color([.12,.13,.14])b([98.85,71.92,48.4],[11.35,7.65,10.2]);
 usb_preview();
 color([.6,.63,.66])b([107.04,50,13.5],[3.16,19,18]);
 color([.28,.29,.31])b([102.35,48.85,41.35],[7.85,6.3,6.3]);
}
module moving_module(tie=true){
 color([.92,.92,.90])cassette_rear();carrier_contents();carrier_fasteners(false);
 color([.89,.89,.85])cassette_spacer();color([.95,.95,.93])cassette_front();
 color([.92,.92,.90])guard_clamp();color([.95,.95,.93])clamp_backing();
 color([.94,.94,.92])controller_frame();mounted_board();
 color([.95,.95,.93]){controller_clip(false);controller_clip(true);tail_keeper();}
 color([.65,.66,.67])tail_hardware();
 color([.14,.15,.16])inline_housing();if(tie)color([.15,.15,.16])housing_tie();
 color([.55,.2,.17]){tail_pad();clamp_pad();}clamp_hardware();
 protected_fan();controller_motor_tails();
}
module cover_screws(){for(p=[[12,131],[106,131],[12,177],[106,177]])color([.65,.67,.69])translate([p[0],p[1],68])difference(){cylinder(d=5.5,h=3,$fn=32);translate([0,0,1.7])cylinder(d=2.9,h=1.4,$fn=6);}}
module wall_context(){color([.88,.89,.87])b([-30,-33,-2],[180,270,2]);
 color([.32,.35,.32])translate([-18,-8,.05])rotate([0,0,90])linear_extrude(.05)text("196 mm shell",size=5);
 color([.32,.35,.32])translate([2,-25,.05])linear_extrude(.05)text("118 mm - enclosure study",size=5);
}
module visible_buttons(){buttons_loaded();if(optional_plugs)for(y=[22,42])translate([109.4,y,0])color([.96,.96,.95])cosmetic_plug();}
if(part=="closed"){
 wall_context();cover_screws();usb_preview();
 color([.95,.95,.95])cover();color([.90,.90,.90])backplate();visible_buttons();chain();
}else if(part=="service"){
 wall_context();color([.9,.9,.9])backplate();color([.62,.65,.62])drive_assembly();
 translate([0,2.5,72])moving_module(false);parked_cables();
 color([.14,.15,.16])b([93.45,124,64.85],[11.2,25.5,8.5]);
 color([.2,.2,.2])b([106.3,125.325,67.5],[3.9,7.35,5.5]);
}else if(part=="buttons"){
 color([.95,.95,.95])intersection(){cover();b([89,8,61],[32,49,20]);}visible_buttons();
}else{
 wall_context();color([.9,.9,.9])backplate();color([.62,.65,.62])drive_assembly();moving_module();encoder_cable();fixed_motor_tails();
}
