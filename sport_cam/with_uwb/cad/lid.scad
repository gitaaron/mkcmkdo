// Enclosure lid — the structural interface between the tripod and the camera.
// The Arducam pan-tilt base is a round turntable on four brass standoffs, its
// pan servo hanging underneath between them. It stands on the lid on those
// standoffs; four M3 screws come up through the lid into them.
//
// The standoff pattern is cut as four radial SLOTS spanning
// ptz_slot_min..ptz_slot_max (config.scad's range, stretched by fit.py if
// your base's measured spacing is outside it), because Arducam publishes no
// drawing for it. If the screws in ordered_parts.toml are too short to reach
// far enough into the standoffs, fit.py counterbores the underside along each
// slot (lid_screw_recess) so the heads sit higher.
//
// Every cable leaves the camera head at the top — nothing comes down through
// the base — so the ribbon and the leads drape over the turntable and enter
// through the cable slot at the back of the lid.
//
// A ring under the lid drops into the enclosure mouth to locate it; four
// radial M3 screws through the wall go into heat-set inserts in that ring.
// Print top face down.
include <config.scad>

module mount_slots() {
    for (a = ptz_bolt_angs)
        rotate([0, 0, a]) {
            hull() for (r = [ptz_slot_min / 2, ptz_slot_max / 2])
                translate([r, 0, -1]) cylinder(d = ptz_slot_w, h = lid_t + 2, $fn = 24);
            if (lid_screw_recess > 0)
                hull() for (r = [ptz_slot_min / 2, ptz_slot_max / 2])
                    translate([r, 0, -1]) cylinder(d = ptz_head_d + 1, h = lid_screw_recess + 1, $fn = 32);
        }
}

// ribbon + leads: an obround, long side along the wall
module cable_slot() {
    rotate([0, 0, cable_slot_ang]) translate([cable_slot_r, 0, -1])
        hull() for (s = [-1, 1])
            translate([0, s * (cable_slot_w - cable_slot_d) / 2, 0]) cylinder(d = cable_slot_d, h = lid_t + 2, $fn = 32);
}

module spigot() {
    ro = R_in - clr;
    translate([0, 0, -spigot_h]) difference() {
        union() {
            difference() {
                cylinder(r = ro, h = spigot_h);
                translate([0, 0, -1]) cylinder(r = ro - spigot_w, h = spigot_h + 2);
            }
            for (a = lid_screw_angs) rotate([0, 0, a])
                intersection() {
                    translate([ro - lid_screw_pad, -5, 0]) cube([lid_screw_pad, 10, spigot_h]);
                    cylinder(r = ro, h = spigot_h);
                }
        }
        // radial M3 heat-set inserts, lined up with the holes in the wall
        for (a = lid_screw_angs) rotate([0, 0, a])
            translate([ro - 6.5, 0, spigot_h / 2]) rotate([0, 90, 0]) cylinder(d = 4.0, h = 7, $fn = 24);
    }
}

module lid() {
    difference() {
        union() {
            cylinder(d = base_d, h = lid_t);
            spigot();
        }
        cable_slot();
        mount_slots();
    }
}

lid();
