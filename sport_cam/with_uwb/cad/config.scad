// SportCam — shared parametric dimensions (mm).
// Every part file includes this; tweak here, re-render, everything stays consistent.
//
// This is the **PTZ-base build**: the camera, pan and tilt all come from the
// Arducam IMX477 PTZ camera with metal pan-tilt base (B0167B12), which bolts
// to the lid of a static enclosure. There is no pan stage, slip ring or
// tilt tower to print — see docs/02-hardware-mechanical.md.

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

// ---- UWB anchor arms (now static) ------------------------------------------
// The anchors no longer rotate with the camera, so the arms bolt to the
// enclosure wall. Board centres land `uwb_half_base` either side of the pan
// axis; the tracker subtracts the commanded pan angle (docs/04).
uwb_half_base = 125;           // half the baseline → 250 mm anchor separation
arm_w = 18; arm_t = 8;
arm_root_h = 24;               // bracket height where the arm meets the wall
arm_insert_d = 4.0;            // M3 heat-set inserts in the arm root
uwb_l = 40; uwb_w = 25;        // Haorutech ULA1 board — MEASURE YOURS
uwb_hole_dx = 32; uwb_hole_dy = 17;               // corner holes — MEASURE YOURS
                               // The ULA1's USB-A plug sticks out past uwb_l;
                               // the pad is cut long enough to clear it.

arm_boss_r = base_d / 2 + 4;  // outer face of the wall boss the arm bolts to
arm_len = uwb_half_base - arm_boss_r;             // boss face to board centre

// ---- third anchor mast (A3) ------------------------------------------------
// A3 gives elevation, which the horizontal A1-A2 bar cannot. It stands on a
// bought ½-inch hardwood dowel held in a printed foot on a third wall boss at
// −X — directly behind the lens, where pan (±80°) never points it — with a
// printed cradle carrying the board at the top. Wood, not metal: a metal
// tube right under a UWB antenna detunes it.
anchor_board_z = 22;           // A1/A2 board height above the enclosure floor
uwb_v_base  = 250;             // A3 board this far above A1/A2 (= σφ baseline)
mast_d      = 12.7;            // ½" dowel — MEASURE YOURS, they run ±0.3 mm
mast_wall   = 4;               // socket wall
mast_floor  = 2;               // closed socket bottom; sets the dowel's height
mast_foot_h = 44;              // foot socket depth: long, so the mast stands still
mast_cap_h  = 30;              // cradle socket depth
mast_bore   = mast_d + 2 * clr;
mast_sock_r = mast_bore / 2 + mast_wall;

// mast axis from the pan axis: boss face, 6 mm root plate, socket, 2 mm overlap.
// device/sportcam/config.py UWB_A3_BACK_M must match (in metres).
mast_axis_r = arm_boss_r + 6 + mast_sock_r - 2;
// The cradle puts the board mast_floor + arm_t + 4 above the dowel top
// (socket floor, pad, standoffs), and the foot's floor sits on the boss at
// z = 10, so cut the dowel to this:
cradle_rise  = mast_floor + arm_t + 4;
mast_dowel_l = anchor_board_z + uwb_v_base - cradle_rise - (10 + mast_floor);

// ---- battery tray ----------------------------------------------------------
// Sized to a 25 000 mAh USB-C PD power bank. MEASURE YOURS — banks of the
// same capacity vary by 15 mm in every direction. The tray straps to a tripod
// leg or centre column, or sandwiches under the enclosure on a long 1/4-20
// (into the reducer bushing).
bank_l = 150; bank_w = 72; bank_h = 30;
tray_wall = 2.4;
tray_lip = 10;                 // how far the side walls come up the bank
tray_strap_w = 26;             // hook-and-loop strap slots

// ---- wearable pod ----------------------------------------------------------
// The ULA1 is 5 V USB with no battery connector, so the tag is the module
// plugged into a small USB power bank rather than a board over a LiPo. Both
// lie side by side; measure your bank, they vary a lot.
bank_tag_l = 95; bank_tag_w = 23; bank_tag_h = 23;     // "lipstick" 2500 mAh
pod_inner_l = bank_tag_l + 5;
pod_inner_w = bank_tag_w + uwb_w + 4;
pod_inner_h = max(bank_tag_h, 12) + 2;
pod_wall = 2.0;
strap_w = 26;                  // elastic armband width
