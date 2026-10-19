// Original Smart Blinds mechanical study. All lengths in mm.
// Coordinates: X across wall, Y up, Z outward. Envelopes are NOT purchased-part CAD.
include <parameters.scad>
option = "compact";
part = "assembly"; // assembly, closed, exploded, base, cover, cradle, clamp, wheel, guard, pcb_tray, button, coupons
$fn = 64;
idx = option == "broad" ? 0 : option == "compact" ? 1 : option == "narrow" ? 2 : 3;
shaft_offset_y = 0;
shaft_offset_z = 0;
W=option_sizes[idx][0]; H=option_sizes[idx][1]; D=option_sizes[idx][2];
wall=shell_wall; base_t=shell_base; r=shell_radius;
pack_origin=pack_origins[idx]; motor_origin=motor_origins[idx]; pcb_origin=pcb_origins[idx];
board_w=idx==2 ? 65 : pcb_width;
wheel_r=chain_pitch/(2*sin(180/chain_pockets));
wheel_x=92; wheel_y=motor_origin[1]+shaft_offset_y; wheel_z=motor_origin[2]+shaft_offset_z;

module rounded_box(size, radius=6) {
    hull() for(x=[radius,size[0]-radius],y=[radius,size[1]-radius])
        translate([x,y,0]) cylinder(r=radius,h=size[2]);
}
module axis_x(d,h) { rotate([0,90,0]) cylinder(d=d,h=h); }
module axis_y(d,h) { rotate([-90,0,0]) cylinder(d=d,h=h); }
module capsule_y(x,y,z,length,width,height) {
    translate([x,y,z]) hull() for(dy=[-length/2+width/2,length/2-width/2])
        translate([0,dy,0]) cylinder(d=width,h=height);
}
module cells() {
    color([0.32,0.47,0.39])
    if(idx!=2) for(x=[0:cell_cols[idx]-1],z=[0:cell_depth[idx]-1],row=[0:cell_rows[idx]-1])
        translate(pack_origin+[x*cell_pitch,2+row*(pack_l+4),z*cell_pitch]) axis_y(cell_d,cell_l);
    else for(y=[0:2],z=[0:1])
        translate(pack_origin+[2,y*cell_pitch,z*cell_pitch]) axis_x(cell_d,cell_l);
}
module pack_envelope() {
    color([0.22,0.31,0.30,0.18])
    if(idx!=2) translate([pack_origin[0]-pack_d/2,pack_origin[1],pack_origin[2]-pack_d/2])
        cube([(cell_cols[idx]-1)*cell_pitch+pack_d,cell_rows[idx]*pack_l+(cell_rows[idx]-1)*4,(cell_depth[idx]-1)*cell_pitch+pack_d]);
    else translate([pack_origin[0],pack_origin[1]-pack_d/2,pack_origin[2]-pack_d/2])
        cube([pack_l,2*cell_pitch+pack_d,cell_pitch+pack_d]);
}
module motor_envelope() {
    color([0.57,0.59,0.60])
    if(idx!=2) translate(motor_origin) axis_x(motor_d,motor_l);
    else translate(motor_origin) axis_y(motor_d,motor_l);
    color([0.24,0.25,0.26])
    if(idx!=2) translate(motor_origin+[-4,0,0]) axis_x(33,4);
    else translate(motor_origin+[0,-4,0]) axis_y(33,4);
    color([0.8,0.8,0.81])
    if(idx!=2) translate(motor_origin+[motor_l,shaft_offset_y,shaft_offset_z]) axis_x(shaft_d,shaft_l);
    else translate(motor_origin+[0,motor_l,0]) axis_y(shaft_d,shaft_l);
}
module chain_wheel() {
    // Shaft along Z locally; transform to X for assembly. Print flat, no motor fit claimed.
    difference() {
        union() {
            cylinder(r=wheel_r+chain_bead/2-0.2,h=wheel_width);
            cylinder(d=30,h=0.8);
            translate([0,0,wheel_width-0.8]) cylinder(d=30,h=0.8);
            translate([0,0,-5]) cylinder(d=13,h=5.5);
        }
        for(i=[0:chain_pockets-1]) rotate([0,0,i*360/chain_pockets])
            translate([wheel_r,0,wheel_width/2]) sphere(d=chain_bead+chain_clearance,$fn=24);
        // Cord groove opens between pockets; beads drive against the remaining flanks.
        rotate_extrude() translate([wheel_r, wheel_width/2,0]) circle(d=chain_link+0.5,$fn=16);
        // Candidate 6 mm D bore: tune coupon first. Flat dimension is independent.
        translate([0,0,-6]) linear_extrude(wheel_width+12)
            intersection(){circle(d=shaft_d+0.25);translate([-5,-5])square([10,shaft_flat-shaft_d/2+5]);}
        // M3 radial grub-screw pilot, nut/insert retention still needs qualification.
        translate([0,0,-2.2]) rotate([0,90,0]) cylinder(d=2.5,h=10);
    }
}
module drive_preview() {
    if(idx!=2) color([0.22,0.23,0.24])
        translate([wheel_x-wheel_width/2,wheel_y,wheel_z]) rotate([0,90,0]) chain_wheel();
    else {
        // Right-angle gear envelope only; no claim of working tooth geometry.
        color([0.35,0.35,0.36]) translate([26,187,26]) rotate([90,0,0]) cylinder(d1=25,d2=10,h=12);
        color([0.35,0.35,0.36]) translate([26,187,26]) rotate([0,90,0]) cylinder(d1=25,d2=10,h=12);
        color([0.7,0.7,0.72]) translate([26,187,26]) axis_x(5,35);
        color([0.22,0.23,0.24]) translate([59,187,26]) rotate([0,90,0]) chain_wheel();
    }
}
module chain_preview() {
    cy=idx!=2?wheel_y:187; cx=idx!=2?wheel_x:64;
    color([0.78,0.78,0.76]) {
        for(z=[wheel_z-wheel_r,wheel_z+wheel_r]) {
            translate([cx,cy,z]) axis_y(chain_link,H+38-cy);
            for(y=[cy:chain_pitch:H+38]) translate([cx,y,z]) sphere(d=chain_bead,$fn=20);
        }
        for(a=[0:30:180]) translate([cx,cy-wheel_r*sin(a),wheel_z+wheel_r*cos(a)]) sphere(d=chain_bead,$fn=20);
        for(a=[0:15:165]) hull() for(t=[a,a+15]) translate([cx,cy-wheel_r*sin(t),wheel_z+wheel_r*cos(t)]) sphere(d=chain_link,$fn=10);
    }
}
module pcb_envelope() {
    translate(pcb_origin) {
        color([0.07,0.075,0.08]) cube([board_w,pcb_height,pcb_thickness]);
        // Reserved volumes are NOT a populated board. No copper/part fit is claimed.
        color([0.1,0.65,0.75,0.35]) translate([0,0,pcb_thickness+0.02])
            if(idx==2) union(){translate([0,15.1,0])cube([board_w,pcb_height-15.1,pcb_component_h]);cube([board_w-18.1,15,pcb_component_h]);}
            else cube([board_w-antenna_w-0.1,pcb_height,pcb_component_h]);
        color([0.16,0.5,0.75,0.45]) translate([board_w-(idx==2?18:antenna_w),0,pcb_thickness+0.02])
            cube([idx==2?18:antenna_w,idx==2?15:pcb_height,pcb_component_h]);
        color([0.7,0.72,0.74]) translate([17,-3,1.6]) cube([9,8,3.4]);
    }
}
module baseplate() {
    difference() {
        union() {
            rounded_box([W,H,base_t],r);
            translate([wall+0.35,wall+0.35,base_t-0.1]) difference() {
                rounded_box([W-2*(wall+0.35),H-2*(wall+0.35),4.1],r-wall);
                translate([1.5,1.5,-0.1]) rounded_box([W-2*(wall+1.85),H-2*(wall+1.85),4.3],r-wall-1.5);
            }
            if(idx==1) {
                // Bottom screw and captive-nut pedestal, outside the pack and RF zone.
                translate([90,3,3]) cube([12,10,22]);
                for(y=[18,77]) translate([82,y,2.9]) cylinder(d=7,h=2.6);
                for(x=[19,64],y=[90,132]) translate([x,y,2.9]) cylinder(d=7,h=3.1);
            }
        }
        for(y=[54,H-19]) capsule_y(W-10,y,-0.1,14,4.6,base_t+0.2);
        capsule_y(10,89,-0.1,14,4.6,base_t+0.2);
        if(idx==1) {
            translate([96,0,18]) axis_y(3.4,16);
            translate([96,8,18]) rotate([-90,0,0]) cylinder(d=6.4,h=2.8,$fn=6);
            translate([93.2,8,18]) cube([5.6,2.8,8]);
            for(y=[18,77]) translate([82,y,-0.1]) cylinder(d=2.6,h=8);
            for(x=[19,64],y=[90,132]) translate([x,y,-0.1]) cylinder(d=2.6,h=8);
        }
    }
}
module cover() {
    difference() {
        translate([0,0,3.4]) rounded_box([W,H,D-3.4],r);
        translate([wall,wall,3.3]) rounded_box([W-2*wall,H-2*wall,D-wall-3.3],r-wall);
        // Chain slots, one for each strand, at the top. Chain plane is YZ.
        cx=idx!=2?wheel_x:64;
        for(z=[wheel_z-wheel_r,wheel_z+wheel_r])
            translate([cx-3.5,H-wall-0.2,z-3.8]) cube([7,wall+0.4,7.6]);
        // Bottom USB aperture, generous provisional plug envelope.
        translate([pcb_origin[0]+13,-0.1,pcb_origin[2]+0.5]) cube([17,wall+0.2,8]);
        // Two quiet flush circular buttons, spaced for fingertip access.
        for(x=[W/2-12,W/2+12]) translate([x,27,D-wall-0.1]) cylinder(d=10.5,h=wall+0.2);
        if(idx==1) translate([96,-0.1,18]) axis_y(3.4,wall+0.2);
    }
}
module battery_cradle() {
    // Removable tray for a pre-insulated welded 3x2 pack. No loose-cell contacts.
    difference() {
        union() {
            translate([4,7.5,3.5]) cube([75,81,2]);
            for(x=[4,77]) translate([x,7.5,5.5]) cube([2,81,11]);
            for(y=[7.5,86.5]) translate([4,y,5.5]) cube([75,2,11]);
            for(y=[18,77]) translate([77,y-4,5.5]) cube([9,8,2.5]);
        }
        // Side wall strap anchors. Use smooth insulating straps; qualify the route.
        for(y=[28,66]) translate([3,y,8]) cube([77,6,2]);
        for(y=[18,77]) translate([82,y,5.4]) cylinder(d=3.3,h=3);
    }
}
module motor_clamp() {
    // Printable lower cradle, 2 locations. Strap/upper clamp needed for live loads.
    difference() {
        union() {
            translate([-5,-23,0]) cube([10,46,10]);
            translate([-5,-20,0]) cube([10,40,28]);
        }
        translate([-6,0,22]) axis_x(motor_d+0.6,12);
        translate([-6,-22,22]) cube([12,44,12]);
        for(y=[-21,21]) translate([0,y,-0.1]) cylinder(d=3.3,h=11);
        for(y=[-15,15]) translate([-6,y,2]) cube([12,3,2]);
    }
}
module chain_guard() {
    // Removable U guard only, avoiding assumptions about an output bearing.
    difference() {
        translate([82,90,7]) rounded_box([20,42,39],4);
        translate([85,94,9]) rounded_box([14,38,35],2);
        translate([80,wheel_y,wheel_z]) axis_x(15.4,25);
        translate([80,111,9]) cube([25,22,35]);
        for(y=[93.5,128.5]) translate([91,y,5]) cylinder(d=3.3,h=44);
    }
}
module pcb_tray() {
    difference() {
        translate([pcb_origin[0]-3,3,53]) cube([63,38,2]);
        translate([pcb_origin[0]+4,8,52.9]) cube([48.5,25,2.2]);
        for(x=[pcb_origin[0]+2,pcb_origin[0]+55],y=[6,35]) translate([x,y,52.9]) cylinder(d=2.2,h=2.2);
    }
}
module button() {
    union(){cylinder(d=9.9,h=1.8);translate([0,0,-0.9])cylinder(d=12,h=1);translate([0,0,-3.6])cylinder(d=4,h=3);}
}
module coupons() {
    // Cell and shaft go/no-go coupons: label externally with measured sizes after printing.
    for(i=[0:2]) translate([i*32,0,0]) difference(){cube([29,29,5]);translate([14.5,14.5,-0.1])cylinder(d=23+i*0.2,h=5.2);}
    for(i=[0:3]) translate([i*20,36,0]) difference(){cube([17,17,5]);translate([8.5,8.5,-0.1])cylinder(d=6+i*0.1,h=5.2);}
    translate([15,80,5]) chain_wheel();
}
module assembly(show_cover=false,explode=0) {
    color([0.85,0.85,0.82]) baseplate();
    translate([0,0,explode]) {cells(); motor_envelope();drive_preview();chain_preview();}
    if(idx==1) {
        color([0.83,0.85,0.82]) translate([0,0,explode*0.8]) battery_cradle();
        color([0.82,0.84,0.82]) for(x=[19,64]) translate([x,111,6+explode*0.8]) motor_clamp();
        color([0.81,0.83,0.81]) translate([explode>0 ? -board_w-20 : 0,0,explode*1.8]) pcb_tray();
        color([0.86,0.87,0.84,0.65]) translate([0,shaft_offset_y,shaft_offset_z+explode*0.8]) chain_guard();
    }
    translate([explode>0 ? -board_w-20 : 0,0,explode*2]) pcb_envelope();
    if(show_cover) color([0.95,0.95,0.92]) translate([explode>0 ? W+20 : 0,0,explode]) cover();
    if(show_cover) color([0.83,0.84,0.81]) for(x=[W/2-12,W/2+12]) translate([x+(explode>0 ? W+20 : 0),27,D-1.1+explode]) button();
}
if(part=="assembly") assembly();
else if(part=="closed") assembly(true);
else if(part=="exploded") assembly(true,27);
else if(part=="base") baseplate();
else if(part=="cover") translate([0,H,D]) rotate([180,0,0]) cover();
else if(part=="cradle") translate([-4,-7.5,-3.5]) battery_cradle();
else if(part=="clamp") motor_clamp();
else if(part=="wheel") translate([0,0,5]) chain_wheel();
else if(part=="guard") translate([-82,-90,-7]) chain_guard();
else if(part=="pcb_tray") translate([-pcb_origin[0]+3,-3,-53]) pcb_tray();
else if(part=="button") translate([0,0,1.8]) rotate([180,0,0]) button();
else if(part=="coupons") coupons();
