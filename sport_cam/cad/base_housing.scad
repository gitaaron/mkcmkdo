// Base housing: holds ESP32 + TMC2209 carrier, buck #1, 12 V jack, NEMA17.
// The lazy-susan bottom plate and slip-ring flange bolt to the top deck.
// LED diffuser ring (separate part) snaps into the circumferential window.
include <config.scad>

led_window_h = 12;             // circumferential LED slot
led_window_z = 18;
deck_t = 4;

module bolt_pattern(spacing, d, depth) {
    for (x = [-1, 1], y = [-1, 1])
        translate([x * spacing / 2, y * spacing / 2, 0])
            cylinder(d = d, h = depth);
}

module base_housing() {
    difference() {
        union() {
            // shell
            cylinder(d = base_d, h = base_h);
            // NEMA17 mount tower: motor hangs under the deck, offset so its
            // 20T pulley meets the ring pulley (center distance ≈ ring_pitch_r + 20T pitch_r)
            // 20T pitch r = 20*2/(2*PI) ≈ 6.37 → center ≈ 44.5 from pan axis
        }
        // hollow interior
        translate([0, 0, base_wall])
            cylinder(d = base_d - 2 * base_wall, h = base_h);
        // LED window — full 360° band (diffuser ring closes it)
        translate([0, 0, led_window_z])
            difference() {
                cylinder(d = base_d + 2, h = led_window_h);
                cylinder(d = base_d - 2 * base_wall - 2, h = led_window_h);
            }
        // 12 V barrel jack (8 mm panel mount) — low on the wall
        translate([0, -base_d / 2, 10]) rotate([90, 0, 0])
            cylinder(d = 8.2, h = 3 * base_wall, center = true);
        // vent slots
        for (a = [30:30:150])
            rotate([0, 0, a]) translate([0, base_d / 2, 8]) rotate([90, 0, 0])
                hull() {
                    translate([0, 0, -base_wall * 2]) cylinder(d = 4, h = base_wall * 4);
                    translate([0, 4, -base_wall * 2]) cylinder(d = 4, h = base_wall * 4);
                }
    }
    // top deck (separate ring so the LED window stays open below it)
    translate([0, 0, base_h - deck_t]) deck();
    // 1/4-20 tripod boss on the floor
    difference() {
        cylinder(d = 20, h = 8);
        cylinder(d = 6.35, h = 9);     // press/epoxy a 1/4-20 brass insert
    }
}

module deck() {
    difference() {
        cylinder(d = base_d, h = deck_t);
        // slip-ring: body drops through, flange screws down
        cylinder(d = sr_body_d + 2 * clr, h = deck_t);
        for (s = [-1, 1])
            translate([s * sr_hole_space / 2, 0, 0]) cylinder(d = 3.2, h = deck_t);
        // lazy-susan bottom plate bolts
        bolt_pattern(ls_bolt, ls_hole_d, deck_t);
        // NEMA17: shaft + boss hole and 4 × M3, motor body below deck
        translate([44.5 + 6.37, 0, 0]) {
            cylinder(d = nema_boss_d + 2 * clr, h = deck_t);
            bolt_pattern(nema_bolt, 3.2, deck_t);
        }
        // wire pass (ESP32 → deck-top LED ring feed etc.)
        translate([-45, 25, 0]) cylinder(d = 10, h = deck_t);
    }
}

base_housing();
