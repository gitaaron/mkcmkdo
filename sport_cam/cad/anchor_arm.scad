// Static UWB anchor arm (×2). Bolts to the enclosure's side boss and reaches
// out so the board centre sits uwb_half_base from the pan axis — 250 mm
// between the two antennas by default.
//
// The arms no longer rotate with the camera, so they can be longer than the
// old rotating pair if you want better bearing resolution: raise
// `uwb_half_base` in config.scad (σθ scales as 1/baseline, docs/04).
// Print flat, 4+ perimeters.
include <config.scad>

rib_h = 6;

module root_bracket() {
    // Vertical plate that mates with the enclosure's arm boss
    difference() {
        cube([arm_w, 6, arm_root_h]);
        for (z = [6, 18])
            translate([arm_w / 2, -1, z]) rotate([-90, 0, 0])
                cylinder(d = 3.4, h = 8, $fn = 24);
    }
}

// The arm body sits ON the bed (z = 0) rather than mid-way up the bracket, so
// the whole part prints flat with no supports under the span.
module anchor_arm() {
    difference() {
        union() {
            // the arm itself, lying along +X from the bracket face
            translate([0, 6, 0])
                cube([arm_len + uwb_l / 2 + 6, arm_w, arm_t]);
            // stiffening rib, on top of the arm
            translate([0, 6 + arm_w / 2 - 2, arm_t])
                cube([arm_len - uwb_l / 2, 4, rib_h]);
            // board pad at the tip
            translate([arm_len - uwb_l / 2 - 6, 6 - (uwb_w - arm_w) / 2, 0])
                cube([uwb_l + 12, uwb_w, arm_t]);
            root_bracket();
        }
        // board standoff holes — M2.5, MEASURE your board's hole pattern
        translate([arm_len, 6 + arm_w / 2, -1])
            for (x = [-1, 1], y = [-1, 1])
                translate([x * uwb_hole_dx / 2, y * uwb_hole_dy / 2, 0])
                    cylinder(d = 2.2, h = arm_t + 2, $fn = 24);
        // weight relief
        for (x = [30:22:arm_len - uwb_l / 2 - 20])
            translate([x, 6 + arm_w / 2, -1])
                cylinder(d = 10, h = arm_t + 2, $fn = 32);
    }
}

anchor_arm();
