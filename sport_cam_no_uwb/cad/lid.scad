// Enclosure lid — the structural interface between the tripod and the camera.
// The Arducam metal pan-tilt base bolts down onto it; the CSI ribbon and the
// servo/I2C leads drop through the central opening to the Pi below.
//
// The base's bolt pattern is cut as four radial SLOTS spanning
// ptz_bolt_min..ptz_bolt_max, because Arducam publishes no drawing for it and
// the footprint differs between revisions. Measure yours, mark through the
// slots, and bolt it down with M3 and nuts.
include <config.scad>

module mount_slots() {
    // Two slot pairs at 90°, each running radially across the accepted range
    for (a = [0, 90, 180, 270])
        rotate([0, 0, a])
            hull() for (r = [ptz_bolt_min / 2, ptz_bolt_max / 2])
                translate([r, 0, -1]) cylinder(d = ptz_slot_w, h = lid_t + 2, $fn = 24);
}

module lid() {
    difference() {
        union() {
            cylinder(d = base_d, h = lid_t);
            // spigot that locates the lid in the enclosure mouth
            translate([0, 0, -4])
                cylinder(d = base_d - 2 * base_wall - 2 * clr, h = 4);
        }
        // central opening for the camera ribbon + servo leads
        translate([0, 0, -6]) cylinder(d = ptz_cable_d, h = lid_t + 8);
        mount_slots();
        // fixing screws down into the enclosure wall
        for (a = [45:90:315])
            rotate([0, 0, a]) translate([base_d / 2 - base_wall / 2 - 1.2, 0, -1]) {
                cylinder(d = 3.2, h = lid_t + 2, $fn = 24);
                translate([0, 0, lid_t - 2.4]) cylinder(d = 6.2, h = 3, $fn = 24);  // countersink
            }
    }
}

lid();
