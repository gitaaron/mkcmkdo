// Battery tray — carries the USB-C power bank low on the tripod, and lets it
// be swapped for a full one in seconds (requirement C4a).
//
// The tray stays on the tripod: a hook-and-loop strap goes through the two
// tunnels under the floor and round a leg or the centre column, never round
// the bank. The bank clips in: push it down between the side walls until the
// lips along the top snap over it. To take it out, pinch it at the finger
// notches half-way along and lift. The ends are open for the cable, which
// leaves from whichever end the bank's USB-C socket is at.
//
// Keeping the heaviest single item low is what stops the rig being tippy.
include <config.scad>

il = bank_l + 2 * tray_clr;            // the pocket
iw = bank_w + 2 * tray_clr;
ih = bank_h + 0.4;                     // floor to the underside of the lips
skin = 1.6;                            // under the strap tunnels
base = skin + tray_tunnel_h + tray_wall;   // skin, strap tunnels, floor
ol = il + 2 * tray_wall;
ow = iw + 2 * tray_wall;
oh = base + ih + tray_lip_t;

module rbox(l, w, h, rad) {
    hull() for (x = [rad, l - rad], y = [rad, w - rad])
        translate([x, y, 0]) cylinder(r = rad, h = h);
}

module battery_tray() {
    difference() {
        rbox(ol, ow, oh, 5);
        // the pocket, up to the underside of the lips
        translate([tray_wall, tray_wall, base]) rbox(il, iw, ih, 3);
        // the opening between the lips, chamfered out to the wall tops as a lead-in
        hull() {
            translate([tray_wall, tray_wall + tray_snap, base + ih - 0.01])
                cube([il, iw - 2 * tray_snap, 0.01]);
            translate([tray_wall, tray_wall, oh - 0.01]) cube([il, iw, 0.02]);
        }
        // cable openings in both end walls (narrower than the bank, so it can't slide out)
        for (x = [-1, ol - tray_wall - 1])
            translate([x, tray_wall + 8, base + 3]) cube([tray_wall + 2, iw - 16, oh]);
        // finger notches half-way along each long side, down to 40 % of the bank
        for (y = [-1, ow - tray_wall - 1])
            translate([(ol - tray_notch_w) / 2, y, base + ih * 0.4])
                cube([tray_notch_w, tray_wall + 2, oh]);
        // strap tunnels under the floor, across the tray (closed underneath, so the strap holds it)
        for (x = [ol * 0.22, ol * 0.78 - tray_strap_w - 1])
            translate([x, -1, skin]) cube([tray_strap_w + 1, ow + 2, tray_tunnel_h]);
    }
}

battery_tray();
