// Camera cradle: clamps the Arducam zoom-lens barrel; one side screws to
// the DS3225's round metal horn, the other carries a 12 mm stub shaft that
// rides in the 6701ZZ bearing. Lens axis passes through the tilt axis.
include <config.scad>

clamp_t = 10;                  // clamp ring thickness along lens axis
back_t = 6;

module clamp_ring() {
    difference() {
        cylinder(d = lens_d + 12, h = clamp_t);
        translate([0, 0, -1]) cylinder(d = lens_d + 2 * clr, h = clamp_t + 2);
        // clamp slit + M3 pinch bolt
        translate([0, -2, -1]) cube([lens_d, 4, clamp_t + 2]);
        translate([lens_d / 2 + 3, 0, clamp_t / 2]) rotate([90, 0, 0])
            cylinder(d = 3.2, h = 30, center = true, $fn = 24);
    }
}

module side_plates() {
    for (s = [-1, 1])
        translate([0, s * (cradle_w / 2 - back_t / 2), clamp_t / 2])
            difference() {
                cube([lens_d + 12, back_t, clamp_t], center = true);
                if (s == 1)  // horn side: 4 × M3 on the horn circle + centre relief
                    rotate([90, 0, 0]) {
                        cylinder(d = 8, h = back_t + 2, center = true, $fn = 24);
                        for (a = [0:90:270])
                            rotate([0, 0, a + 45])
                                translate([horn_screw_circle / 2, 0, 0])
                                    cylinder(d = 3.2, h = back_t + 2, center = true, $fn = 24);
                    }
            }
    // bearing-side stub shaft
    translate([0, -cradle_w / 2 - tilt_bearing_w, clamp_t / 2]) rotate([-90, 0, 0])
        cylinder(d = tilt_bearing_od - 2 * 0.15, h = tilt_bearing_w + back_t);
}

module camera_cradle() {
    difference() {
        union() {
            clamp_ring();
            // bridge between clamp and side plates
            for (s = [-1, 1])
                translate([0, s * (cradle_w / 4 + 2), clamp_t / 2])
                    cube([lens_d + 12, cradle_w / 2 - back_t, clamp_t], center = true);
            side_plates();
        }
        // lens bore cut through everything (bridges included)
        translate([0, 0, -1]) cylinder(d = lens_d + 2 * clr, h = clamp_t + 2);
        // re-open the clamp slit
        translate([0, -2, -1]) cube([lens_d, 4, clamp_t + 2]);
    }
}

camera_cradle();
