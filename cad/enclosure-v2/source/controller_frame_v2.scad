// Public maintained CAD interface; dimensions are millimetres.
use <definitions.scad>
module controller_frame(){frame__current_frame();}
module tail_keeper(){motor_support__tail_keeper();}
module tail_pad(){motor_support__tail_pad();}
module tail_hardware(){motor_support__tail_hardware();}
module housing_tie(){motor_support__housing_tie();}
module inline_housing(){motor_support__inline_body();}
module controller_clip(upper=false){translate([0,-3,0])controller__clip(upper);}
module controller_board(){translate([0,-3,0])controller__board();}
