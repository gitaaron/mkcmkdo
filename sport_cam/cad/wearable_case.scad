// Wearable pod: ESP32-UWB board + 1000 mAh LiPo + TP4056.
// Renders body + friction-fit lid side by side. Strap bars fit a 26 mm
// elastic armband. USB-C charge slot on one end. Rounded, no sharp corners
// (worn against an arm). Add a 3 mm foam pad under the board — keeps the
// ceramic antenna off the skin.
include <config.scad>

r = 4;                                    // corner radius
ol = pod_inner_l + 2 * pod_wall;
ow = pod_inner_w + 2 * pod_wall;
oh = pod_inner_h + pod_wall;              // lid adds the top

module rbox(l, w, h, rad) {
    hull()
        for (x = [rad, l - rad], y = [rad, w - rad])
            translate([x, y, 0]) cylinder(r = rad, h = h);
}

module body() {
    difference() {
        rbox(ol, ow, oh, r);
        translate([pod_wall, pod_wall, pod_wall])
            rbox(pod_inner_l, pod_inner_w, pod_inner_h + 1, r - 1);
        // USB-C slot (charging without opening the pod)
        translate([-1, ow / 2 - 5, pod_wall + 3]) cube([pod_wall + 2, 10, 4.5]);
        // lid lip rebate
        translate([pod_wall / 2, pod_wall / 2, oh - 2])
            rbox(ol - pod_wall, ow - pod_wall, 3, r - 1);
    }
    // strap bars under the base
    for (x = [ol * 0.18, ol * 0.82 - 6])
        translate([x, -3, -4]) difference() {
            cube([6, ow + 6, 4]);
            translate([-1, 3, -1]) cube([8, ow, 3]);   // strap tunnel
        }
}

module lid() {
    rbox(ol - pod_wall - 2 * clr, ow - pod_wall - 2 * clr, 2, r - 1);
    translate([pod_wall / 2 + clr, pod_wall / 2 + clr, 2])
        difference() {
            rbox(ol - 2 * pod_wall - 4 * clr, ow - 2 * pod_wall - 4 * clr, 2, r - 1.5);
            // LED light pipe + button access
            translate([10, (ow - 2 * pod_wall) / 2, -1]) cylinder(d = 3.5, h = 4, $fn = 24);
            translate([22, (ow - 2 * pod_wall) / 2, -1]) cylinder(d = 8, h = 4, $fn = 32);
        }
}

body();
translate([0, ow + 12, 4]) lid();
