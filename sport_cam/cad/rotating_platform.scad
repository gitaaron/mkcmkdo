// Rotating platform: carries Pi 5, bucks #2/#3, tilt tower, anchor arms.
// Lazy-susan top plate and ring pulley bolt underneath; slip-ring wires
// pass through the centre.
include <config.scad>

module bolt_pattern(spacing, d, depth) {
    for (x = [-1, 1], y = [-1, 1])
        translate([x * spacing / 2, y * spacing / 2, 0])
            cylinder(d = d, h = depth);
}

module pi_standoffs() {
    // Pi sits left of centre, USB/ethernet edge outward
    translate([-plat_d / 4 - 5, 0, plat_t])
        for (x = [-1, 1], y = [-1, 1])
            translate([x * pi_hole_dx / 2, y * pi_hole_dy / 2, 0])
                difference() {
                    cylinder(d = 7, h = pi_standoff_h);
                    cylinder(d = 2.4, h = pi_standoff_h + 1);   // M2.5 thread-form
                }
}

module tower_feet_slots() {
    // Two rectangular slots + screw holes accept the tilt-tower feet
    for (s = [-1, 1])
        translate([plat_d / 4 - 6, s * (tower_gap / 2 + tower_t / 2), 0]) {
            translate([0, 0, -1]) cube([tower_w + 2 * clr, tower_t + 2 * clr, plat_t + 2], center = true);
            for (x = [-1, 1])
                translate([x * (tower_w / 2 + 6), 0, -1]) cylinder(d = 3.2, h = plat_t + 2);
        }
}

module arm_sockets() {
    // Anchor arms bolt flat on the underside pointing ±Y (perpendicular to lens axis +X)
    for (s = [-1, 1])
        translate([0, s * (plat_d / 2 - 14), 0])
            for (x = [-1, 1])
                translate([x * 9, 0, -1]) cylinder(d = 3.2, h = plat_t + 2);
}

module rotating_platform() {
    difference() {
        cylinder(d = plat_d, h = plat_t);
        // centre pass-through for slip-ring wires
        translate([0, 0, -1]) cylinder(d = sr_wire_d + 6, h = plat_t + 2);
        // lazy-susan top-plate bolts
        translate([0, 0, -1]) bolt_pattern(ls_bolt, ls_hole_d, plat_t + 2);
        // ring-pulley bolts (6 × M3, matches ring_pulley.scad)
        for (a = [0:60:300])
            rotate([0, 0, a + 30])
                translate([(ring_id / 2 + ring_pitch_r + 0.38) / 2, 0, -1])
                    cylinder(d = 3.2, h = plat_t + 2, $fn = 24);
        tower_feet_slots();
        arm_sockets();
        // buck mounting holes (2 modules, M3 pairs)
        for (p = [[-20, 45], [-20, -45]])
            translate([p[0], p[1], 0])
                for (x = [-1, 1])
                    translate([x * 8, 0, -1]) cylinder(d = 3.2, h = plat_t + 2);
    }
    pi_standoffs();
}

rotating_platform();
