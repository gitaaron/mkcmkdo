// Static enclosure: Raspberry Pi 5, 5 V distribution, WS2812B ring.
// The lid carries the Arducam pan-tilt base. Nothing rotates — there is no
// pan stage — and with camera-only tracking there is nothing else to mount:
// the wall is plain all the way round.
//
// Renders the body; `lid.scad` is the separate top plate.
include <config.scad>

module vent_slot() {
    hull() {
        cylinder(d = 4, h = base_wall * 4, center = true);
        translate([0, 4, 0]) cylinder(d = 4, h = base_wall * 4, center = true);
    }
}

module pi_standoffs() {
    // Pi lies flat on the floor, long axis along X, shifted to -X so the
    // PD trigger, buck and INA226 get the +X side of the floor
    for (x = [-1, 1], y = [-1, 1])
        translate([pi_x_off + x * pi_hole_dx / 2, y * pi_hole_dy / 2, base_wall])
            difference() {
                cylinder(d = 7, h = pi_standoff_h);
                cylinder(d = 2.4, h = pi_standoff_h + 1);   // M2.5 thread-form
            }
}

module power_standoffs() {
    // Buck, PD trigger and INA226 on the +X side of the floor, on M3 posts
    for (p = [[46, -18], [46, 18], [46, 0]])
        translate([p[0], p[1], base_wall])
            difference() {
                cylinder(d = 7, h = 4);
                cylinder(d = 2.9, h = 5);
            }
}

module base_housing() {
    difference() {
        union() {
            cylinder(d = base_d, h = base_h);
            // tripod boss on the floor: 3/8-16 insert, 1/4-20 via bushing
            cylinder(d = tripod_boss_d, h = tripod_boss_h);
        }
        // hollow interior
        translate([0, 0, base_wall])
            cylinder(d = base_d - 2 * base_wall, h = base_h);
        // LED window — full 360° band (diffuser ring closes it)
        translate([0, 0, led_window_z])
            difference() {
                cylinder(d = base_d + 2, h = led_window_h);
                cylinder(d = base_d - 2 * base_wall - 2, h = led_window_h);
            }
        // 5 V barrel jack, low on the −Y wall
        translate([0, -base_d / 2, 11]) rotate([90, 0, 0])
            cylinder(d = jack_d, h = 3 * base_wall, center = true);
        // tripod insert bore
        translate([0, 0, -1]) cylinder(d = tripod_hole_d, h = tripod_boss_h + 1);
        // vents: the Pi's blower needs a path, and the lid is sealed by the base
        for (a = [25:25:155])
            rotate([0, 0, a]) translate([0, base_d / 2, 9]) rotate([90, 0, 0]) vent_slot();
        for (a = [205:25:335])
            rotate([0, 0, a]) translate([0, base_d / 2, 9]) rotate([90, 0, 0]) vent_slot();
        // lid screws: 4 × M3 into the wall top
        for (a = [45:90:315])
            rotate([0, 0, a]) translate([base_d / 2 - base_wall / 2 - 1.2, 0, base_h - 12])
                cylinder(d = 2.6, h = 13, $fn = 24);
    }
    pi_standoffs();
    power_standoffs();
}

base_housing();
