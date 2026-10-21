// Public maintained CAD interface; dimensions are millimetres.
use <definitions.scad>
module drive_lower(d=39){drive__lower(d);}
module drive_upper(d=39){drive__upper(d);}
module bearing_block(){drive__bearing_block();}
module bearing_retainer(){drive__retainer();}
module chainwheel(){drive__wheel();}
module chain_guard(){drive__guard();}
module drive_assembly(){translate([0,11,0])carrier_core__retained_drive();}
module chain(){translate([0,13,0])drive__chain();}
