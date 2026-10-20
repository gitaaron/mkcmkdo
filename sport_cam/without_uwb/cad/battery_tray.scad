// Battery tray — carries the USB-C power bank low on the tripod.
//
// Strap it to a tripod leg or the centre column through the two slots. (An
// earlier version also had a central 1/4-20 bore for sandwiching the tray
// between the tripod and the enclosure, but the bolt would have had to pass
// through the bank, so it's gone.)
//
// Keeping the heaviest single item low is what stops the rig being tippy.
include <config.scad>

ol = bank_l + 2 * tray_wall;
ow = bank_w + 2 * tray_wall;

module rbox(l, w, h, rad) {
    hull() for (x = [rad, l - rad], y = [rad, w - rad])
        translate([x, y, 0]) cylinder(r = rad, h = h);
}

module battery_tray() {
    difference() {
        rbox(ol, ow, tray_wall + tray_lip, 5);
        // bank pocket
        translate([tray_wall, tray_wall, tray_wall])
            rbox(bank_l, bank_w, tray_lip + 1, 4);
        // open the ends so a USB cable can leave either side
        for (x = [-1, ol - tray_wall - 1])
            translate([x, tray_wall + 8, tray_wall + 3])
                cube([tray_wall + 2, bank_w - 16, tray_lip]);
        // strap slots through the floor, either side of the pocket
        for (x = [ol * 0.26, ol * 0.74 - tray_strap_w])
            for (y = [tray_wall / 2 - 1, ow - tray_wall / 2 - 2])
                translate([x, y, -1]) cube([tray_strap_w, 3, tray_wall + 2]);
    }
}

battery_tray();
