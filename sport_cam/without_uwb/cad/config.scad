// SportCam — parametric dimensions (mm). Every part file includes this.
//
// Three kinds of number feed the CAD:
//   * design choices — wall thickness, clearances — set below;
//   * the sizes of the parts you buy — in ../../cad/ordered_parts.toml;
//   * the layout — where each board sits, which way the Pi faces, how big
//     the enclosure is — which ../../cad/fit.py solves from the other two
//     and writes to layout.scad (included half-way down).
// After changing either file run   python3 cad/fit.py   from sport_cam/.
// It re-solves the layout, re-renders the STLs and audits that every part
// fits together and prints on a Bambu Lab A1 Mini (cad/FIT_REPORT.md).
//
// Keep the numbers above the include plain numbers (fit.py reads them);
// anything worked out from the layout goes below it.
//
// This is the **PTZ-base build**: the camera, pan and tilt all come from the
// Arducam IMX477 PTZ camera with metal pan-tilt base (B0167B12), which bolts
// to the lid of a static enclosure — see docs/design/03-mechanical-design.md.
//
// This is the **camera-only variant**: no UWB anchors, no mast, no wearable.
// The camera finds and follows a person by vision alone.

$fn = 96;
clr = 0.25;                    // general printed-fit clearance per side

// ---- enclosure -------------------------------------------------------------
// Bottom to top: the power boards stuck to the floor; the LED ring under a
// printed shelf, shining out through the LED window; the Raspberry Pi on the
// shelf; the lid with the camera. Every part must print in one piece on a
// Bambu Lab A1 Mini (≤ 170 mm on every axis); fit.py keeps it that way.
base_d_min    = 135;           // narrowest enclosure (outer Ø); fit.py widens it only if the parts need it
base_h_min    = 66;            // lowest floor-to-lid height; fit.py raises it to clear the stack
base_wall     = 3;
lid_t         = 5;             // lid is structural: it carries the whole camera
spigot_h      = 6;             // locating ring under the lid that drops into the mouth
spigot_w      = 3;
lid_screw_pad = 7;             // the ring is thickened here for the four radial M3 inserts
lid_screw_d   = 3.4;
led_window_h  = 12;            // circumferential window the LED ring lights
window_bridge = 22;            // longest unsupported span over the window; ribs every this far
window_rib_w  = 3;
diffuser_t    = 1.6;           // translucent band slid over the outside of the window
diffuser_lip  = 2;             // how far it overlaps the wall above and below
ledge_h       = 2;             // the band rests on this outside ledge

tripod_boss_d = 24;            // floor boss with a hex pocket for a 3/8-16 nut (size from ordered_parts.toml)
tripod_boss_h = 12;
tripod_ledge = 3;              // plastic under the nut: the tripod screw pulls the nut down onto it
tripod_clear_d = 10.2;         // through the ledge, for the bushing or a 3/8-16 screw
tripod_nut_clr = 0.2;          // round the nut in its pocket, each side (epoxied)

tape_t        = 1;             // foam tape under the power boards and the LED ring
part_gap      = 2;             // clearance fit.py keeps between parts
wall_gap      = 1;             // and between a part and the wall
shelf_t       = 3;             // the Pi shelf
post_d        = 10;            // shelf posts, merged into the wall; M3 insert in each top
post_insert_d = 4.0;
vent_w        = 4;
vent_h        = 8;
ribbon_slack_h = 8;            // clear height kept under the lid's cable slot for the ribbon to turn

// ---- Arducam pan-tilt base interface ---------------------------------------
// The base is a round turntable on four brass standoffs, the pan servo hanging
// under it between them. It keeps its standoffs: four M3 screws come up
// through the lid into them. Arducam publishes no drawing for the B0167B12
// base, so the lid is cut with radial SLOTS spanning this range. Your base's
// spacing goes in ordered_parts.toml [ptz]; the audit checks it lands inside.
ptz_bolt_min  = 70;
ptz_bolt_max  = 104;
ptz_slot_w    = 3.4;           // M3 clearance
// The ribbon and the leads leave the camera head at the top, drape over the
// turntable and come in through a slot at the back of the lid (fit.py sizes
// it to the ribbon and places it clear of the bolt slots and the lid screws).
ptz_loop      = 60;            // free ribbon kept outside for the pan and tilt travel

// ---- battery tray ----------------------------------------------------------
// Sized to the power bank in ordered_parts.toml. The tray stays strapped to a
// tripod leg or the centre column; the bank clips in and out of it without
// touching the strap, so a flat bank is swapped for a full one in seconds.
tray_wall = 2.4;
tray_clr = 0.6;                // round the bank, so it drops in
tray_snap = 1.4;               // how far the lips along the top reach over the bank
tray_lip_t = 1.6;              // their thickness (the top is chamfered as a lead-in)
tray_notch_w = 34;             // finger notches half-way along each long side
tray_strap_w = 26;             // hook-and-loop strap, through two tunnels under the floor
tray_tunnel_h = 3.5;

// ---- solved layout ---------------------------------------------------------
include <layout.scad>          // GENERATED by cad/fit.py — bought-part sizes + layout

R_in = base_d / 2 - base_wall; // inside of the wall
