// Explicit auxiliary verification operand. Not an additional printable part.
// Clip fasteners copied dimension-for-dimension from the frozen v5 source,
// moved with the existing controller by global Y-3. No new hardware geometry.
use <protected_cassette_v2.scad>
use <controller_frame_v2.scad>
module controller_clip_hardware(){
 $fn=32;
 for(p=[[2,6.6],[71,64.4]]){
  translate([106.6,p[0],p[1]])rotate([0,90,0])cylinder(d=2,h=7.1);
  translate([113.7,p[0],p[1]])rotate([0,90,0])cylinder(d1=2,d2=3.8,h=.9);
  translate([106.6,p[0],p[1]])rotate([0,90,0])rotate([0,0,30])difference(){cylinder(d=4.62,h=1.6,$fn=6);cylinder(d=2,h=1.7);}
 }
}
carrier_fasteners(false);clamp_hardware();tail_hardware();translate([0,-3,0])controller_clip_hardware();
