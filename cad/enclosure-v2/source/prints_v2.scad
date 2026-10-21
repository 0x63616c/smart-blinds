// Version 2 assembly candidate. Millimetres, X across wall, Y up, Z out.
use <enclosure_case_v2.scad>
use <controller_frame_v2.scad>
use <protected_cassette_v2.scad>
use <front_buttons_v2.scad>
use <button_assembly_nest.scad>
use <cosmetic_plug_v2.scad>
use <drive_v2.scad>
use <usb_preview_v2.scad>
part="cover";
optional_plugs=false;
if(part=="cover")cover();
else if(part=="backplate")backplate();
else if(part=="motor_frame")controller_frame();
else if(part=="tail_keeper")tail_keeper();
else if(part=="front")cassette_front();
else if(part=="rear")cassette_rear();
else if(part=="spacer")cassette_spacer();
else if(part=="guard_clamp")guard_clamp();
else if(part=="backing")clamp_backing();
else if(part=="guide_bar")button_bar();
else if(part=="button")button();
else if(part=="lower_clip")translate([0,1,-3.4])controller_clip(false);
else if(part=="upper_clip")translate([0,-68,-61])controller_clip(true);
else if(part=="nest")button_nest();
else if(part=="cosmetic_plug")cosmetic_plug();
else if(part=="ring")cosmetic_ring();
else if(part=="inline_body")inline_housing();
else if(part=="housing_tie")housing_tie();
else if(part=="contents")carrier_contents();
else if(part=="pack_fasteners")carrier_fasteners(false);
else if(part=="drive")drive_assembly();
else if(part=="rear_lower")translate([5,28,-6])drive_lower(33.4);
else if(part=="rear_upper")translate([5,28,-28.8])drive_upper(33.4);
else if(part=="front_lower")translate([5,28,-6])drive_lower(37.4);
else if(part=="front_upper")translate([5,28,-28.8])drive_upper(37.4);
else if(part=="bearing_block")translate([0,24,-6])bearing_block();
else if(part=="retainer")rotate([0,-90,0])bearing_retainer();
else if(part=="wheel")rotate([0,-90,0])chainwheel();
else if(part=="guard")translate([0,0,-81.2])rotate([0,-90,0])chain_guard();
