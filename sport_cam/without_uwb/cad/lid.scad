// Enclosure lid — the structural interface between the tripod and the camera.
// The Arducam metal pan-tilt base bolts down onto it; the CSI ribbon and the
// servo/I2C leads drop through the central opening to the Pi below.
//
// The base's bolt pattern is cut as four radial SLOTS spanning
// ptz_slot_min..ptz_slot_max (config.scad's range, stretched by fit.py if
// your base's measured spacing is outside it), because Arducam publishes no drawing for it and
// the footprint differs between revisions. Measure yours, mark through the
// slots, and bolt it down with M3 and nuts. If the screws in
// ordered_parts.toml are too short to take a full nut, fit.py relieves the
// underside along each slot (lid_nut_recess) so the nut sits higher.
//
// A ring under the lid drops into the enclosure mouth to locate it; four
// radial M3 screws through the wall go into heat-set inserts in that ring.
// Print top face down.
include <config.scad>

module mount_slots() {
    for (a = [0, 90, 180, 270])
        rotate([0, 0, a]) {
            hull() for (r = [ptz_slot_min / 2, ptz_slot_max / 2])
                translate([r, 0, -1]) cylinder(d = ptz_slot_w, h = lid_t + 2, $fn = 24);
            if (lid_nut_recess > 0)
                hull() for (r = [ptz_slot_min / 2, ptz_slot_max / 2])
                    translate([r, 0, -1]) cylinder(d = ptz_nut_af / cos(30) + 0.6, h = lid_nut_recess + 1, $fn = 6);
        }
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
        // central opening for the camera ribbon + servo leads
        translate([0, 0, -1]) cylinder(d = ptz_cable_d, h = lid_t + 2);
        mount_slots();
    }
}

lid();
