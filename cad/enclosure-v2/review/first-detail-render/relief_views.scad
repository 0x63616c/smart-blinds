// Source-exported cutaway views. Colours distinguish parts, not final filament.
part="link";
module box(p,s){translate(p)cube(s);}
module mesh(n){import(str("../exports/",n,".stl"),convexity=12);}
module crop(){
 if(part=="link")box([36,106,34],[14,14,13]);
 else if(part=="motor")box([88,63,61.6],[12,10,11]);
 else if(part=="upper_capture")box([88,96,26],[9,13,17]);
 else box([88,7,34],[9,6,10]);
}
color([.92,.92,.89])intersection(){mesh("front");crop();}
color([.75,.82,.88])intersection(){mesh("rear");crop();}
color([.95,.57,.17])intersection(){mesh("spacer");crop();}
color([.1,.42,.2])intersection(){mesh("contents");crop();}
if(part=="motor")color([.3,.45,.7])intersection(){mesh("motor_frame");crop();}
