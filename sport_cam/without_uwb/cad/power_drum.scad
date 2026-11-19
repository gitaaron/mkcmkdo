// Power drum: everything to do with power, in a round open-topped box the
// enclosure's own diameter, screwed up under its floor (the floor is its lid),
// so the two make one cylinder. The tripod screws into its floor. Moving the
// power parts down here leaves the enclosure only the LED ring, the shelf and
// the Pi, which is what makes the camera low.
//
//   * The bank pocket runs across the middle, open at one side of the drum.
//     The bank slides in on a drop-in plate (bank_plate.scad) that holds the
//     tripod nut and carries a sprung catch; finger windows either side of the
//     open end let you pinch it out.
//   * The buck and the power latch stand on edge against the pocket's walls,
//     on their standoffs; countersunk M3 screws go through the wall from inside
//     the pocket, flush, so the bank slides past them. They go in before the
//     plate does.
//   * The PD trigger lies on the floor near a finger window, screwed up
//     through the floor; the bank's cable (right-angle plug in the bank) comes
//     back in through the window. The rocker switch is in the wall.
//   * Posts, merged into the wall or the pocket's walls, take heat-set inserts
//     for the M3 screws that come down through the enclosure floor.
//
// Drawn as it prints, floor on the plate, in the enclosure's x and y. The
// pocket is drawn in its own frame (bank along +x, open end at +x, the tripod
// axis at the origin) and turned by drum_ang. fit.py places everything: change
// the inputs and re-run it, don't move features here.
include <config.scad>

R = base_d / 2;
Ri = R - drum_wall;
H = drum_h;
x0 = pocket_x0;  x1 = pocket_x1;  y0 = pocket_y0;  y1 = pocket_y1;
pw = pocket_wall;
fz = drum_floor + plate_t + finger_z;       // the finger windows' bottom
BIG = R + 6;

module in_pocket() rotate([0, 0, drum_ang]) children();

module shell() {
    difference() {
        cylinder(r = R, h = H, $fn = 192);
        translate([0, 0, drum_floor]) cylinder(r = Ri, h = H, $fn = 192);
    }
}

module pocket_walls() {
    intersection() {
        cylinder(r = R - 0.01, h = H, $fn = 192);
        in_pocket() union() {
            translate([x0 - pw, y0 - pw, 0]) cube([BIG - x0 + pw, pw, H]);      // the two side walls
            translate([x0 - pw, y1, 0]) cube([BIG - x0 + pw, pw, H]);
            translate([x0 - pw, y0 - pw, 0]) cube([pw, y1 - y0 + 2 * pw, H]);   // the closed end
        }
    }
}

module pocket_cuts() in_pocket() {
    // the bank's slot, through the drum wall at the open end
    translate([x0, y0, drum_floor]) cube([BIG - x0, y1 - y0, H]);
    // finger windows either side of the open end, through the pocket walls and the drum wall
    translate([x1 - finger_l, y1 - 1, fz]) cube([BIG, pw + finger_d + 1, H]);
    translate([x1 - finger_l, y0 - pw - finger_d, fz]) cube([BIG, pw + finger_d + 1, H]);
    // the boards' screws: from the pocket face out through the wall, countersunk flush on the bank's side
    for (h = wall_holes) translate([h[0], h[1], h[2]]) rotate([0, 0, h[3]]) rotate([0, 90, 0]) {
        translate([0, 0, -1]) cylinder(d = wall_hole_d, h = pw + 2, $fn = 24);
        translate([0, 0, -0.01]) cylinder(d1 = 6.4, d2 = wall_hole_d, h = (6.4 - wall_hole_d) / 2 + 0.01, $fn = 24);
    }
    // the plate's two screws, up from underneath into the inserts in it
    for (p = plate_screws) translate([p[0], p[1], 0]) {
        translate([0, 0, -1]) cylinder(d = 3.4, h = drum_floor + 2, $fn = 24);
        translate([0, 0, -0.01]) cylinder(d1 = 6.4, d2 = 3.4, h = 1.51, $fn = 24);
    }
}

