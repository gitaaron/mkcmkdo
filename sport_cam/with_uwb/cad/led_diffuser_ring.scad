// Translucent band over the enclosure's LED window. It slides down over the
// outside of the enclosure (lid off) and rests on the small ledge below the
// window, overlapping the wall above and below by diffuser_lip; a few dabs of
// glue hold it. The LED ring inside lights it from behind.
//
// Print in white or natural PETG, 2 perimeters, 0 % infill, no top/bottom.
include <config.scad>

module led_diffuser_ring() {
    id = base_d + 2 * clr;
    difference() {
        cylinder(d = id + 2 * diffuser_t, h = led_window_h + 2 * diffuser_lip);
        translate([0, 0, -1]) cylinder(d = id, h = led_window_h + 2 * diffuser_lip + 2);
    }
}

led_diffuser_ring();
