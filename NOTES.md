# Notes
2026-07-17
- T0 extruder is slipping because the latch opens, printing alternate latches to try to fix
- Extruder changes have unnecessary movements, moving from the front left to the back right to the front left for some reason
- purge from teal to black is not at all sufficient, need more purge for black
- 

2026-07-19
I have made some hardware changes to the blobifier, most notably I increased the height of the blobifier tray, increased the x and z position of the shaker arm, moved the depressor from the front left to the back right and added a new nozzle rest and brush rest. The new nozzle rest and brush rest are both mounted on the gantry so the z position does not matter.

- shaker arm pos is x=4, z=4, y=ymax

- updated blobifier tray top z=0.3, x = 9, y = ymax

depressor position update
- start: x=15, y=341, z=15
- end: x=0, y=341, z=15
- note: the min z during depressor movement is 15, this clears the shaker arm
- once the cut is made, the toolhead do the following:
    1. should return to the depressor start position (x=15, y=341, z=15)
    2. then move perform any x/y moves needed before dropping z < 15 (need to clare the shaker arm)


brush and nozzle position update:
- note: the brush and nozzle rest are both mounted on the gantry so the z position does not matter
- note: the brush and nozzle rest should be approached from the side going either right or left, not forward or backward
- nozzle rest: x=45, y=ymax, z>0
- brush left: x=53, y=ymax, z>0
- brush right: x=88, y=ymax, z>0

2026-07-25
I have been testing blobifier and found that the initial extrusion does not stick to the arm because the filament in the nozzle has oozed out before it starts the purge, which means the initial part of the purge is nothing and yet the toolhead is going up in Z.
