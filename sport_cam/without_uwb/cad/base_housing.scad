// Static enclosure. Bottom to top inside: the power boards stuck to the
// floor, the LED ring hanging under the Pi shelf (which rests on three posts
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
        // 5 V service jack
        at_wall(jack_ang, jack_z) rotate([0, 90, 0]) cylinder(d = jack_d, h = base_wall * 4, center = true);
        // rocker switch, with the wall thinned from inside so its clips grip
        at_wall(switch_ang, switch_z) {
            cube([base_wall * 4, switch_cut_w, switch_cut_h], center = true);
            if (switch_panel_t < base_wall)
                translate([(-switch_panel_t - 2) / 2, 0, 0])
                    cube([base_wall - switch_panel_t + 2, switch_cut_w + 6, switch_cut_h + 6], center = true);
        }
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

module base_housing() {
    difference() {
        union() {
            shell();
            // added after the hollowing, which would otherwise take it away
            cylinder(d = tripod_boss_d, h = tripod_boss_h);
            // posts after the window cut, so it doesn't cut them
            for (a = post_angs) shelf_post(a);
            // risers lifting a board clear of the tripod boss, when fit.py needed them
            for (r = risers) translate([r[0], r[1], base_wall]) rotate([0, 0, r[2]])
                translate([-3, -3, 0]) cube([6, 6, r[3]]);
        }
        // tripod insert bore
        translate([0, 0, -1]) cylinder(d = tripod_hole_d, h = tripod_boss_h + 1);
    }
}

base_housing();
