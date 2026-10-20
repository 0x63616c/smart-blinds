// Reusable holder-service fixture candidate. This is not an installed enclosure part.
// Original geometry; holder body remains the conservative family allocation.
// Fit, clamp force, cell insertion trajectory and dielectric contact need qualification.
use <compact_direct.scad>
part="assembly";
$fn=40;
pcb_origin=[10,10,12];
pcb_size=[86,104,1.6];
holder_rim_height=16.1;
contact_gap=0.2; // Independent setting. No preload or solder unloading is assumed.
foot_drop=1.8;
beam_height=4;
contact_z=pcb_origin[2]+pcb_size[2]+holder_rim_height+contact_gap;
beam_bottom=contact_z+foot_drop;
beam_top=beam_bottom+beam_height;
nut_z=beam_top-30; // M3x30 thread starts at this nominal captive-nut base.
beam_ys=[13,107];
foot_ys=[19.6,98.6];
holder_xs=[25,51,77];
backing_lands=[[11,25,19,75],[37,25,45,75],[63,25,71,75]];
corner_xy=[[14,14],[92,14],[14,110],[92,110]];

module box(p,s){translate(p)cube(s);}
module zz(p,d,h){translate(p)cylinder(d=d,h=h);}
module hex(p,d,h){translate(p)cylinder(d=d,h=h,$fn=6);}

module fixture_base(){difference(){union(){
 rounded([106,124,6],4);
 // Dielectric supports avoid end contacts, locating pegs and the untrimmed tails.
 for(r=backing_lands)box([10+r[0],10+r[1],5.9],[r[2]-r[0],r[3]-r[1],6.1]);
 for(p=corner_xy){zz([p[0],p[1],5.9],7.6,6.1);zz([p[0],p[1],11.9],3,2.5);}
 for(x=[5,101],y=beam_ys)zz([x,y,5.9],8,beam_bottom-5.9);
 }
 for(x=[5,101],y=beam_ys){
  zz([x,y,nut_z-.1],3.4,beam_bottom-nut_z+.3);
  hex([x,y,nut_z],6.6,2.8);
  box([x<50?-1:101,y-3.3,nut_z],[6,6.6,2.8]);
 }
}}
module end_comb(index=0){
 y=beam_ys[index]; fy=foot_ys[index];
 difference(){union(){
  box([1,y-3,beam_bottom],[104,6,beam_height]);
  for(x=holder_xs,dx=[-9.5,6.5]){
   box([x+dx,min(y,fy),beam_bottom],[3,abs(y-fy)+1.6,beam_height]);
   box([x+dx,fy,contact_z],[3,1.6,foot_drop+.1]);
  }
 }
 for(x=[5,101])zz([x,y,beam_bottom-.1],3.4,beam_height+.2);
 }
}
module fixture_pcb(){difference(){
 translate(pcb_origin)rounded(pcb_size,4);
 for(p=corner_xy)zz([p[0],p[1],11.9],3.4,1.8);
}}
module fixture_holders(){for(x=holder_xs)translate([x,18,13.6])holder();}
module fixture_fasteners(){for(x=[5,101],y=beam_ys){
 zz([x,y,nut_z],3,30);zz([x,y,beam_top],5.5,3);
 hex([x,y,nut_z],6.35,2.4);
}}
module contact_foot_reservation(){for(x=holder_xs,dx=[-9.5,6.5],y=foot_ys)
 box([x+dx,y,contact_z],[3,1.6,foot_drop]);}
module tails(){
 // Untrimmed drawing maximum4.5 mm; the PCB underside is Z12.
 for(x=holder_xs,y=[19.9,99.9])box([x-.55,y-1.9,7.5],[1.1,3.8,4.5]);
}
module assembly(){
 color([.86,.89,.84])fixture_base();
 color([.06,.07,.07,.5])fixture_pcb();
 fixture_holders();
 color([.84,.87,.81])for(i=[0,1])end_comb(i);
 color([.6,.62,.64])fixture_fasteners();
}
if(part=="base")fixture_base();
else if(part=="lower_comb")translate([0,0,beam_top])rotate([180,0,0])end_comb(0);
else if(part=="upper_comb")translate([0,0,beam_top])rotate([180,0,0])end_comb(1);
else if(part=="collision_holders")intersection(){fixture_holders();union(){fixture_base();end_comb(0);end_comb(1);}}
else if(part=="collision_pcb")intersection(){
 // Exclude only the intended seating plane; the locating pegs must clear holes.
 intersection(){fixture_pcb();box([0,0,12.01],[110,125,1.6]);}
 union(){fixture_base();end_comb(0);end_comb(1);}
}
else if(part=="collision_tails")intersection(){tails();fixture_base();}
else assembly();
