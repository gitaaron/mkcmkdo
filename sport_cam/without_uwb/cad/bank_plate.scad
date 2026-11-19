// Bank plate: the floor of the power drum's bank pocket, a separate part so
// that the boards' screws through the pocket walls can be driven first.
//
// It drops into the pocket and two M3 screws come up through the drum floor
// into heat-set inserts in its underside. The tripod's 3/8-16 nut sits in a
// hex hole through it, on the drum floor: the tripod screw comes up through
// the floor and pulls the nut down onto it, so the plate only stops the nut
// turning. The bank slides in over it.
//
// Its front edge is a crossbar, held at both ends and thinned from underneath,
// with a catch on top in the middle: the bank pushes it down going in, and it
// springs up behind the bank's front face once the bank is home. To take the
// bank out, press the catch down and pinch the bank out through the finger
// windows. (A bar held at both ends prints as a plain bridge.)
//
// Drawn in the pocket's frame, as it prints: underside on the plate, the bank
// along +x with its open end at +x, the tripod axis at the origin.
include <config.scad>

R = base_d / 2;
x0 = pocket_x0;  x1 = pocket_x1;  y0 = pocket_y0;  y1 = pocket_y1;
c = plate_clr;
T = plate_t;
yc = (y0 + y1) / 2;
bx0 = x1 - 2;                               // the crossbar: from here to the front edge

module outline() {
    // the pocket's inside, out to the drum's outline at the open end
    intersection() {
        translate([x0 + c, y0 + c, 0]) cube([R + 6 - x0, y1 - y0 - 2 * c, T]);
        translate([0, 0, -1]) cylinder(r = R - 0.3, h = T + 2, $fn = 192);
    }
}

module catch() {
    // a vertical face against the bank, sloping down towards the open end, catch_w wide
    intersection() {
        translate([0, yc, 0]) rotate([90, 0, 0]) linear_extrude(height = catch_w, center = true)
            polygon([[x1, T - 0.01], [x1, T + catch_h], [x1 + 1.5, T + catch_h], [x1 + catch_l, T - 0.01]]);
        translate([0, 0, -1]) cylinder(r = R - 0.3, h = T + catch_h + 2, $fn = 192);
    }
}

module bank_plate() {
    difference() {
        union() { outline(); catch(); }
        // the crossbar: a slit behind it, and thinned from underneath, so it flexes down in the
        // middle; its ends stay joined to the plate either side
        translate([bx0 - 1.5, yc - bar_span / 2, -1]) cube([1.5, bar_span, T + 2]);
        translate([bx0 - 1.5, yc - bar_span / 2, -1]) cube([R, bar_span, T - bar_t + 1]);
        // the tripod nut: a hex hole right through, the nut on the drum floor under it
        translate([0, 0, -1]) cylinder(d = (nut_af + 2 * tripod_nut_clr) / cos(30), h = T + 2, $fn = 6);
        // heat-set inserts from underneath, for the two screws up through the drum floor
        for (p = plate_screws) translate([p[0], p[1], -1]) cylinder(d = drum_insert_d, h = drum_insert_h + 1, $fn = 24);
    }
}

bank_plate();
