// Translucent diffuser band that closes the base housing's LED window.
// Print in white/natural PETG, 2 perimeters, 0% infill, no top/bottom.
include <config.scad>

led_window_h = 12;             // must match base_housing.scad
lip = 2;

module led_diffuser_ring() {
    difference() {
        cylinder(d = base_d + 1.6, h = led_window_h + 2 * lip);
        translate([0, 0, -1])
            cylinder(d = base_d - 2 * base_wall - 0.8, h = led_window_h + 2 * lip + 2);
        // snap reliefs: 4 shallow finger cuts on the inside lip
        for (a = [0:90:270])
            rotate([0, 0, a])
                translate([base_d / 2 - base_wall, 0, led_window_h / 2 + lip])
                    cube([base_wall * 2, 8, led_window_h - 2], center = true);
    }
}

led_diffuser_ring();
