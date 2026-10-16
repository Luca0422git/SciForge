# Raspberry Pi 5 case (made in SciForge)

Built from scratch by the GUI test `SciForgeTests/gui/scenarios/pi5_case.py` with SciForge's
own tools, the way a Fusion user would: Create Sketch, Extrude, Fillet, Shell, Hole, sketches
on each wall cut with Extrude, the lid as a New Body with a lip, a vent slot repeated with
Rectangular Pattern, a GPIO opening, the lid's top outline rounded with one Fillet click.

| File | What |
|---|---|
| `pi5_case.FCStd` | the design, with its timeline (open in SciForge) |
| `pi5_case.step` | both bodies, for any CAD program |
| `pi5_case-base.stl`, `pi5_case-lid.stl` | for the slicer, one file per body |
| `pi5_case-exploded.png` | lid lifted, a Pi 5 stand-in inside (green) |

Sizes (mm): base 91 x 62 x 25, 2 mm walls and floor, corners R3; the board's corner at
(3, 3) on four posts 3 mm high with 2.5 mm holes 4 deep (M2.5 self-tapping); lid 2 mm with a
1.2 x 1.5 lip (0.3 mm play). Openings: USB-C 10 x 5 and micro HDMI 9 x 5 (front), Ethernet
17 x 14.5 and two USB 15 x 17 (right), microSD 14 x 3 under the board (left), GPIO 53 x 5.8
in the lid, six vent slots 29 x 3.

**Not yet checked against a real board.** The board size, hole pattern and the Ethernet / USB
/ HDMI centres were confirmed from Raspberry Pi's mechanical drawing (through search
results); USB-C 11.2, HDMI 39.2, the microSD position and the connector heights are from
memory of the drawing and rounded up. Every opening has about 0.5 mm play. There is no
opening for the power button (which edge it faces was not confirmed); the active cooler
fits under the lid only if it is lower than the USB stacks (16 mm). Print one and check.
