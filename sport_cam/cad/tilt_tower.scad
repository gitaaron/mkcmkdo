// Tilt tower upright. Render twice:
//   side = "servo"   — pocket for the DS3225, tab screw holes
//   side = "bearing" — press-fit seat for the 6701ZZ bearing
// Feet drop into the platform slots and screw down from below.
include <config.scad>

side = "servo";                // override with -D side=\"bearing\"

foot_l = tower_w + 24;

module foot() {
    translate([0, 0, plat_t / 2])
        difference() {
            cube([foot_l, tower_t, plat_t], center = true);
            for (x = [-1, 1])
                translate([x * (tower_w / 2 + 6), 0, 0])
                    cylinder(d = 3.2, h = plat_t + 2, center = true);
        }
    // tenon that drops into the platform slot
    translate([0, 0, -plat_t / 2 + 0.01])
        cube([tower_w, tower_t, plat_t], center = true);
}

module upright() {
    difference() {
        hull() {
            translate([0, 0, 2]) cube([tower_w, tower_t, 4], center = true);
            translate([0, 0, tower_h]) rotate([90, 0, 0])
                cylinder(d = tower_w, h = tower_t, center = true);
        }
        // lightening window
        translate([0, 0, tower_h * 0.45])
            cube([tower_w - 12, tower_t + 2, tower_h * 0.5], center = true);
    }
}

module servo_head() {
    // DS3225 nests through a rectangular window; tabs screw to the face
    translate([0, 0, tower_h]) rotate([90, 0, 0]) {
        translate([-(servo_tab_l + 10) / 2, -(servo_w + 10) / 2, -tower_t / 2]) difference() {
            cube([servo_tab_l + 10, servo_w + 10, tower_t], center = false);
            translate([5 + (servo_tab_l - servo_l) / 2, 5, -1])
                cube([servo_l + 2 * clr, servo_w + 2 * clr, tower_t + 2]);
            for (x = [-1, 1], y = [-1, 1])
                translate([5 + servo_tab_l / 2 + x * servo_hole_dx / 2,
                           5 + servo_w / 2 + y * servo_hole_dy / 2, -1])
                    cylinder(d = 4.2, h = tower_t + 2, $fn = 24);
        }
    }
}

module bearing_head() {
    translate([0, 0, tower_h]) rotate([90, 0, 0])
        difference() {
            cylinder(d = tilt_bearing_od + 8, h = tower_t, center = true);
            // press-fit seat, open one side
            translate([0, 0, tower_t / 2 - tilt_bearing_w])
                cylinder(d = tilt_bearing_od + 2 * 0.1, h = tilt_bearing_w + 1);
            cylinder(d = tilt_bearing_od - 3, h = tower_t + 2, center = true);
        }
}

module tilt_tower() {
    foot();
    upright();
    if (side == "servo") servo_head();
    else bearing_head();
}

tilt_tower();
