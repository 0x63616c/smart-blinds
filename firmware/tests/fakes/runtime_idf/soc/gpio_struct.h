#pragma once
struct MockGpio {
 struct { unsigned out_sel=128;bool out_inv_sel=false,oen_inv_sel=false; } func_out_sel_cfg[32];
 struct { unsigned val=0xFFFFFFFF; } enable;
};
extern MockGpio GPIO;
