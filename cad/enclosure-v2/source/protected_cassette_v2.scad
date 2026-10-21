// Public maintained CAD interface; dimensions are millimetres.
use <definitions.scad>
module cassette_front(){cassette__front();}
module cassette_rear(){cassette__rear();}
module cassette_spacer(){cassette__spacer();}
module guard_clamp(){wire_clamp__guard_clamp();}
module clamp_backing(){wire_clamp__backing();}
module clamp_pad(){wire_clamp__compliant_pad();}
module clamp_hardware(){wire_clamp__clamp_hardware();}
module carrier_contents(){carrier_details__contents_without_old_fan();}
module carrier_fasteners(frame=true){carrier_core__pack_fasteners(frame);}
module barrier(){carrier_core__insulating_barrier();}
