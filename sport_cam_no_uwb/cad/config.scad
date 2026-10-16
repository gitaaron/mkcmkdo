// SportCam — shared parametric dimensions (mm).
// Every part file includes this; tweak here, re-render, everything stays consistent.
//
// This is the **PTZ-base build**: the camera, pan and tilt all come from the
// Arducam IMX477 PTZ camera with metal pan-tilt base (B0167B12), which bolts
// to the lid of a static enclosure. There is no pan stage, slip ring or
// tilt tower to print — see docs/02-hardware-mechanical.md.
//
// This is the **camera-only variant**: no UWB anchors, no mast, no wearable.
// The camera finds and follows a person by vision alone.

$fn = 96;
clr = 0.25;                    // general printed-fit clearance per side

// ---- enclosure -------------------------------------------------------------
// Holds the Pi 5 (85 × 56) flat on standoffs, the 5 V distribution and the
// LED ring. The lid carries the Arducam pan-tilt base.
base_d        = 135;           // outer diameter — the Pi plus the power boards
                               // need this much floor; see base_housing.scad
base_h        = 66;            // floor to lid underside
base_wall     = 3;
lid_t         = 5;             // lid is structural: it carries the whole camera
led_window_h  = 12;            // circumferential LED slot
led_window_z  = 20;

jack_d        = 8.2;           // 5 V barrel jack, panel mount
// Tripod socket: a 3/8-16 brass insert, which takes a 3/8-16 tripod screw
// directly and a 1/4-20 one through a removable 3/8→1/4 reducer bushing —
// so it fits every photo and video tripod. The boss is 8 mm tall because
// the Pi sits 6 mm above the floor over it: use an insert no longer than
// that (or file one down).
tripod_boss_d = 24;
tripod_boss_h = 8;
tripod_hole_d = 12.7;          // MEASURE YOUR INSERT: epoxied, so a snug slip fit

pi_l = 85; pi_w = 56;          // Raspberry Pi 5
pi_hole_dx = 58; pi_hole_dy = 49;
pi_standoff_h = 6;
pi_x_off      = -10;           // Pi sits off-centre, leaving the +X side for power

// ---- Arducam pan-tilt base interface ---------------------------------------
// MEASURE YOURS. Arducam publishes no drawing for the B0167B12 metal base and
// the footprint has changed between revisions, so the lid is cut with **slots**
// spanning the range below rather than fixed holes. If your base's bolt
// spacing falls outside it, edit these two numbers and re-render.
ptz_bolt_min  = 30;            // narrowest bolt spacing the slots accept
ptz_bolt_max  = 72;            // widest
ptz_slot_w    = 3.4;           // M3 clearance
ptz_cable_d   = 34;            // central opening: CSI ribbon + servo leads drop through

// ---- battery tray ----------------------------------------------------------
// Sized to a 25 000 mAh USB-C PD power bank. MEASURE YOURS — banks of the
// same capacity vary by 15 mm in every direction. The tray straps to a tripod
// leg or centre column, or sandwiches under the enclosure on a long 1/4-20
// (into the reducer bushing).
bank_l = 150; bank_w = 72; bank_h = 30;
tray_wall = 2.4;
tray_lip = 10;                 // how far the side walls come up the bank
tray_strap_w = 26;             // hook-and-loop strap slots
