// SportCam — shared parametric dimensions (mm).
// Every part file includes this; tweak here, re-render, everything stays consistent.

$fn = 96;
clr = 0.25;                    // general printed-fit clearance per side

// ---- pan stage -------------------------------------------------------------
base_d        = 150;           // base housing outer diameter
base_h        = 62;            // base housing height
base_wall     = 3;

ls_size       = 76.2;          // 3" lazy-susan square plate
ls_bolt       = 66;            // bolt spacing (square)
ls_hole_d     = 5;             // M5-ish mounting holes
ls_thick      = 8;             // bearing stack height

sr_body_d     = 22.5;          // slip ring body (Adafruit 736 class)
sr_flange_d   = 44.5;          // stationary flange diameter
sr_flange_t   = 2.5;
sr_hole_space = 33;            // two flange screw holes, M3
sr_wire_d     = 14;            // wire bundle pass-through

nema_face     = 42.3;          // NEMA17
nema_bolt     = 31;            // M3 square pattern
nema_boss_d   = 22.5;
nema_shaft_d  = 5;

// ---- belt drive ------------------------------------------------------------
gt2_pitch       = 2.0;
ring_teeth      = 120;         // printed ring pulley (6:1 with 20T motor pulley)
ring_pitch_r    = ring_teeth * gt2_pitch / (2 * PI);   // ≈ 38.2
ring_id         = 60;          // clears the 44.5 slip-ring flange with margin
pulley_h        = 8;           // belt is 6 mm wide
flange_lip      = 1.5;

// ---- rotating platform -----------------------------------------------------
plat_d        = 160;
plat_t        = 5;
plat_bolt_circle = 70;         // M3 bosses meeting the lazy-susan top plate

pi_l = 85; pi_w = 56;          // Raspberry Pi 5
pi_hole_dx = 58; pi_hole_dy = 49;
pi_hole_off = 3.5;             // hole inset from board corner
pi_standoff_h = 6;

// ---- tilt ------------------------------------------------------------------
servo_l = 40.5; servo_w = 20.2; servo_h = 38.5;   // DS3225 body
servo_tab_l = 54.5;            // over mounting tabs
servo_hole_dx = 49.5; servo_hole_dy = 10;         // 4 × M4 tab holes
servo_axis_off = 9.9;          // spline axis from body front face

tilt_bearing_od = 18; tilt_bearing_w = 4;         // 6701ZZ
tilt_shaft_d = 12;
tower_h = 90;                  // tilt-axis height above platform
tower_w = 30; tower_t = 12;
tower_gap = 90;                // clear width between the two uprights

// ---- camera cradle ---------------------------------------------------------
lens_d = 33;                   // Arducam zoom-lens barrel — MEASURE YOURS
cam_board_w = 25;              // IMX219 board width behind lens
horn_d = 21;                   // DS3225 round metal horn
horn_screw_circle = 14;        // 4 × M3 on the horn
cradle_w = 60;

// ---- UWB anchor arm --------------------------------------------------------
arm_len = 200;                 // baseline = 2 × arm_len = 400
arm_w = 18; arm_t = 8;
uwb_l = 55; uwb_w = 30;        // ESP32-UWB board
uwb_hole_dx = 49; uwb_hole_dy = 24;               // corner holes — MEASURE YOURS

// ---- wearable pod ----------------------------------------------------------
pod_inner_l = 58; pod_inner_w = 33; pod_inner_h = 22;  // board + LiPo + TP4056
pod_wall = 2.0;
strap_w = 26;                  // elastic armband width
