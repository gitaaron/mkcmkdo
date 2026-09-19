// UWB anchor arm: 200 mm, bolts flat under the platform edge, board pocket
// at the far end (antenna outboard, clear of the platform).
// Print flat, 4+ perimeters.
include <config.scad>

rib_h = 6;

module anchor_arm() {
    difference() {
        union() {
            cube([arm_len, arm_w, arm_t]);
            // stiffening rib
            translate([0, arm_w / 2 - 2, arm_t]) cube([arm_len - uwb_l - 10, 4, rib_h]);
            // board platform at the tip
            translate([arm_len - uwb_l - 6, -(uwb_w - arm_w) / 2, 0])
                cube([uwb_l + 6, uwb_w, arm_t]);
        }
        // platform-side bolt holes (matches arm_sockets in rotating_platform.scad)
        for (x = [6, 24])
            translate([x, arm_w / 2, -1]) cylinder(d = 3.2, h = arm_t + rib_h + 2, $fn = 24);
        // board standoff holes — M2.5, MEASURE your board's hole pattern
        translate([arm_len - uwb_l / 2 - 3, arm_w / 2, 0])
            for (x = [-1, 1], y = [-1, 1])
                translate([x * uwb_hole_dx / 2, y * uwb_hole_dy / 2, -1])
                    cylinder(d = 2.2, h = arm_t + 2, $fn = 24);
        // weight relief
        for (x = [40:22:arm_len - uwb_l - 30])
            translate([x, arm_w / 2, -1]) cylinder(d = 10, h = arm_t + 2, $fn = 32);
    }
}

anchor_arm();
