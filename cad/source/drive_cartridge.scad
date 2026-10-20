// Original mechanically retained drive prototype. Millimetres, X shaft direction.
// Reference case allocation 180 x 160 x 58; this file is the replaceable drive cartridge.
// Source dimensions: goBILDA 4002-0006-0006,1611-0514-0006,2101-0006-0070,2910-0919-0006.
part="assembly";
$fn=64;
shaft_offset_z=7; // 0..7 scenario; body stays fixed, replace bearing pods/guard risers.
motor_body_z=28; axis_z=motor_body_z+shaft_offset_z; axis_y=126;
rear_d=33.4; front_d=37.4; wheel_x=143; wheel_r=6/(2*sin(180/12));
module ax(d,l){rotate([0,90,0])cylinder(d=d,h=l);}
module ay(d,l){rotate([-90,0,0])cylinder(d=d,h=l);}
module roundbox(s,r=3){hull()for(x=[r,s[0]-r],y=[r,s[1]-r])translate([x,y,0])cylinder(r=r,h=s[2]);}
module nut_pocket(h=2.7){cylinder(d=6.6,h=h,$fn=6);}
module bolt(l=12){color([.60,.62,.64])union(){cylinder(d=3,h=l);translate([0,0,l])cylinder(d=5.5,h=3);}}
module countersunk_bolt(l=10){color([.60,.62,.64])union(){cylinder(d1=6,d2=3,h=1.5);translate([0,0,1.5])cylinder(d=3,h=l-1.5);}}
module base(){difference(){translate([5,106,0])roundbox([173,49,6]);
 for(x=[25,65],y=[111,141]){translate([x,y,-.1])cylinder(d=3.4,h=6.2);translate([x,y,-.1])nut_pocket(2.8);}
 for(x=[131.5,154.5],y=[114,143]){translate([x,y,-.1])cylinder(d=3.4,h=6.2);translate([x,y,-.1])nut_pocket(2.8);}
 for(x=[10,173],y=[112,149])translate([x,y,-.1])cylinder(d=3.4,h=6.2);
 }
}

module clamp_lower(d){
 wing=d/2+5;
 difference(){union(){translate([-5,-19,6])cube([10,38,4]);translate([-5,-6,9.9])cube([10,12,max(.1,motor_body_z-d/2-9.8)]);
 intersection(){translate([-5,0,motor_body_z])ax(d+8,10);translate([-5,-d,6])cube([10,2*d,motor_body_z-6]);}
 for(y=[-wing,wing])translate([-5,y-4,motor_body_z-5])cube([10,8,5]);
 }
 translate([-5.1,0,motor_body_z])ax(d,10.2);
 for(y=[-15,15])translate([0,y,5.9])cylinder(d=3.4,h=4.2);
 for(y=[-wing,wing]){translate([0,y,motor_body_z-5.1])cylinder(d=3.4,h=5.3);translate([0,y,motor_body_z-5.1])nut_pocket(2.8);}
 }
}
module clamp_upper(d){wing=d/2+5;difference(){union(){intersection(){translate([-5,0,motor_body_z])ax(d+8,10);translate([-5,-d,motor_body_z+.8])cube([10,2*d,d]);}for(y=[-wing,wing])translate([-5,y-4,motor_body_z+.8])cube([10,8,5]);}translate([-5.1,0,motor_body_z])ax(d,10.2);for(y=[-wing,wing])translate([0,y,motor_body_z])cylinder(d=3.4,h=6);}}
module bearing_block(){difference(){union(){translate([0,-15,6])cube([8,35,6]);translate([0,-6,11.9])cube([8,12,axis_z-11.8]);hull(){translate([0,0,axis_z])ax(22,8);translate([0,-19,axis_z])ax(8,8);translate([0,-12,axis_z-16])ax(8,8);}for(y=[-12.5,12.5])translate([0,y,axis_z])ax(8,8);}
 translate([-.1,0,axis_z])ax(14.2,5.2);translate([-.1,0,axis_z])ax(15.2,1.2);translate([-.1,0,axis_z])ax(10.5,8.2);
 for(y=[-12,17])translate([4,y,5.9])cylinder(d=3.4,h=6.2);
 for(y=[-12.5,12.5]){translate([-.1,y,axis_z])ax(3.4,8.2);translate([4.3,y,axis_z])rotate([0,90,0])nut_pocket(3.8);}
 for(v=[[-19,0],[-12,-16]]){translate([-.1,v[0],axis_z+v[1]])ax(3.4,8.2);translate([-.1,v[0],axis_z+v[1]])rotate([0,90,0])nut_pocket(2.8);}
}}
module bearing_retainer(){difference(){union(){ax(22,3);for(y=[-12.5,12.5])translate([0,y,0])ax(8,3);}translate([-.1,0,0])ax(10.5,3.2);for(y=[-12.5,12.5]){translate([-.1,y,0])ax(3.4,3.2);translate([-.1,y,0])rotate([0,90,0])cylinder(d1=6.6,d2=3.4,h=1.6);}}}
module bearing(){color([.67,.69,.70])difference(){union(){ax(15,1);ax(14,5);}translate([-.1,0,0])ax(6,5.2);}}
module collar(){color([.6,.62,.64])difference(){union(){ax(19,9);translate([9,0,0])ax(9,.5);}translate([-.1,0,0])ax(6,9.7);translate([-.1,0,0])cube([9.2,12,.7]);}
 // Translucent ring represents the complete 22.6 mm rotating pinch-screw sweep.
 color([.55,.58,.6,.22])difference(){ax(22.6,9);translate([-.1,0,0])ax(19,9.2);}}
