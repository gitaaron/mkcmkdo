// Third UWB anchor (A3) mast — two printed parts around a bought ½" dowel.
//
//   part = "foot"    bolts to the −X wall boss, holds the dowel upright
//   part = "cradle"  caps the dowel and carries the ULA1 flat, like A1/A2
//
// render_all.sh renders both with -D part=... . The dowel is cut to
// mast_dowel_l (echoed below), which lands A3 uwb_v_base above A1/A2.
//
// Both print with the socket opening UP, no supports. 4+ walls: the foot
// takes the whole mast's leverage through two M3s. One M3 heat-set insert in
// each socket wall takes a thumb screw that pinches the dowel.
include <config.scad>

part = "foot";
echo(str("cut the dowel to ", mast_dowel_l, " mm; mast axis ", mast_axis_r,
         " mm behind the pan axis"));

module socket(h) {
    // open-topped tube with a closed floor and a pinch-screw insert
    difference() {
        cylinder(r = mast_sock_r, h = h);
        translate([0, 0, mast_floor]) cylinder(d = mast_bore, h = h);
        translate([0, 0, h - 10]) rotate([-90, 0, 0])
            cylinder(d = arm_insert_d, h = mast_sock_r + 1, $fn = 24);
    }
}

// Root plate as on the arms, but full socket height for stiffness: above the
// boss it stands clear of the curved wall, so it can be taller than the boss.
module mast_foot() {
    sy = 6 + mast_sock_r - 2;          // socket centre from the plate's back face
    difference() {
        union() {
            cube([arm_w, 6, mast_foot_h]);
            translate([arm_w / 2, sy, 0]) socket(mast_foot_h);
        }
        translate([arm_w / 2, sy, mast_floor]) cylinder(d = mast_bore, h = mast_foot_h);
        for (z = [6, 18])
            translate([arm_w / 2, -1, z]) rotate([-90, 0, 0])
                cylinder(d = 3.4, h = 8, $fn = 24);
    }
}

// Printed pad-down; mounted, it is flipped so the board faces up.
module mast_cradle() {
    difference() {
        union() {
            translate([-(uwb_l + 12) / 2, -uwb_w / 2, 0]) cube([uwb_l + 12, uwb_w, arm_t]);
            translate([0, 0, arm_t]) socket(mast_cap_h);
        }
        for (x = [-1, 1], y = [-1, 1])
            translate([x * uwb_hole_dx / 2, y * uwb_hole_dy / 2, -1])
                cylinder(d = 2.2, h = arm_t + 2, $fn = 24);
    }
}

if (part == "foot") mast_foot();
else mast_cradle();
