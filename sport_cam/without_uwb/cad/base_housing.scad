// Static enclosure. Bottom to top inside: the LED ring hanging under the Pi
// shelf (which rests on three posts merged into the wall), the Pi on the shelf.
// Everything to do with power is in the power drum screwed up under the floor. The lid carries the Arducam
// pan-tilt base. Nothing rotates, and with camera-only tracking there is
// nothing to mount outside: the wall is plain all the way round.
//
// Every position here — openings, posts, vents, window height, the enclosure
// size itself — comes from layout.scad, which cad/fit.py solves from the part
// sizes. Don't move a feature here: change the inputs and re-run fit.py.
//
// Renders the body; `lid.scad`, `shelf.scad`, `led_diffuser_ring.scad`,
// `power_drum.scad` (screwed under the floor; the tripod screws into it) and
// `bank_plate.scad` are separate parts.
include <config.scad>

// x radial (outward) through the middle of the wall, at angle a, height z
module at_wall(a, z) rotate([0, 0, a]) translate([R_in + base_wall / 2, 0, z]) children();

module vent_slot() {
    hull() for (dz = [-(vent_h - vent_w) / 2, (vent_h - vent_w) / 2])
        translate([0, 0, dz]) rotate([0, 90, 0]) cylinder(d = vent_w, h = base_wall * 4, center = true);
}

module shelf_post(a) {
    // merged into the wall; M3 heat-set insert in the top for the shelf screw
    rotate([0, 0, a]) translate([post_r, 0, base_wall])
        difference() {
            cylinder(d = post_d, h = shelf_z - base_wall);
            translate([0, 0, shelf_z - base_wall - 7]) cylinder(d = post_insert_d, h = 8, $fn = 24);
        }
}

module band_ledge() {
    // the diffuser band rests on this; 45° underneath so it prints unsupported
    w = diffuser_t + clr;
    z = window_z - diffuser_lip - ledge_h;
    translate([0, 0, z]) rotate_extrude()
        polygon([[base_d / 2 - 0.5, -w], [base_d / 2 + w, 0], [base_d / 2 + w, ledge_h], [base_d / 2 - 0.5, ledge_h]]);
}

module shell() {
    difference() {
        union() {
            cylinder(d = base_d, h = base_h);
            band_ledge();
        }
        // hollow interior
        translate([0, 0, base_wall]) cylinder(r = R_in, h = base_h);
        // LED window — all the way round, in bays: thin ribs every
        // window_bridge mm keep the wall above it printable without support
        translate([0, 0, window_z])
            difference() {
                cylinder(d = base_d + 2, h = led_window_h);
                cylinder(r = R_in - 0.01, h = led_window_h);
                for (a = window_ribs) rotate([0, 0, a])
                    translate([R_in - 1, -window_rib_w / 2, -1]) cube([base_wall + 3, window_rib_w, led_window_h + 2]);
            }
        // vents for the Pi, above the shelf
        for (a = vents_high) at_wall(a, vent_high_z) vent_slot();
        // lid fixings: four M3 in through the wall, countersunk outside, into
        // heat-set inserts in the lid's spigot
        for (a = lid_screw_angs) at_wall(a, lid_screw_z) rotate([0, 90, 0]) {
            cylinder(d = lid_screw_d, h = base_wall * 4, center = true, $fn = 24);
            translate([0, 0, base_wall / 2 - 1.7]) cylinder(d1 = lid_screw_d, d2 = 6.4, h = 1.71, $fn = 24);
        }
    }
}

module base_housing() {
    difference() {
        union() {
            shell();
            // posts after the window cut, so it doesn't cut them
            for (a = post_angs) shelf_post(a);
        }
        // the level shifter, when the shelf has no room for it, stands on standoffs on the
        // floor: countersunk screws come up from underneath, through the floor into them
        for (h = floor_holes) translate([h[0], h[1], 0]) {
            translate([0, 0, -1]) cylinder(d = h[2], h = h[4] + 2, $fn = 24);
            translate([0, 0, -0.01]) cylinder(d1 = h[3], d2 = h[2], h = (h[3] - h[2]) / 2 + 0.01, $fn = 24);
        }
        // the power drum hangs under the floor: M3 countersunk screws, driven from inside
        // before the shelf goes in, down into the inserts in its posts
        for (p = drum_screws) translate([p[0], p[1], 0]) {
            translate([0, 0, -1]) cylinder(d = 3.4, h = base_wall + 2, $fn = 24);
            translate([0, 0, base_wall - 1.7]) cylinder(d1 = 3.4, d2 = 6.4, h = 1.71, $fn = 24);
        }
        // the leads up from the drum: the buck's 5 V, the latch's HOLD and SENSE
        translate([wire_hole[0], wire_hole[1], -1]) cylinder(d = wire_hole[2], h = base_wall + 2, $fn = 32);
    }
}

base_housing();
