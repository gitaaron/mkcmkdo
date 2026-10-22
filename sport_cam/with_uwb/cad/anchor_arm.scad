// Static UWB anchor arm (×2). Bolts to the enclosure's side boss and reaches
// out so the board centre sits uwb_half_base from the pan axis — 400 mm
// between the two antennas by default.
//
// The arms no longer rotate with the camera, so they can be longer than the
// old rotating pair if you want better bearing resolution: raise
// `uwb_half_base` in config.scad (σθ scales as 1/baseline, docs/04).
// The ULA1 sits on the pad either along the arm (USB plug towards the
// enclosure) or across it (plug towards −X). cad/fit.py picks: along needs
// room between the plug and the arm's root for the extension cable's rigid
// socket end, and with the assumed sizes there isn't, so the boards go across
// and the cable runs off to the side. pad_* and hole_* in config.scad follow.
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
                cube([arm_len + pad_along / 2, arm_w, arm_t]);
            // stiffening rib, on top of the arm
            translate([0, 6 + arm_w / 2 - 2, arm_t])
                cube([arm_len - pad_along / 2, 4, rib_h]);
            // board pad at the tip
            translate([arm_len - pad_along / 2, 6 + arm_w / 2 - pad_across / 2, 0])
                cube([pad_along, pad_across, arm_t]);
            root_bracket();
        }
        // board standoff holes — M2.5; the pattern is in ordered_parts.toml [ula1]
        translate([arm_len, 6 + arm_w / 2, -1])
            for (x = [-1, 1], y = [-1, 1])
                translate([x * hole_along / 2, y * hole_across / 2, 0])
                    cylinder(d = 2.2, h = arm_t + 2, $fn = 24);
        // weight relief
        for (x = [30:22:arm_len - pad_along / 2 - 20])
            translate([x, 6 + arm_w / 2, -1])
                cylinder(d = 10, h = arm_t + 2, $fn = 32);
    }
}

anchor_arm();