module vent_slot() {
    hull() for (dz = [-(vent_h - vent_w) / 2, (vent_h - vent_w) / 2])
        translate([0, 0, dz]) rotate([0, 90, 0]) cylinder(d = vent_w, h = drum_wall * 4, center = true);
}

// Round rocker switch: its bezel sits on a flat cut into the curved wall
// outside, and its ring screws up against a flat boss inside.
module switch_boss() {
    inner = switch_seat_r - switch_panel_t;
    if (inner < Ri + 0.5)
        rotate([0, 0, switch_ang]) translate([inner, 0, switch_z]) rotate([0, 90, 0])
            cylinder(d = switch_boss_d, h = Ri + 0.5 - inner, $fn = 64);
}

module switch_cut() {
    rotate([0, 0, switch_ang]) {
        translate([switch_seat_r, 0, switch_z]) rotate([0, 90, 0])
            cylinder(d = switch_flange_d + 1, h = drum_wall + 5, $fn = 64);
        translate([switch_seat_r - switch_panel_t - 1, 0, switch_z]) rotate([switch_flat_rot, 0, 0])
            intersection() {
                rotate([0, 90, 0]) cylinder(d = switch_hole_d, h = switch_panel_t + drum_wall + 6, $fn = 64);
                translate([0, -switch_hole_d, switch_hole_d / 2 - switch_flat_d])
                    cube([switch_panel_t + drum_wall + 6, 2 * switch_hole_d, switch_flat_d]);
            }
    }
}

// With UWB: the pads the anchor arms (±Y) and the mast foot (−X) bolt to,
// two M3 inserts each, run down to the bed so they print without support.
module arm_boss() {
    difference() {
        translate([-arm_w / 2 - 2, R - 2, 0]) cube([arm_w + 4, 6, arm_boss_z + arm_root_h]);
        for (z = [arm_boss_z + 6, arm_boss_z + 18])
            translate([0, arm_boss_r + 1, z]) rotate([90, 0, 0])
                cylinder(d = arm_insert_d, h = arm_boss_r + 1 - (Ri + 0.8), $fn = 24);
    }
}

module power_drum() {
    difference() {
        union() {
            shell();
            pocket_walls();
            intersection() {
                cylinder(r = R - 0.01, h = H, $fn = 192);
                for (p = drum_screws) translate([p[0], p[1], 0]) cylinder(d = drum_post_d, h = H, $fn = 48);
            }
            switch_boss();
            // the PD trigger's rest: its two standoffs are at the socket end, this holds up the other
            for (r = drum_rests) translate([r[0], r[1], drum_floor]) rotate([0, 0, r[2]])
                translate([-r[3] / 2, -r[4] / 2, 0]) cube([r[3], r[4], r[5]]);
            if (drum_arms) for (a = [90, 270, 180]) rotate([0, 0, a - 90]) arm_boss();
        }
        pocket_cuts();
        switch_cut();
        for (a = drum_vents) rotate([0, 0, a]) translate([Ri + drum_wall / 2, 0, drum_vent_z]) vent_slot();
        // tripod: through the floor, under the nut in the plate
        translate([0, 0, -1]) cylinder(d = tripod_clear_d, h = drum_floor + 2, $fn = 48);
        // the PD trigger's standoffs: countersunk screws up through the floor
        for (h = drum_floor_holes) translate([h[0], h[1], 0]) {
            translate([0, 0, -1]) cylinder(d = h[2], h = h[4] + 2, $fn = 24);
            translate([0, 0, -0.01]) cylinder(d1 = h[3], d2 = h[2], h = (h[3] - h[2]) / 2 + 0.01, $fn = 24);
        }
        // heat-set inserts in the posts' tops, for the screws down through the enclosure floor
        for (p = drum_screws) translate([p[0], p[1], H - drum_insert_h])
            cylinder(d = drum_insert_d, h = drum_insert_h + 1, $fn = 24);
    }
}

power_drum();