module spacer(l=3){color([.7,.72,.73])difference(){union(){ax(8,2);translate([2,0,0])ax(9,1);}translate([-.1,0,0])ax(6.1,l+.2);}}
module wheel(){difference(){union(){ax(27,10);ax(30,.8);translate([9.2,0,0])ax(30,.8);}
 for(a=[0:30:330])translate([5,wheel_r*cos(a),wheel_r*sin(a)])sphere(d=5,$fn=24);
 // Open cord channel: chord midpoint is below the bead pitch circle.
 translate([4.1,0,0])difference(){ax(32,1.8);translate([-.1,0,0])ax(20.8,2);}
 rotate([105,0,0])translate([-.1,0,0])rotate([0,90,0])linear_extrude(10.2)intersection(){circle(d=6.25);translate([-5,-5])square([10,7.55]);}
 // Captive M3 nut and radial screw, between bead pockets. D flat is output-shaft5.5mm.
 rotate([15,0,0]){translate([5,0,0])cylinder(d=3.3,h=16);translate([5,0,5.1])nut_pocket(2.8);translate([2,0,5.1])cube([6,9,2.8]);}
}}
module guard(){difference(){union(){
 intersection(){difference(){translate([130,axis_y,axis_z])ax(37,14);translate([129.9,axis_y,axis_z])ax(33,14.2);}translate([129,axis_y-20,axis_z-20])cube([16,21,40]);}
 for(x=[130,142.5])intersection(){translate([x,axis_y,axis_z])ax(37,1.5);translate([x-.1,axis_y-20,axis_z-20])cube([1.7,21,40]);}
 for(x=[129.5,142.5],v=[[-19,0],[-12,-16]])translate([x,axis_y+v[0],axis_z+v[1]])ax(8,x<130?2.5:2);
 }
 translate([129.9,axis_y,axis_z])ax(8,14.2);
 for(v=[[-19,0],[-12,-16]])translate([129.4,axis_y+v[0],axis_z+v[1]])ax(3.4,15.2);
}}
module purchased(){
 color([.56,.58,.59])translate([12,axis_y,motor_body_z])ax(33,22);
 color([.60,.62,.63])translate([34,axis_y,motor_body_z])ax(37,42);
 color([.14,.15,.16])translate([8,axis_y,motor_body_z])ax(33,4);
 color([.56,.58,.59])translate([76,axis_y,axis_z])ax(12,6); // Boss diameter is an allowance, axial 6 mm is seller dimension.
 color([.68,.69,.70])translate([82,axis_y,axis_z])ax(6,15.5);
 color([.55,.58,.6])difference(){translate([89,axis_y,axis_z])ax(20,25);for(x=[97:2:105])translate([x,axis_y-11,axis_z-.4])cube([.8,22,.8]);}
 color([.72,.74,.75])translate([106,axis_y,axis_z])ax(6,70);
 translate([127.5,axis_y,axis_z])bearing();translate([158.5,axis_y,axis_z])mirror([1,0,0])bearing();
 translate([115,axis_y,axis_z])collar();translate([171,axis_y,axis_z])mirror([1,0,0])collar();
 translate([124.5,axis_y,axis_z])spacer();translate([158.5,axis_y,axis_z])spacer();
}
module chain(){color([.76,.77,.75]){
 for(z=[axis_z-wheel_r,axis_z+wheel_r]){translate([wheel_x,axis_y,z])ay(1,50);for(y=[axis_y+6:6:axis_y+48])translate([wheel_x,y,z])sphere(d=4.5,$fn=16);}
 for(a=[0:30:180])translate([wheel_x,axis_y-wheel_r*sin(a),axis_z+wheel_r*cos(a)])sphere(d=4.5,$fn=16);
 for(a=[0:30:150])hull()for(t=[a,a+30])translate([wheel_x,axis_y-wheel_r*sin(t),axis_z+wheel_r*cos(t)])sphere(d=1,$fn=8);
}}
module assembly(exploded=false){e=exploded?18:0;color([.86,.87,.84])base();
 for(i=[0:1])let(x=i==0?25:65,d=i==0?rear_d:front_d){color([.80,.83,.80])translate([x,axis_y,e])clamp_lower(d);color([.89,.9,.86])translate([x,axis_y,e*2])clamp_upper(d);if(!exploded)for(y=[axis_y-d/2-5,axis_y+d/2+5])translate([x,y,motor_body_z-6.2])bolt(12);}
 color([.83,.85,.82])translate([127.5,axis_y,e])bearing_block();color([.83,.85,.82])translate([158.5,axis_y,e])mirror([1,0,0])bearing_block();
 color([.88,.9,.86])translate([124.5-e,axis_y,axis_z+e])bearing_retainer();color([.88,.9,.86])translate([161.5+e,axis_y,axis_z+e])mirror([1,0,0])bearing_retainer();
 translate([0,0,e])purchased();color([.24,.25,.26])translate([138,axis_y,axis_z+e])wheel();color([.85,.86,.83])translate([6,-e,e*2])guard();
 if(!exploded){chain();for(y=[axis_y-12.5,axis_y+12.5]){translate([124.5,y,axis_z])rotate([0,90,0])countersunk_bolt(10);translate([161.5,y,axis_z])rotate([0,-90,0])countersunk_bolt(10);}
 for(x=[25,65],y=[111,141])translate([x,y,.2])bolt(10);for(x=[131.5,154.5],y=[114,143])translate([x,y,.2])bolt(12);for(v=[[-19,0],[-12,-16]]){translate([126,axis_y+v[0],axis_z+v[1]])rotate([0,90,0])bolt(12);translate([160.5,axis_y+v[0],axis_z+v[1]])rotate([0,-90,0])bolt(12);}}
}
if(part=="assembly")assembly();else if(part=="exploded")assembly(true);
else if(part=="base")translate([-5,-106,0])base();
else if(part=="rear_lower")translate([5,25,-6])clamp_lower(rear_d);
else if(part=="front_lower")translate([5,25,-6])clamp_lower(front_d);
else if(part=="rear_upper")translate([5,25,motor_body_z+rear_d/2+4])rotate([180,0,0])clamp_upper(rear_d);
else if(part=="front_upper")translate([5,25,motor_body_z+front_d/2+4])rotate([180,0,0])clamp_upper(front_d);
else if(part=="bearing_block")translate([0,20,-6])bearing_block();
else if(part=="bearing_retainer")rotate([0,-90,0])bearing_retainer();
else if(part=="wheel")rotate([0,-90,0])wheel();
else if(part=="guard")translate([0,0,-129.5])rotate([0,-90,0])guard();
