// SportCam — parametric dimensions (mm). Every part file includes this.
//
// Three kinds of number feed the CAD:
//   * design choices — wall thickness, clearances, the anchor baseline — set below;
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

tripod_boss_d = 24;            // floor boss for the 3/8-16 insert (bore from ordered_parts.toml)
tripod_boss_h = 8;

tape_t        = 1;             // foam tape under the power boards and the LED ring
part_gap      = 2;             // clearance fit.py keeps between parts
wall_gap      = 1;             // and between a part and the wall
shelf_t       = 3;             // the Pi shelf
post_d        = 10;            // shelf posts, merged into the wall; M3 insert in each top
post_insert_d = 4.0;
vent_w        = 4;
vent_h        = 8;
ribbon_slack_h = 8;            // clear height kept under the lid opening for the coiled camera ribbon

// ---- Arducam pan-tilt base interface ---------------------------------------
// Arducam publishes no drawing for the B0167B12 metal base and the footprint
// has changed between revisions, so the lid is cut with radial SLOTS spanning
// this range. Your base's spacing goes in ordered_parts.toml [ptz]; the audit
// checks it lands inside.
ptz_bolt_min  = 30;
ptz_bolt_max  = 72;
ptz_slot_w    = 3.4;           // M3 clearance
ptz_cable_d   = 34;            // central opening: CSI ribbon + servo leads drop through

// ---- UWB anchor arms (static) ----------------------------------------------
// The anchors don't rotate with the camera, so the arms bolt to the enclosure
// wall. Board centres land `uwb_half_base` either side of the pan axis; the
// tracker subtracts the commanded pan angle (docs/04).
uwb_half_base = 190;           // board centre; the antenna sits 10 mm further out → 400 mm
arm_w = 18; arm_t = 8;
arm_root_h = 24;               // bracket height where the arm meets the wall
arm_boss_z = 10;               // bottom of the wall bosses
arm_insert_d = 4.0;            // M3 heat-set inserts in the bosses
ula1_standoff_h = 3;

// ---- third anchor mast (A3) ------------------------------------------------
// A3 gives elevation, which the horizontal A1-A2 bar cannot. It stands on a
// bought ½-inch hardwood dowel held in a printed foot on a third wall boss at
// −X — directly behind the lens, where pan (±80°) never points it — with a
// printed cradle carrying the board at the top. Wood, not metal: a metal
// tube right under a UWB antenna detunes it.
anchor_board_z = 22;           // A1/A2 board height above the enclosure floor
uwb_v_base  = 250;             // A3 board this far above A1/A2 (= σφ baseline)
mast_wall   = 4;               // socket wall
mast_floor  = 2;               // closed socket bottom; sets the dowel's height
mast_foot_h = 44;              // foot socket depth: long, so the mast stands still
mast_cap_h  = 30;              // cradle socket depth

// ---- battery tray ----------------------------------------------------------
// Sized to the power bank in ordered_parts.toml. Straps to a tripod leg or
// centre column, or sandwiches under the enclosure on a long 1/4-20.
tray_wall = 2.4;
tray_lip = 10;                 // how far the side walls come up the bank
tray_strap_w = 26;             // hook-and-loop strap slots

// ---- wearable pod ----------------------------------------------------------
// The tag is a ULA1 plugged straight into a slim USB bank, end to end; fit.py
// sizes the pod from both (ordered_parts.toml).
pod_wall = 2.0;
strap_w = 26;                  // elastic armband width
pod_max_l = 150;               // longest pod that's still comfortable on an arm

// ---- solved layout ---------------------------------------------------------
include <layout.scad>          // GENERATED by cad/fit.py — bought-part sizes + layout

R_in = base_d / 2 - base_wall; // inside of the wall
tripod_hole_d = insert_od;     // the 3/8-16 insert, epoxied: a snug slip fit

arm_boss_r = base_d / 2 + 4;   // outer face of the wall boss the arm bolts to
arm_len = uwb_half_base - arm_boss_r;             // boss face to board centre

// ULA1 pad. fit.py turns the boards across the arms (plug towards −X) when
// the extension cable's socket end has no room between the plug and the
// enclosure; the pad and holes follow.
pad_along   = ula1_tangential ? uwb_w + 12 : uwb_l + 12;
pad_across  = ula1_tangential ? uwb_l : uwb_w;
hole_along  = ula1_tangential ? uwb_hole_dy : uwb_hole_dx;
hole_across = ula1_tangential ? uwb_hole_dx : uwb_hole_dy;

mast_bore   = mast_d + 2 * clr;
mast_sock_r = mast_bore / 2 + mast_wall;
// mast axis from the pan axis: boss face, 6 mm root plate, socket, 2 mm overlap.
// fit.py keeps device/sportcam/config.py UWB_A3_BACK_M in step.
mast_axis_r = arm_boss_r + 6 + mast_sock_r - 2;
// The cradle puts the board mast_floor + arm_t + 4 above the dowel top
// (socket floor, pad, standoffs), and the foot's floor sits on the boss at
// z = arm_boss_z, so cut the dowel to this:
cradle_rise  = mast_floor + arm_t + 4;
mast_dowel_l = anchor_board_z + uwb_v_base - cradle_rise - (arm_boss_z + mast_floor);
