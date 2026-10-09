> **Triaged 2026-10-09** — nothing below is open here any more; tracked items live in `TODO.md`.
> - Cold-start heat/cool dance, Z50 bob, ooze while the bed heats, 8-min soak → TODO *Cut
>   cold-start time in START_PRINT* (one START_PRINT sequencing problem).
> - Swap time → TODO roadmap #8 (toolchange sequence).
> - Blobs squashed by the tray, post-blob ooze → fixed (`eject_hop 3` / `z_raise 8`; purge runbook
>   closed 2026-10-09).
> - Jam missed by FlowGuard → fixed by `flowguard_max_relief` 40 → 8 (2026-08-20).
> - Shake not happening → by design: first shake after ~20 blobs (`max_blobs 400`,
>   `bucket_shake_frequency 0.95`); not seen failing since.
> - "Printer is actively printing" at start → not seen since; reopen with the log line if it returns.

2026-08-08 - 18:00
- during multi-color print start, it first heats up to unload the hotend, then it has to cool down to a safe temperature for beacon. is done by a 150C set and hold, and takes a long time. there is no fan assistance durint this, also, couldn't we hold and wait to the max safe temp for beacon contact, and then just set to 150 without a hold, then do contact auto calibrate
- there are severl times where we do a blobifier operation, then go up to z=50, then back down to blobifier height for no reason whatsoever
- there was a filament jam, looks like the filament got caught on something right after the hotend switch, but it was not caught by the flowguard
- blobifier shake is not happening for some reason, maybe the switch isn't being activated???
- on a print at 6:30pm, I saw the following error during print startup: Operation not possible. Printer is actively printing
- when doing a multi-color print, it unloads the filament and then parks the tool above the bed while the bed heats up, but that entire time the hotend is still at temperature and oozing filament. what the fuck is going on here???
- the bed is set to heat soak for 8+ min, this is ridiculous. I have a beacon that will can the bed in seconds and then the first layer only takes a minute or two, why do we need to heat soack the bed?
- I need to create two new briefs. one for speeding up the time for a print if it is Starting from cold and another one for the time between filament swaps. both of which are just too freaking long
- filament blobs falling over when tray pulls out from under them rather than hanging down in front of the tray, then they get swquished between the nozzle an tray and then dragged around until they fall off (this is a major issue and could cause a failed print)
- there is oozing from the nozzle after blobifier blob is removed, whcih then transfers over to the print
- 