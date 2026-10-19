// Original holder/drive integration study. X across wall, Y up, Z outward.
// Purchased items are explicit envelopes, not manufacturer CAD or verified fits.
include <packaging_v2_parameters.scad>
option="holders_broad";
part="assembly"; // assembly, closed, exploded, drive, holder_carrier
$fn=48;
idx=search([option],ids)[0];
sz=sizes[idx];W=sz[0];H=sz[1];D=sz[2];
battery=batteries[idx];drive=drives[idx];pb=pcbs[idx];mo=motors[idx];ca=carriers[idx];ra=radios[idx];
explode=part=="exploded"?35:0;
wheel_r=6/(2*sin(180/12));
wx=drive=="direct"?85:drive=="belt"?99:125.5;
wy=drive=="belt"?mo[1]+36:mo[1];wz=30;
module ax(d,l){rotate([0,90,0])cylinder(d=d,h=l);}
module ay(d,l){rotate([-90,0,0])cylinder(d=d,h=l);}
module roundbox(s,r=8){hull()for(x=[r,s[0]-r],y=[r,s[1]-r])translate([x,y,0])cylinder(r=r,h=s[2]);}
module slot(x,y,z,l=12,d=4.6,h=4){translate([x,y,z])hull()for(t=[-l/2+d/2,l/2-d/2])translate([0,t,0])cylinder(d=d,h=h);}
module backplate(){difference(){roundbox([W,H,3]);for(y=[45,H-16])slot(W-10,y,-.1);slot(10,H-16,-.1);}}
module cover(){difference(){translate([0,0,3.4])roundbox([W,H,D-3.4]);translate([2.4,2.4,3.3])roundbox([W-4.8,H-4.8,D-5.7],5.6);for(z=[wz-wheel_r,wz+wheel_r])translate([wx-3.5,H-2.5,z-3.7])cube([7,3,7.4]);translate([pb[0]+pb[3]/2-8.5,-.1,pb[2]+.5])cube([17,3,8]);if(pb[3]<50)for(y=[28,52])translate([pb[0]+pb[3]/2,y,D-2.5])cylinder(d=10.5,h=3);else for(x=[W/2-12,W/2+12])translate([x,27,D-2.5])cylinder(d=10.5,h=3);}}
module buttons(){color([.80,.82,.79])if(pb[3]<50)for(y=[28,52])translate([pb[0]+pb[3]/2,y,D-2])cylinder(d=9.9,h=1.5);else for(x=[W/2-12,W/2+12])translate([x,27,D-2])cylinder(d=9.9,h=1.5);}
module cell(){color([.31,.46,.38])translate([0,6,2.1+21.25/2])ay(21.25,70.8);}
module holder(smt=false){
  // Body maximum envelope with original visual reliefs; drawing not a solid model.
  color([.13,.14,.15])difference(){translate([-12.75,0,0])cube([25.5,83.8,16.1]);translate([-11,2.5,2])cube([22,78.8,20]);translate([-14,17,8])cube([28,50,12]);}
  color([.7,.72,.73])for(y=[1.5,80])translate([-8,y,2])cube([16,1,14]);
  if(smt)color([.7,.72,.73])for(y=[-5,83])translate([-4,y,0])cube([8,5,.5]);
  cell();
}
module pcb_carrier(){
  color([.08,.085,.09])translate([ca[0],ca[1],ca[2]])cube([ca[3],ca[4],1.6]);
  // Separate protection electronics strip, not a populated circuit.
  color([.88,.48,.16,.55])translate([ca[0]+5,ca[1]+ca[4]-9,ca[2]+1.6])cube([ca[3]-10,8,6]);
  if(battery=="broad")for(i=[0:5])translate([ca[0]+14+i*26,ca[1]+4,ca[2]+1.6])holder();
  if(battery=="smt"){
    for(i=[0:2])translate([ca[0]+14+i*26,ca[1]+6,ca[2]+1.6])holder(true);
    // 12mm stagger reserves room to develop non-colliding peg patterns; not qualified.
    for(i=[0:2])translate([ca[0]+14+i*26,ca[1]+18,ca[2]])mirror([0,0,1])holder(true);
  }
  if(battery=="stack"){
    for(i=[0:2])translate([ca[0]+14+i*26,ca[1]+4,ca[2]])mirror([0,0,1])holder();
    color([.08,.085,.09])translate([ca[0],ca[1],ca[2]+13.6])cube([ca[3],ca[4],1.6]);
    for(i=[0:2])translate([ca[0]+14+i*26,ca[1]+4,ca[2]+15.2])holder();
    // 1mm insulating barrier in12mm rear gap: 4.5mm tails +2mm combined residual clearance.
    color([.76,.66,.37])translate([ca[0],ca[1],ca[2]+7.1])cube([ca[3],ca[4],1]);
    color([.68,.47,.18])for(x=[ca[0]+8,ca[0]+26,ca[0]+44,ca[0]+62])translate([x,ca[1]+ca[4]-4,ca[2]+1.6])cube([3,2,12]);
  }
}
module batteries_view(){if(battery=="welded"){
 color([.30,.45,.37])for(x=[18,41.5,65],z=[17,40.5])translate([x,12,z])ay(21.25,70.8);
 color([.23,.32,.29,.18])translate([6.5,10,5.5])cube([70,76,46.5]);
}else pcb_carrier();}
module board(){color([.065,.07,.075])translate([pb[0],pb[1],pb[2]])cube([pb[3],pb[4],1.6]);color([.09,.65,.72,.3])difference(){translate([pb[0],pb[1],pb[2]+1.6])cube([pb[3],pb[4],8]);translate([ra[0]-.02,ra[1]-.02,ra[2]-.02])cube([ra[3]+.04,ra[4]+.04,ra[5]+.04]);}color([.14,.38,.78,.7])translate([ra[0],ra[1],ra[2]])cube([ra[3],ra[4],ra[5]]);color([.73,.74,.75])translate([pb[0]+pb[3]/2-4.5,pb[1]-3,pb[2]+1.6])cube([9,8,3.4]);}
module wheel(){difference(){union(){ax(27,10);ax(30,.8);translate([9.2,0,0])ax(30,.8);}for(a=[0:30:330])translate([5,wheel_r*cos(a),wheel_r*sin(a)])sphere(d=5,$fn=20);translate([-1,0,0])ax(6.25,12);}}
module chain(){color([.75,.76,.74]){for(z=[wz-wheel_r,wz+wheel_r]){translate([wx,wy,z])ay(1,H+30-wy);for(y=[wy:6:H+30])translate([wx,y,z])sphere(d=4.5,$fn=16);}for(a=[0:30:180])translate([wx,wy-wheel_r*sin(a),wz+wheel_r*cos(a)])sphere(d=4.5,$fn=16);for(a=[0:15:165])hull()for(t=[a,a+15])translate([wx,wy-wheel_r*sin(t),wz+wheel_r*cos(t)])sphere(d=1,$fn=8);}}
module bearing(x,y){color([.62,.64,.66])difference(){translate([x,y,30])ax(19,6);translate([x-.1,y,30])ax(6,6.2);}}
module drive_train(){
 color([.58,.60,.61])translate(mo)ax(39,64);
 color([.15,.16,.17])translate(mo+[-4,0,0])ax(33,4);
 color([.66,.66,.68])translate(mo+[64,0,0])ax(6,15.5);
 // Rear connector plus cable bend reservation is deliberately visible.
 color([.8,.4,.1,.45])translate(mo+[-8,-8,-8])cube([8,16,16]);
 if(drive=="inline"){
  color([.52,.53,.55])translate([83,wy,wz])ax(20,25);
  color([.7,.71,.72])translate([100,wy,wz])ax(6,43);
  bearing(112,wy);bearing(136,wy);
 }
 if(drive=="belt"){
  color([.7,.71,.72])translate([68,wy,wz])ax(6,43);bearing(69,wy);bearing(104,wy);
  color([.32,.33,.34])for(y=[mo[1],wy])translate([82,y,wz])ax(18,8);
  // Belt loop outline only; no tooth, tension or vendor specification claim.
  color([.13,.14,.15])translate([83,0,0])difference(){hull(){translate([0,mo[1],30])ax(20,6);translate([0,wy,30])ax(20,6);}translate([-.1,0,0])hull(){translate([0,mo[1],30])ax(17,6.2);translate([0,wy,30])ax(17,6.2);}}
 }
 color([.22,.23,.24])translate([wx-5,wy,wz])wheel();chain();
}
module cable_route(){color([.65,.15,.12]){a=[battery=="broad"?ca[0]+ca[3]-5:82,100,40];b=[pb[0]+4,82,40];hull(){translate(a)sphere(d=3);translate(b)sphere(d=3);}hull(){translate(b)sphere(d=3);translate([pb[0]+4,pb[1]+pb[4]-4,pb[2]+4])sphere(d=3);}}}
module study(){color([.87,.88,.85])backplate();translate([0,0,explode])batteries_view();translate([0,0,explode*1.5])drive_train();translate([explode>0?-pb[3]-25:0,0,explode*2])board();if(explode==0)cable_route();if(part=="closed"||part=="exploded")translate([explode>0?W+20:0,0,explode]){color([.95,.95,.92])cover();buttons();}}
if(part=="drive")drive_train();else if(part=="holder_carrier")pcb_carrier();else study();
