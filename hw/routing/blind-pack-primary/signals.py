# Close charge-pump and supply bypass loops; vias lie outside SMT lands.
track(net('protection.gauge',2),F,.2,[[27.25,2.89],[27.25,2.45],[26.75,1.8],[26.75,1]],'CP-local')
n=net('protection.gauge',1)
track(n,F,.2,[[26.75,2.89],[25.4,2.1],[25.12,1.2]],'IN-local-bypass')
via(n,[25.4,2.1],'IN-local',False)
track(n,B,.2,[[25.4,2.1],[25.4,.65],[30.6,.65],[30.6,.65]],'IN-pump-return')
via(n,[30.6,.65],'IN-pump',False)
track(n,F,.2,[[30.6,.65],[28.75,1]],'IN-pump-cap')
# Ground/EP is separate from CSP until the RAW shunt landing.
for p in ([[26.75,6.71],[26.75,5.8],[28,5.8]],[[26.09,6.05],[28,6.05]],[[26.09,5.55],[28,5.55]]):
 track(ground,F,.2,p,'gauge-GND-local')
track(ground,F,.2,[[26.09,5.55],[25.6,5.55],[25.2,6.0]],'GND-pin-escape')
via(ground,[46.1,2],'GND-shunt',False)
track(ground,F,.3,[[46.1,2],[44.145,2.555]],'GND-shunt-bottom-land')
# REG2 and REG3 capacitors on each side; ground joins the same quiet return.
track(ground,F,.2,[[23.5,5.5],[24.3,5.5],[25.2,6.0]],'REG2-quiet-return')
# AOLDO is a local pulldown, separate from the charge-pump supply.

track(ground,F,.2,[[24.28,1.2],[24.2,2.5],[23.6,3.5],[23.5,5.5]],'IN-quiet-ground')
# Local PFAIL pulldown with layer transitions clear of both Kelvin traces.
n=net('protection.gauge',11)
via(ground,[35.6,3.5],'PFAIL-ground',False)

track(ground,B,.3,[[35.6,3.5],[44.3,3.5],[44.3,2],[46.1,2]],'quiet-right-return')

track(ground,F,.2,[[33.8,4.2],[35.6,3.5]],'REG3-flipped-shunt-return')
