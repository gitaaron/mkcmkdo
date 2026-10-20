// Pi shelf. Rests on the three posts in the enclosure wall, screwed into the
// heat-set inserts in their tops (M3 × 8). The Raspberry Pi sits on top on
// M2.5 nylon standoffs; the LED ring hangs underneath on foam tape, LEDs
// down, so it lights the window between the power boards and the shelf.
//
// One side is cut away along a chord: the Pi's USB-C pigtail, the gauge's
// I2C leads, the PTZ controller's 5 V and the LED ring's leads pass between
// the floor and the shelf through that gap.
//
// The shelf's size, the gap, the posts and the Pi's holes all come from
// layout.scad (cad/fit.py). Print flat, 3 walls, 20 %; white or natural
// PETG helps the ring's light reach the window.
include <config.scad>

module shelf() {
    difference() {
        intersection() {
            cylinder(r = shelf_r, h = shelf_t);
            // keep the side of the chord away from the cable gap
            rotate([0, 0, gap_ang]) translate([gap_d - 400, -200, -1]) cube([400, 400, shelf_t + 2]);
        }
        for (a = post_angs) rotate([0, 0, a]) translate([post_r, 0, -1])
            cylinder(d = 3.4, h = shelf_t + 2, $fn = 24);
        for (p = pi_holes) translate([p[0], p[1], -1])
            cylinder(d = pi_hole_d, h = shelf_t + 2, $fn = 24);
        // centre mark for sticking the LED ring on concentric
        translate([0, 0, -1]) cylinder(d = 4, h = shelf_t + 2, $fn = 24);
    }
}

shelf();
