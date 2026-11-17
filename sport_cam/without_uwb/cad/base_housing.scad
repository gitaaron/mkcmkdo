// Static enclosure. Bottom to top inside: the power boards on the floor (the
// buck and power latch screwed up into their standoffs from underneath, the rest taped), the LED ring hanging under the Pi shelf (which rests on three posts
// merged into the wall), the Pi on the shelf. The lid carries the Arducam
// pan-tilt base. Nothing rotates, and with camera-only tracking there is
// nothing to mount outside: the wall is plain all the way round.
//
// Every position here — openings, posts, vents, window height, the enclosure
// size itself — comes from layout.scad, which cad/fit.py solves from the part
// sizes. Don't move a feature here: change the inputs and re-run fit.py.
//
// Renders the body; `lid.scad`, `shelf.scad` and `led_diffuser_ring.scad`
// are separate parts.
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
        // USB-C inlet for the bank cable; the PD trigger's socket sits behind it
        at_wall(usbc_ang, usbc_z) cube([base_wall * 4, usbc_w, usbc_h], center = true);
        // vents: low ones for the buck, high ones for the Pi
        for (a = vents_low) at_wall(a, vent_low_z) vent_slot();
        for (a = vents_high) at_wall(a, vent_high_z) vent_slot();
        // lid fixings: four M3 in through the wall, countersunk outside, into
        // heat-set inserts in the lid's spigot
        for (a = lid_screw_angs) at_wall(a, lid_screw_z) rotate([0, 90, 0]) {
            cylinder(d = lid_screw_d, h = base_wall * 4, center = true, $fn = 24);
            translate([0, 0, base_wall / 2 - 1.7]) cylinder(d1 = lid_screw_d, d2 = 6.4, h = 1.71, $fn = 24);
        }
    }
}

// Round rocker switch: its bezel sits on a flat cut into the curved wall
// outside, and its ring screws up against a flat boss inside, so the two
// clamp switch_panel_t of plastic between parallel faces.
module switch_boss() {
    inner = switch_seat_r - switch_panel_t;
    if (inner < R_in + 0.5)
        rotate([0, 0, switch_ang]) translate([inner, 0, switch_z]) rotate([0, 90, 0])
            cylinder(d = switch_boss_d, h = R_in + 0.5 - inner, $fn = 64);
}

module switch_cut() {
    rotate([0, 0, switch_ang]) {
        translate([switch_seat_r, 0, switch_z]) rotate([0, 90, 0])
            cylinder(d = switch_flange_d + 1, h = base_wall + 5, $fn = 64);         // flat seat for the bezel
        // through the wall, with a flat matching the thread's key flat so the switch can't turn
        translate([switch_seat_r - switch_panel_t - 1, 0, switch_z]) rotate([switch_flat_rot, 0, 0])
            intersection() {
                rotate([0, 90, 0]) cylinder(d = switch_hole_d, h = switch_panel_t + base_wall + 6, $fn = 64);
                translate([0, -switch_hole_d, switch_hole_d / 2 - switch_flat_d])
                    cube([switch_panel_t + base_wall + 6, 2 * switch_hole_d, switch_flat_d]);
            }
    }
}

module base_housing() {
    difference() {
        union() {
            shell();
            // added after the hollowing, which would otherwise take it away
            cylinder(d = tripod_boss_d, h = tripod_boss_h);
            // posts after the window cut, so it doesn't cut them
            for (a = post_angs) shelf_post(a);
            // flat boss inside the wall for the rocker switch's locking ring
            switch_boss();
            // risers lifting a board clear of the tripod boss, when fit.py needed them
            for (r = risers) translate([r[0], r[1], base_wall]) rotate([0, 0, r[2]])
                translate([-r[4] / 2, -r[4] / 2, 0]) cube([r[4], r[4], r[3]]);
            // the PD trigger's rest: its two standoffs are at the socket end, this holds up the other
            for (r = rests) translate([r[0], r[1], base_wall]) rotate([0, 0, r[2]])
                translate([-r[3] / 2, -r[4] / 2, 0]) cube([r[3], r[4], r[5]]);
        }
        switch_cut();
        // the boards on standoffs (buck, power latch, PD trigger, and the level shifter
        // when it is on the floor): countersunk screws come up from underneath, through
        // the floor (and its risers, if raised), into them
        for (h = floor_holes) translate([h[0], h[1], 0]) {
            translate([0, 0, -1]) cylinder(d = h[2], h = h[4] + 2, $fn = 24);
            translate([0, 0, -0.01]) cylinder(d1 = h[3], d2 = h[2], h = (h[3] - h[2]) / 2 + 0.01, $fn = 24);
        }
        // tripod socket: a 3/8-16 nut dropped into a hex pocket from inside, on a ledge
        // the screw passes up through — tightening pulls the nut onto the ledge
        translate([0, 0, -1]) cylinder(d = tripod_clear_d, h = tripod_ledge + 2, $fn = 48);
        translate([0, 0, tripod_ledge])
            cylinder(d = (nut_af + 2 * tripod_nut_clr) / cos(30), h = tripod_boss_h, $fn = 6);
    }
}

base_housing();
