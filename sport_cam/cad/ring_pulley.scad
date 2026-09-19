// 120T GT2 annular ring pulley — bolts to the underside of the rotating
// platform, encircling the slip ring (ID 60 clears the 44.5 flange).
// 6:1 with a bought 20T motor pulley. Print at 0.16 mm layers.
include <config.scad>

// Simplified GT2 tooth: 2 mm pitch, ~0.75 mm deep rounded tooth. Teeth are
// cut as circular reliefs at each pitch point — prints cleanly and grips a
// GT2 belt fine at these torques.
tooth_r = 0.85;
outer_r = ring_pitch_r + 0.38;   // belt-tooth land radius

module ring_pulley() {
    difference() {
        union() {
            // toothed body
            difference() {
                cylinder(r = outer_r, h = pulley_h);
                for (i = [0:ring_teeth - 1])
                    rotate([0, 0, i * 360 / ring_teeth])
                        translate([outer_r, 0, -1])
                            cylinder(r = tooth_r, h = pulley_h + 2, $fn = 24);
            }
            // belt-retention flanges
            for (z = [0, pulley_h - flange_lip])
                translate([0, 0, z])
                    cylinder(r = outer_r + 1.8, h = flange_lip);
        }
        // annulus
        translate([0, 0, -1]) cylinder(d = ring_id, h = pulley_h + 2);
        // 6 × M3 bolts up into the platform, on the lazy-susan-safe circle
        for (a = [0:60:300])
            rotate([0, 0, a + 30])
                translate([(ring_id / 2 + outer_r) / 2, 0, -1])
                    cylinder(d = 3.2, h = pulley_h + 2, $fn = 24);
    }
}

ring_pulley();
