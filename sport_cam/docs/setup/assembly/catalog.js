/* SportCam assembly guides: parts-and-tools catalogue.
 *
 * Shared by with_uwb/ and without_uwb/ docs/setup/assembly/index.html. Every
 * part or tool named in a step's Parts / Tools lists is matched against the
 * entries below and turned into a link; clicking it opens a picture and a
 * description ("what is an M2.5 × 6?").
 *
 *   SportcamCatalog.linkify(html)   wrap known names in clickable buttons
 *   SportcamCatalog.open(id)        show one entry
 *   SportcamCatalog.snapshot = fn   set by the guide's 3D viewer: fn(partIds)
 *                                   → PNG data URL of those PARTS models
 *
 * Pictures come from one of three places, in this order:
 *   printed  the part previews in docs/<build>/images/parts/ (rendered by
 *            <build>/cad/render_previews.py)
 *   model    a snapshot of the same model the guide's 3D viewer draws
 *   svg      a drawing defined in this file (also the offline fallback)
 *
 * To add an entry: give it an id, a name, the regexes that find it in the
 * guide's text (no capturing groups — use (?:…)), a kind, a picture and a
 * description. Longer patterns win where two overlap.
 */
(function () {
  "use strict";

  /* ---- drawings ------------------------------------------------------- */
  const C = { ink: "#2a2e35", steel: "#b9bdc4", steelD: "#8a9099", brass: "#d2ab52", brassD: "#a5822f",
    black: "#33373e", nylon: "#f1ecdc", pcb: "#2f7a4c", blue: "#1e4f8f", red: "#c0392b", green: "#1f9d55",
    wood: "#d9b77e", grey: "#c3ccdb", yellow: "#f2c230", orange: "#e67e22", white: "#ffffff" };
  const svg = (body) => `<svg viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg" role="img" class="cat-svg">` +
    `<defs><marker id="cat-ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">` +
    `<path d="M0 0 L10 5 L0 10 z" fill="${C.green}"/></marker></defs>` +
    `<g stroke="${C.ink}" stroke-width="1.6" stroke-linejoin="round" fill="none" font-family="system-ui,sans-serif" font-size="13">${body}</g></svg>`;
  const T = (x, y, s, anchor = "middle", size = 13) => `<text x="${x}" y="${y}" fill="${C.ink}" stroke="none" text-anchor="${anchor}" font-size="${size}">${s}</text>`;
  const dim = (x1, y1, x2, y2) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${C.green}" stroke-width="1.4" marker-start="url(#cat-ah)" marker-end="url(#cat-ah)"/>`;
  const R = (x, y, w, h, fill, rx = 0, extra = "") => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" ${extra}/>`;
  const L = (x1, y1, x2, y2, extra = "") => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${extra}/>`;
  const Ci = (x, y, r, fill, extra = "") => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" ${extra}/>`;

  // Side view of a metric screw, to scale, with its length and diameter
  // dimensioned. For a countersunk screw the length includes the head.
  function screw({ d, L: len, head = "cap", pitch, note }) {
    const hd = head === "csk" ? 2 * d : head === "thumb" ? 3.3 * d : 1.8 * d;
    const hh = head === "csk" ? d / 2 : head === "thumb" ? 1.1 * d : d;
    const total = len + (head === "csk" ? 0 : hh);
    const k = Math.min(16, 160 / total, 92 / hd);   // leaves room for the Ø label
    const x0 = 62, cy = 82, r = (d * k) / 2, H = (hd * k) / 2, hw = hh * k;
    let s = "";
    let shank, from;
    if (head === "csk") {
      s += `<path d="M${x0} ${cy - H} L${x0 + hw} ${cy - r} L${x0 + hw} ${cy + r} L${x0} ${cy + H} Z" fill="${C.steel}"/>`;
      shank = x0 + hw; from = x0;
    } else {
      s += R(x0, cy - H, hw, 2 * H, C.steel, head === "cap" ? 2 : 3);
      if (head === "thumb") for (let y = cy - H + 5; y < cy + H - 2; y += 5) s += L(x0 + 1, y, x0 + hw - 1, y, `stroke="${C.steelD}" stroke-width="1"`);
      shank = from = x0 + hw;
    }
    const end = from + len * k, ch = Math.min(r * 0.35, 4);
    s += `<path d="M${shank} ${cy - r} L${end - ch} ${cy - r} L${end} ${cy - r + ch} L${end} ${cy + r - ch} L${end - ch} ${cy + r} L${shank} ${cy + r} Z" fill="${C.steel}"/>`;
    const p = pitch * k;
    for (let x = shank + p; x < end - ch; x += p) s += L(x, cy - r, x - p / 2, cy + r, `stroke="${C.steelD}" stroke-width="1"`);
    if (head === "cap") s += `<path d="M${x0 - 1} ${cy - r * 0.45} L${x0 + hw * 0.45} ${cy - r * 0.45} L${x0 + hw * 0.45} ${cy + r * 0.45} L${x0 - 1} ${cy + r * 0.45}" stroke-dasharray="3 2" stroke-width="1"/>`;
    const yd = cy + H + 20;
    s += L(from, cy + H + 4, from, yd + 5, `stroke="${C.green}" stroke-width="1"`) + L(end, cy + r + 4, end, yd + 5, `stroke="${C.green}" stroke-width="1"`);
    s += dim(from, yd, end, yd) + T((from + end) / 2, yd + 18, `length ${len} mm`);
    const xd = end + 22;
    s += L(end + 4, cy - r, xd + 5, cy - r, `stroke="${C.green}" stroke-width="1"`) + L(end + 4, cy + r, xd + 5, cy + r, `stroke="${C.green}" stroke-width="1"`);
    s += dim(xd, cy - r - 1, xd, cy + r + 1) + T(xd + 9, cy + 5, `Ø ${d} mm`, "start");
    s += T(160, 190, note || `${head === "csk" ? "countersunk" : head === "thumb" ? "thumb screw" : "socket-head cap screw"}, shown enlarged`, "middle", 11.5);
    return svg(s);
  }

  function hexagon(cx, cy, r, fill) {
    const pts = [];
    for (let i = 0; i < 6; i++) { const a = Math.PI / 6 + (i * Math.PI) / 3; pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`); }
    return `<polygon points="${pts.join(" ")}" fill="${fill}"/>`;
  }
  // a small PCB with a chip and a label: the offline fallback for bought boards
  const board = (label, fill = C.pcb, w = 170, h = 96) => svg(
    R(160 - w / 2, 92 - h / 2, w, h, fill, 6) + R(140, 72, 40, 40, C.black, 3) +
    [0, 1, 2, 3, 4].map((i) => Ci(160 - w / 2 + 12 + i * 10, 92 + h / 2 - 10, 3, C.brass)).join("") + T(160, 178, label));
  let clipN = 0;
  function knurl(x, y, w, h) {   // diamond knurling, clipped to the part's outline
    const id = "cat-k" + (++clipN);
    let s = `<clipPath id="${id}"><rect x="${x}" y="${y}" width="${w}" height="${h}"/></clipPath><g clip-path="url(#${id})" stroke="${C.brassD}" stroke-width="1">`;
    for (let i = -h; i < w; i += 8) s += L(x + i, y, x + i + h, y + h) + L(x + i, y + h, x + i + h, y);
    return s + "</g>";
  }

  const DRAW = {
    nut: svg(hexagon(105, 90, 52, C.steel) + Ci(105, 90, 22, "#f3f5f9") + Ci(105, 90, 26, "none", `stroke-dasharray="3 3" stroke-width="1"`) +
      R(195, 45, 30, 90, C.steel) + R(225, 52, 14, 76, "#3a6fd8") + dim(53, 160, 157, 160) + T(105, 180, "5.5 mm across flats") + T(217, 160, "nylon ring", "middle", 11.5)),
    insert: svg(R(70, 55, 70, 60, C.brass, 3) + knurl(70, 55, 70, 60) + R(68, 62, 4, 46, C.brassD) + L(82, 85, 150, 85, `stroke-dasharray="4 3" stroke-width="1"`) +
      R(190, 70, 100, 70, C.grey) + R(222, 70, 36, 34, "#f3f5f9") + `<path d="M240 20 L240 58" stroke="${C.green}" stroke-width="2" marker-end="url(#cat-ah)"/>` +
      R(230, 0, 20, 20, C.steelD) + T(105, 140, "brass, knurled outside") + T(105, 156, "threaded inside") + T(240, 160, "pressed into a printed hole") + T(240, 176, "with a hot soldering iron")),
    standoff: svg(R(70, 70, 120, 40, C.nylon, 2) + L(70, 80, 190, 80, `stroke-width="1"`) + L(70, 100, 190, 100, `stroke-width="1"`) +
      R(190, 80, 40, 20, C.nylon) + [0, 1, 2, 3, 4, 5].map((i) => L(196 + i * 6, 80, 193 + i * 6, 100, `stroke-width="1"`)).join("") +
      L(62, 85, 72, 85, `stroke-dasharray="3 2" stroke-width="1"`) + dim(70, 128, 190, 128) + T(130, 148, "3 mm tall body") + T(210, 70, "threaded stud", "middle", 11.5) + T(70, 62, "threaded hole", "middle", 11.5)),
    tripodInsert: svg(R(80, 50, 90, 80, C.brass, 4) + knurl(80, 50, 90, 80) + R(80, 70, 90, 40, "#8a6c25", 0, `opacity="0.55"`) +
      [0, 1, 2, 3, 4, 5, 6].map((i) => L(88 + i * 11, 70, 82 + i * 11, 110, `stroke-width="1"`)).join("") + dim(80, 150, 170, 150) + T(125, 170, "≤ 8 mm long") +
      T(240, 80, "3/8-16 thread", "middle") + T(240, 98, "inside", "middle", 11.5) + T(240, 126, "epoxied into the", "middle", 11.5) + T(240, 142, "enclosure floor", "middle", 11.5)),
    bushing: svg(Ci(95, 92, 52, C.brass) + Ci(95, 92, 32, "#f3f5f9") + Ci(95, 92, 35, "none", `stroke-dasharray="3 3" stroke-width="1"`) + R(40, 88, 18, 8, C.brassD) + R(132, 88, 18, 8, C.brassD) +
      R(190, 50, 60, 84, C.brass, 2) + [0, 1, 2, 3, 4, 5, 6].map((i) => L(190, 56 + i * 11, 250, 50 + i * 11, `stroke="${C.brassD}" stroke-width="1"`)).join("") +
      T(95, 168, "end view: slot for a") + T(95, 184, "flat screwdriver") + T(220, 152, "outside 3/8-16") + T(220, 170, "inside 1/4-20")),
    threads: svg(R(40, 52, 200, 30, C.steel, 2) + [...Array(16)].map((_, i) => L(52 + i * 12.5, 52, 46 + i * 12.5, 82, `stroke="${C.steelD}" stroke-width="1"`)).join("") +
      R(40, 116, 200, 46, C.steel, 2) + [...Array(12)].map((_, i) => L(55 + i * 16, 116, 47 + i * 16, 162, `stroke="${C.steelD}" stroke-width="1"`)).join("") +
      T(250, 72, "1/4-20", "start") + T(250, 144, "3/8-16", "start") + T(160, 36, "Ø inches – threads per inch", "middle", 11.5)),
    hexKey: (size) => svg(`<path d="M60 40 L60 150 Q60 162 72 162 L250 162" stroke="${C.black}" stroke-width="12" stroke-linecap="butt"/>` + T(160, 140, `${size} mm hex (Allen) key`) + T(60, 30, "short arm", "middle", 11.5)),
    driver: (label) => svg(R(30, 78, 110, 40, C.red, 14) + [0, 1, 2, 3].map((i) => L(45 + i * 22, 82, 45 + i * 22, 114, `stroke="#8e2b2b" stroke-width="1"`)).join("") +
      R(140, 92, 120, 12, C.steel) + `<path d="M260 92 L282 94 L282 102 L260 104 Z" fill="${C.steelD}"/>` + T(160, 160, label)),
    calipers: svg(R(30, 60, 270, 22, C.steel, 2) + [...Array(26)].map((_, i) => L(40 + i * 10, 60, 40 + i * 10, i % 5 ? 66 : 70, `stroke-width="1"`)).join("") +
      `<path d="M30 60 L30 165 L48 165 L48 82" fill="${C.steel}"/>` + `<path d="M110 50 L110 165 L92 165 L92 82" fill="${C.steelD}"/>` + R(92, 50, 80, 40, C.black, 4) + R(102, 56, 50, 20, "#9fc5a8", 2) +
      T(127, 71, "24.15", "middle", 12) + `<path d="M30 60 L30 30 L42 30 L42 60" fill="${C.steel}"/>` + T(200, 130, "outside jaws ↓", "middle", 11.5) + T(200, 148, "inside jaws ↑", "middle", 11.5)),
    cutters: svg(`<path d="M60 150 Q120 110 150 90 L250 40 L255 52 L160 102 Z" fill="${C.steel}"/>` + `<path d="M60 40 Q120 80 150 100 L250 152 L255 140 L160 90 Z" fill="${C.steelD}"/>` +
      `<path d="M150 90 L150 100" stroke-width="2"/>` + R(14, 30, 70, 20, C.red, 10, `transform="rotate(32 49 40)"`) + R(14, 140, 70, 20, C.red, 10, `transform="rotate(-32 49 150)"`) + T(265, 106, "flat", "start", 11.5) + T(265, 120, "side", "start", 11.5)),
    iron: svg(R(20, 86, 110, 28, C.blue, 12) + R(130, 92, 50, 16, C.black) + R(180, 96, 80, 8, C.steel) + `<path d="M260 96 L292 100 L260 104 Z" fill="${C.steelD}"/>` +
      `<path d="M20 100 Q0 140 30 170" stroke="${C.black}" stroke-width="3"/>` + T(200, 140, "tip gets to 200–450 °C") + T(200, 158, "an insert tip helps for heat-set inserts", "middle", 11.5)),
    drill: (label) => svg(R(30, 88, 90, 24, C.steelD) + `<path d="M120 88 L270 88 L292 100 L270 112 L120 112 Z" fill="${C.steel}"/>` +
      [...Array(9)].map((_, i) => `<path d="M${132 + i * 16} 88 Q${140 + i * 16} 100 ${132 + i * 16} 112" stroke="${C.steelD}"/>`).join("") + T(170, 150, label)),
    stepBit: svg(R(30, 92, 70, 16, C.steelD) + [0, 1, 2, 3, 4, 5].map((i) => R(100 + i * 28, 100 - (36 - i * 6), 28, 2 * (36 - i * 6), C.steel)).join("") + T(160, 165, "each step drills one size larger")),
    multimeter: svg(R(100, 20, 120, 165, C.yellow, 14) + R(115, 34, 90, 40, "#9fc5a8", 3) + T(160, 61, "5.08 V", "middle", 16) + Ci(160, 115, 26, C.black) + L(160, 115, 172, 96, `stroke="${C.white}" stroke-width="3"`) +
      Ci(130, 166, 7, C.black) + Ci(160, 166, 7, C.red) + Ci(190, 166, 7, C.black) + `<path d="M130 172 Q110 195 60 190" stroke="${C.black}" stroke-width="3"/>` + `<path d="M160 172 Q200 195 270 188" stroke="${C.red}" stroke-width="3"/>`),
    load: svg(R(70, 60, 180, 70, "#aab2bd", 4) + [...Array(8)].map((_, i) => R(80 + i * 21, 50, 12, 10, "#aab2bd")).join("") + T(160, 102, "1.2 Ω 50 W", "middle", 15) +
      L(70, 95, 30, 95, `stroke="${C.red}" stroke-width="3"`) + L(250, 95, 290, 95, `stroke="${C.black}" stroke-width="3"`) + T(160, 160, "aluminium-cased power resistor") + T(160, 178, "or an electronic load", "middle", 11.5)),
    marker: svg(R(40, 88, 190, 26, C.black, 6) + R(230, 92, 30, 18, C.black, 3) + `<path d="M260 95 L285 101 L260 107 Z" fill="${C.black}"/>` + R(60, 92, 60, 18, C.white, 3) + T(160, 160, "fine-tip permanent marker")),
    level: svg(R(30, 80, 260, 44, C.yellow, 4) + R(130, 88, 60, 28, "#c8f0c0", 12) + Ci(165, 102, 9, "#e9ffe5") + L(150, 86, 150, 118) + L(170, 86, 170, 118) + T(160, 160, "bubble between the lines = level")),
    tape: svg(R(50, 50, 110, 110, C.yellow, 22) + Ci(105, 105, 22, C.black) + R(160, 140, 130, 18, C.yellow) + [...Array(12)].map((_, i) => L(166 + i * 10, 140, 166 + i * 10, i % 2 ? 146 : 150, `stroke-width="1"`)).join("") + R(288, 132, 6, 30, C.steelD)),
    laptop: svg(R(70, 30, 180, 115, C.black, 6) + R(80, 40, 160, 95, "#1b2740") + T(160, 80, "ssh pi@sportcam", "middle", 12).replace(`fill="${C.ink}"`, `fill="#9fc5a8"`) + `<path d="M40 150 L280 150 L270 165 L50 165 Z" fill="${C.steel}"/>`),
    stopwatch: svg(Ci(160, 110, 62, C.steel) + Ci(160, 110, 52, C.white) + L(160, 110, 160, 70, `stroke-width="3"`) + L(160, 110, 186, 122, `stroke-width="2"`) + R(150, 30, 20, 18, C.steelD, 3) + R(198, 46, 12, 18, C.steelD, 3, `transform="rotate(40 204 55)"`)),
    printer: svg(R(60, 20, 18, 150, C.black) + R(242, 20, 18, 150, C.black) + R(60, 20, 200, 14, C.black) + R(130, 34, 40, 50, C.steel, 4) + `<path d="M144 84 L156 84 L150 96 Z" fill="${C.black}"/>` +
      R(80, 120, 160, 10, "#a3743f") + R(110, 106, 70, 14, "#8fb7ff") + R(50, 170, 220, 14, C.black, 3) + T(160, 198, "FDM printer: melts plastic filament layer by layer", "middle", 11.5)),
    glue: svg(R(70, 60, 60, 100, C.white, 8) + `<path d="M88 60 L100 22 L112 60 Z" fill="${C.red}"/>` + T(100, 118, "CA", "middle", 16) + R(170, 90, 120, 30, C.white, 6) + R(150, 98, 20, 14, C.steelD) + R(290, 96, 10, 18, C.black) + T(230, 150, "hot-glue gun stick", "middle", 11.5)),
    epoxy: svg(R(60, 60, 170, 22, "#f3e7c4", 4) + R(60, 92, 170, 22, "#e9e9e9", 4) + R(230, 64, 30, 46, C.white, 4) + `<path d="M260 76 L290 86 L260 96 Z" fill="${C.white}"/>` + R(30, 70, 30, 34, C.black, 3) + T(145, 76, "resin", "middle", 11.5) + T(145, 108, "hardener", "middle", 11.5) + T(160, 150, "two parts, mixed 1 : 1 just before use")),
    zipTie: svg(`<path d="M60 160 Q20 60 140 50 Q260 40 250 120" stroke="${C.black}" stroke-width="8"/>` + R(240, 116, 22, 22, C.black, 3) + R(110, 140, 60, 40, C.white, 4) + `<path d="M120 160 L160 160" stroke="${C.black}" stroke-width="6"/>` + T(140, 196, "adhesive tie mount", "middle", 11.5)),
    strap: svg(R(20, 80, 280, 34, C.black, 4) + [...Array(18)].map((_, i) => L(30 + i * 8, 82, 30 + i * 8, 112, `stroke="#555" stroke-width="2"`)).join("") + R(250, 72, 46, 50, C.steelD, 6) + T(90, 140, "hooks", "middle", 11.5) + T(220, 140, "loops", "middle", 11.5)),
    usb: (a, b, note) => svg(R(30, 85, 50, 30, C.steel, 3) + R(80, 92, 30, 16, C.black, 3) + `<path d="M110 100 Q160 40 210 100" stroke="${C.black}" stroke-width="7"/>` + R(210, 92, 30, 16, C.black, 3) + R(240, 88, 50, 24, C.steel, 6) +
      T(55, 140, a) + T(265, 140, b) + (note ? T(160, 178, note, "middle", 11.5) : "")),
    pigtail: svg(R(30, 88, 30, 24, C.steel, 8) + R(60, 92, 30, 16, C.black, 3) + `<path d="M90 100 Q150 100 200 92 L270 70" stroke="${C.red}" stroke-width="4"/>` + `<path d="M90 100 Q150 104 200 108 L270 130" stroke="${C.black}" stroke-width="4"/>` +
      R(268, 66, 10, 6, C.brass) + R(268, 126, 10, 6, C.brass) + T(45, 140, "USB-C") + T(260, 160, "bare 5 V and ground")),
    microsd: svg(`<path d="M120 30 L200 30 L200 170 L110 170 L110 70 L120 60 Z" fill="${C.black}"/>` + R(120, 110, 70, 50, "#e8edf6", 3) + T(155, 140, "64 GB", "middle", 13) + [...Array(7)].map((_, i) => R(124 + i * 10, 34, 6, 16, C.brass)).join("")),
    cap: svg(R(120, 30, 80, 120, "#1e3a8a", 10) + R(180, 30, 20, 120, "#9fb3e8") + T(190, 95, "−", "middle", 18) + L(140, 150, 140, 190, `stroke="${C.steelD}" stroke-width="3"`) + L(180, 150, 180, 175, `stroke="${C.steelD}" stroke-width="3"`) +
      T(80, 92, "470 µF", "middle") + T(250, 92, "stripe = −", "middle", 11.5)),
    wire: svg(`<path d="M20 70 Q160 30 300 80" stroke="${C.red}" stroke-width="9"/>` + `<path d="M20 120 Q160 80 300 130" stroke="${C.black}" stroke-width="9"/>` + T(160, 170, "18 AWG ≈ 1.0 mm copper, silicone-insulated")),
    dowel: svg(R(20, 86, 280, 28, C.wood, 3) + [...Array(6)].map((_, i) => L(30 + i * 46, 92, 70 + i * 46, 96, `stroke="#b8925a" stroke-width="1"`)).join("") + dim(20, 140, 300, 140) + T(160, 160, "246 mm") + T(160, 60, "½ inch = 12.7 mm round hardwood")),
    spool: svg(Ci(160, 100, 80, C.black) + Ci(160, 100, 64, C.orange) + Ci(160, 100, 26, C.black) + Ci(160, 100, 12, "#f3f5f9") + T(160, 196, "1 kg spool of 1.75 mm filament", "middle", 11.5)),
    bank: svg(R(40, 60, 240, 80, C.black, 10) + R(60, 128, 30, 8, C.steelD, 2) + [0, 1, 2, 3].map((i) => Ci(220 + i * 12, 80, 3, C.green)).join("") + T(160, 170, "USB-C PD bank, about 150 × 72 × 30 mm")),
    tripod: svg(R(140, 20, 40, 10, C.black) + R(152, 30, 16, 50, C.steelD) + L(160, 80, 70, 190, `stroke="${C.black}" stroke-width="6"`) + L(160, 80, 160, 190, `stroke="${C.black}" stroke-width="6"`) + L(160, 80, 250, 190, `stroke="${C.black}" stroke-width="6"`)),
  };

  /* ---- the catalogue --------------------------------------------------- */
  const printed = (stl) => ({ printed: stl });
  const model = (ids, fallback) => ({ model: ids, svg: fallback });
  const pic = (s) => ({ svg: s });

  const SCREW_NOTE = "<p><b>How to read it:</b> <b>M</b> means metric thread; the number after it is the thread's outside diameter in millimetres; the number after the × is the length in millimetres, measured from under the head to the tip (for a countersunk screw, from the top of the head). The thread pitch is left off because each size has one standard coarse pitch.</p>";

  const ENTRIES = [
    // ---- fasteners
    { id: "m25x6", name: "M2.5 × 6 screw", kind: "Fastener", match: ["M2\\.5\\s*[×x]\\s*6\\b"], img: pic(screw({ d: 2.5, L: 6, pitch: 0.45 })),
      desc: "<p>A small metric machine screw: <b>2.5 mm</b> thread diameter, <b>6 mm</b> long. Socket-head cap screw — a round head with a hex socket, turned with a <b>2 mm</b> hex key or driver.</p>" + SCREW_NOTE +
        "<p>It fastens the Raspberry Pi to its standoffs, and with UWB the ULA1 boards to theirs.</p>",
      specs: [["Thread", "M2.5 × 0.45 mm pitch"], ["Length", "6 mm"], ["Head", "socket cap, ≈ 4.5 mm across"], ["Drive", "2 mm hex"]] },
    { id: "m3x10", name: "M3 × 10 screw", kind: "Fastener", match: ["M3\\s*[×x]\\s*10\\b"], img: pic(screw({ d: 3, L: 10, pitch: 0.5 })),
      desc: "<p>Metric machine screw, <b>3 mm</b> thread diameter, <b>10 mm</b> long, socket-head cap. Turned with a <b>2.5 mm</b> hex key.</p>" + SCREW_NOTE +
        "<p>Four of these, with nuts underneath, bolt the Arducam pan-tilt base to the lid through its slots.</p>",
      specs: [["Thread", "M3 × 0.5 mm pitch"], ["Length", "10 mm"], ["Head", "socket cap, ≈ 5.5 mm across"], ["Drive", "2.5 mm hex"]] },
    { id: "m3x8csk", name: "M3 × 8 countersunk screw", kind: "Fastener", match: ["M3\\s*[×x]\\s*8\\s+countersunk"], img: pic(screw({ d: 3, L: 8, head: "csk", pitch: 0.5 })),
      desc: "<p>Metric screw, <b>3 mm</b> thread, <b>8 mm</b> long, with a cone-shaped <b>countersunk</b> head that sits flush. The length of a countersunk screw includes the head.</p>" + SCREW_NOTE +
        "<p>Four of these hold the lid on: they go in sideways through the countersunk holes near the top of the enclosure wall, into heat-set inserts in the lid's locating ring. Most take a <b>2 mm</b> hex key.</p>",
      specs: [["Thread", "M3 × 0.5 mm pitch"], ["Length", "8 mm, head included"], ["Head", "90° countersunk, ≈ 6 mm across"]] },
    { id: "m3x8", name: "M3 × 8 screw", kind: "Fastener", match: ["M3\\s*[×x]\\s*8\\b"], img: pic(screw({ d: 3, L: 8, pitch: 0.5 })),
      desc: "<p>Metric machine screw, <b>3 mm</b> thread diameter, <b>8 mm</b> long, socket-head cap, turned with a <b>2.5 mm</b> hex key.</p>" + SCREW_NOTE +
        "<p>Three of these fix the Pi shelf to the posts in the enclosure wall, into heat-set inserts in the post tops.</p>",
      specs: [["Thread", "M3 × 0.5 mm pitch"], ["Length", "8 mm"], ["Drive", "2.5 mm hex"]] },
    { id: "m3x12", name: "M3 × 12 screw", kind: "Fastener", match: ["M3\\s*[×x]\\s*12\\b"], img: pic(screw({ d: 3, L: 12, pitch: 0.5 })),
      desc: "<p>Metric machine screw, <b>3 mm</b> thread diameter, <b>12 mm</b> long, socket-head cap, turned with a <b>2.5 mm</b> hex key.</p>" + SCREW_NOTE +
        "<p>Bolts the anchor arms and the mast foot to the enclosure's wall bosses, into heat-set inserts.</p>",
      specs: [["Thread", "M3 × 0.5 mm pitch"], ["Length", "12 mm"], ["Drive", "2.5 mm hex"]] },
    { id: "m3thumb", name: "M3 thumb screw", kind: "Fastener", match: ["M3\\s+thumb\\s+screws?"], img: pic(screw({ d: 3, L: 8, head: "thumb", pitch: 0.5, note: "knurled head, turned by hand" })),
      desc: "<p>An M3 screw with a large knurled head you turn with your fingers. One in each mast socket pinches the dowel, so the mast lifts out for transport without tools.</p>" },
    { id: "m3nut", name: "M3 nut", kind: "Fastener", match: ["\\bnuts\\b"], img: pic(DRAW.nut),
      desc: "<p>A hex nut for M3 screws, <b>5.5 mm across the flats</b>. A <b>nylon-insert (nyloc)</b> nut — the version with a coloured ring — grips the thread and won't vibrate loose, which is why the guide prefers it under the camera base.</p><p>Hold it with a 5.5 mm spanner or pliers while you turn the screw.</p>" },
    { id: "screwkit", name: "M2.5 / M3 screw kit", kind: "Fastener", match: ["M2\\.5\\s*/\\s*M3\\s+screw\\s+kit", "\\bM3\\s+screws\\b"], img: pic(screw({ d: 3, L: 12, pitch: 0.5, note: "an M3 socket-head cap screw" })),
      desc: "<p>An assortment box of small metric screws, nuts and washers in two sizes: <b>M2.5</b> (2.5 mm thread) for the Pi and small boards, and <b>M3</b> (3 mm thread) for everything structural. The bill of materials lists the counts.</p>" + SCREW_NOTE },
    { id: "heatset", name: "Brass heat-set insert (M3)", kind: "Fastener", match: ["brass\\s+heat-set\\s+inserts?", "heat-set\\s+inserts?", "M3\\s+inserts?"], img: pic(DRAW.insert),
      desc: "<p>A small knurled brass sleeve with an M3 thread inside. You melt it into a printed hole with a soldering iron; the plastic flows into the knurling and sets around it, giving the part a metal thread that survives being screwed and unscrewed many times — plastic threads don't.</p>" +
        "<p><b>How:</b> sit the insert on the hole, put the iron (about 220–250 °C for PETG, an insert tip if you have one) on top, and let it sink under light pressure until flush. Pull the iron straight out and hold the insert square with a flat tool for a few seconds while it cools.</p>" },
    { id: "standoff", name: "3 mm standoffs", kind: "Fastener", match: ["3\\s*mm\\s+standoffs?"], img: pic(DRAW.standoff),
      desc: "<p>Short threaded spacers, here nylon in M2.5. They hold a circuit board <b>3 mm</b> off the surface, so the solder joints underneath can't touch anything and the board isn't bent by the screw.</p>" },
    { id: "pistandoff", name: "M2.5 nylon standoffs, 6 mm", kind: "Fastener", match: ["M2\\.5\\s+nylon\\s+standoffs?(?:,\\s*6\\s*mm)?"], img: pic(DRAW.standoff),
      desc: "<p>Threaded nylon spacers, 6 mm tall, from the standoff kit. Four of them hold the Raspberry Pi 6 mm above the shelf — enough to clear the solder joints and the microSD socket under the board. Screw them into the shelf's Pi holes from underneath, then the Pi onto them with M2.5 × 6.</p>" },
    { id: "tape", name: "Double-sided foam tape", kind: "Consumable", match: ["Double-sided\\s+foam\\s+tape"], img: pic(DRAW.strap),
      desc: "<p>About 1 mm thick, the mounting kind (VHB or similar). It sticks the power boards to the enclosure floor and the LED ring under the shelf, and the foam keeps solder joints off the plastic. Clean both surfaces with alcohol first.</p>" },
    { id: "tripodInsert", name: "3/8-16 brass insert", kind: "Fastener", match: ["3/8-16\\s+brass\\s+insert"], img: pic(DRAW.tripodInsert),
      desc: "<p>A brass sleeve with a <b>3/8-16</b> thread inside — the standard thread on video heads and larger tripods (3/8 inch diameter, 16 threads per inch). Epoxied into the enclosure floor, it is what the whole head screws onto.</p><p>It must be no longer than the <b>8 mm</b> boss it sits in.</p>" },
    { id: "bushing", name: "3/8-16 → 1/4-20 reducer bushing", kind: "Fastener", match: ["3/8-16\\s*→\\s*1/4-20\\s+reducer\\s+bushing", "reducer\\s+bushing"], img: pic(DRAW.bushing),
      desc: "<p>A brass adapter: <b>3/8-16</b> thread on the outside, <b>1/4-20</b> inside. Screw it into the 3/8-16 insert and the enclosure fits a normal photo tripod, whose screw is 1/4-20. Take it out for 3/8-16 tripods.</p><p>It has a slot across one end; turn it with a flat screwdriver, slot facing down.</p>" },
    { id: "plug", name: "3/8-16 screw (as a plug)", kind: "Tool", match: ["3/8-16\\s+screw\\s+as\\s+a\\s+plug"], img: pic(DRAW.threads),
      desc: "<p>Any bolt with a 3/8-16 thread. Greased lightly and threaded into the insert from below while the epoxy cures, it keeps glue out of the threads and holds the insert square. Remove it after the cure.</p>" },
    { id: "threads", name: "1/4-20 and 3/8-16 tripod threads", kind: "Reference", match: ["1/4-20", "3/8-16"], img: pic(DRAW.threads),
      desc: "<p>The two standard camera-mount threads, written the imperial way: <b>diameter in inches – threads per inch</b>.</p><ul><li><b>1/4-20</b>: ¼ inch (6.35 mm), 20 threads per inch. Almost every photo tripod and phone mount.</li><li><b>3/8-16</b>: ⅜ inch (9.5 mm), 16 threads per inch. Video heads and heavier tripods.</li></ul><p>The enclosure has a 3/8-16 insert and a removable bushing that turns it into 1/4-20, so it fits either.</p>" },

    // ---- printed parts
    { id: "enclosure", name: "Enclosure", kind: "Printed part", match: ["\\bEnclosure\\b"], img: printed("base_housing"),
      desc: "<p>The round printed body. The power boards stick to its floor; three posts in the wall carry the Pi shelf above them. It has a window all the way round for the light band, a USB-C inlet, a switch cut-out and a jack hole low in the wall, vents, and a boss in the floor for the tripod insert. Its size is solved by <code>cad/fit.py</code> to fit your parts (see <code>cad/FIT_REPORT.md</code>).</p><p>PETG, 4 walls, 20 % infill, no supports.</p>" },
    { id: "lid", name: "Lid", kind: "Printed part", match: ["\\bLid\\s+assembly\\b", "\\bLid\\b"], img: printed("lid"),
      desc: "<p>The top plate. It carries the Arducam pan-tilt base on four radial slots (any bolt spacing 30–72 mm) and passes the camera ribbon through a central opening. A ring underneath drops into the enclosure mouth; four M3 screws through the wall go into heat-set inserts in that ring. It holds the whole camera up, so print it stronger than the rest: PETG, <b>5 walls, 40 %</b>, top face down.</p>" },
    { id: "diffuser", name: "LED diffuser band", kind: "Printed part", match: ["LED\\s+diffuser\\s+ring", "diffuser\\s+band"], img: printed("led_diffuser_ring"),
      desc: "<p>A thin translucent band that slides down over the <b>outside</b> of the enclosure and rests on a small ledge, covering the light window, so the 16 LEDs inside glow as one even ring rather than 16 dots. Print it in <b>white or natural PETG</b>, 2 walls, 0 % infill — thin is what makes it glow. Four dabs of glue hold it.</p>" },
    { id: "shelf", name: "Pi shelf", kind: "Printed part", match: ["\\bShelf\\b"], img: printed("shelf"),
      desc: "<p>A flat plate that rests on three posts in the enclosure wall, above the power boards. The Raspberry Pi sits on top on nylon standoffs; the LED ring is taped underneath, LEDs down, lighting the window. One side is cut away so the power and data leads can pass between the floor and the shelf.</p><p>Its size, the cut-away and the hole positions come from <code>cad/fit.py</code>. Print flat, 3 walls, 20 % — white or natural PETG helps the ring's light reach the window.</p>" },
    { id: "arm", name: "UWB anchor arm", kind: "Printed part", match: ["Anchor\\s+arm"], img: printed("anchor_arm"),
      desc: "<p>One of two arms that hold the A1 and A2 anchors <b>250 mm apart</b>, either side of the camera. That spacing is the baseline the bearing maths depends on. Bolts to the wall boss with two M3 screws into heat-set inserts. Print flat, 4+ walls.</p>" },
    { id: "mastFoot", name: "Mast foot", kind: "Printed part", match: ["Mast\\s+foot"], img: printed("mast_foot"),
      desc: "<p>Bolts to the boss at the back of the enclosure and holds the bottom of the ½-inch dowel in a socket, clamped by an M3 thumb screw.</p>" },
    { id: "mastCradle", name: "Mast cradle", kind: "Printed part", match: ["mast\\s+cradle"], img: printed("mast_cradle"),
      desc: "<p>Caps the top of the dowel and carries the third anchor (A3), 250 mm above the other two. A thumb screw clamps it to the dowel.</p>" },
    { id: "tray", name: "Battery tray", kind: "Printed part", match: ["Battery\\s+tray"], img: printed("battery_tray"),
      desc: "<p>A saddle for the USB-C power bank, sized to it, with slots for a hook-and-loop strap. Strap it to a tripod leg or the centre column, low, to keep the weight down.</p>" },
    { id: "petg", name: "PETG filament", kind: "Consumable", match: ["\\bPETG\\b"], img: pic(DRAW.spool),
      desc: "<p>The plastic all the printed parts are made from. PETG is tougher and more heat-resistant than PLA and doesn't creep under the camera's weight. Prints at about 230–250 °C on an 80 °C bed. The LED diffuser needs <b>white or natural</b> PETG so light passes through.</p><p>Full settings: <a href='../../../../docs/setup/11-3d-printing.md' target='_blank'>3D printing specifications</a>.</p>" },

    // ---- bought parts
    { id: "pd", name: "USB-C PD trigger board", kind: "Electronics", match: ["USB-C\\s+PD\\s+trigger\\s+board"], img: model(["trigger"], board("USB-C PD trigger", C.blue)),
      desc: "<p>A small board with a USB-C socket that talks USB Power Delivery to the power bank and asks it for a fixed voltage — <b>12 V</b> here — instead of the default 5 V. You select the voltage with a solder jumper or resistor printed on the board.</p><p>Check it with a meter on a real bank before wiring anything else.</p>" },
    { id: "rocker", name: "Rocker switch", kind: "Electronics", match: ["Rocker\\s+switch"], img: model(["switch"], board("rocker switch", C.black, 80, 100)),
      desc: "<p>The camera's on/off switch. Panel-mount: it clips into a rectangular hole in the enclosure wall. It doesn't carry the power. It tells the power latch to turn on, and the Pi when to shut down, so switching off saves any recording before the power goes.</p>" },
    { id: "latch", name: "Power latch", kind: "Electronics", match: ["Power\\s+latch"], img: model(["latch"], board("power latch")),
      desc: "<p>A small board you build on perfboard: an IRF4905 P-channel MOSFET switches the camera's 12 V, and two 2N3904 transistors turn it on, one for the rocker switch and one for the Pi. After you switch off, the Pi keeps it on until it has saved the recording and shut down, then lets go.</p><p>Circuit and values: <a href='../12-wiring.md#power-latch' target='_blank'>wiring guide</a>.</p>" },
    { id: "ina", name: "INA226 / INA260 battery gauge", kind: "Electronics", match: ["INA226\\s+module", "\\bINA2[26]0\\b"], img: model(["ina226"], board("INA226 / INA260")),
      desc: "<p>A current-and-voltage sensor on the 12 V line, read by the Pi over I2C at address <b>0x40</b>. The camera software uses it to estimate battery time left.</p><p>The bill of materials prefers the <b>INA260</b> (Adafruit 4226), which has the measuring resistor built in, so there is nothing to calibrate. A bare INA226 module works too — set <code>POWER_MONITOR = \"ina226\"</code> and its shunt value. Without either, set <code>POWER_MONITOR = \"none\"</code>.</p>" },
    { id: "buck", name: "12 V → 5 V 8 A buck converter", kind: "Electronics", match: ["12\\s*V\\s*→\\s*5\\s*V\\s*8\\s*A\\s+buck", "\\bbuck\\b"], img: model(["buck"], board("buck converter", C.blue)),
      desc: "<p>A switching regulator that steps 12 V down to 5 V efficiently, for the Pi, the camera's servos and the LED ring. Rated 8 A; the build draws up to about 4 A.</p><p>Its output is adjustable with a small trimmer screw. <b>Set it to 5.1 V while a 4 A load is connected</b> — the voltage with nothing attached tells you little.</p>" },
    { id: "jack", name: "Panel-mount barrel jack", kind: "Electronics", match: ["Panel-mount\\s+barrel\\s+jack", "barrel\\s+jack"], img: model(["jack"], board("barrel jack", C.black, 70, 70)),
      desc: "<p>A round DC power socket that screws through a hole in the enclosure wall (8 mm, low on the −Y side). Here it is a <b>5 V service tap</b> off the buck output, for bench work.</p>" },
    { id: "wire", name: "18 AWG silicone wire", kind: "Consumable", match: ["18\\s*AWG\\s+silicone\\s+wire"], img: pic(DRAW.wire),
      desc: "<p>Stranded copper hook-up wire. <b>AWG</b> is the American Wire Gauge: a <i>smaller</i> number is a <i>thicker</i> wire. 18 AWG is about 1.0 mm of copper (0.82 mm²), enough for the 4 A on the 5 V line over short runs. Silicone insulation stays flexible and doesn't melt back when you solder near it.</p>" },
    { id: "cap", name: "470 µF capacitor", kind: "Electronics", match: ["470\\s*µF"], img: pic(DRAW.cap),
      desc: "<p>An electrolytic capacitor, 470 microfarads, rated 10 V or more. Across the buck's output it smooths the 5 V rail when the servos or the Pi suddenly draw current.</p><p><b>It has a polarity:</b> the stripe marks the negative (−) leg, which goes to OUT−. Fitted backwards it can fail violently.</p>" },
    { id: "pi", name: "Raspberry Pi 4 Model B (4 GB)", kind: "Electronics", match: ["Raspberry\\s+Pi\\s+4\\s+Model\\s+B\\s+4\\s*GB", "Raspberry\\s+Pi\\s+4"], img: model(["pi"], board("Raspberry Pi 4", C.pcb, 200, 120)),
      desc: "<p>The computer that runs everything: the camera, tracking, recording, the LED ring and the connection to the phone app. The Pi 4 is used rather than the Pi 5 because it has a hardware H.264 video encoder, which makes recording nearly free on battery.</p>" },
    { id: "cooler", name: "Heatsink / fan", kind: "Electronics", match: ["heatsink/fan", "heatsinks?"], img: model(["cooler"], board("heatsink + fan", "#4a4f57")),
      desc: "<p>Stick-on heatsinks or a small fan case for the Pi's chips. The Pi sits low in a closed enclosure, so fit it <b>before</b> mounting the board — you can't reach the chips afterwards.</p>" },
    { id: "sd", name: "64 GB microSD card", kind: "Electronics", match: ["64\\s*GB\\s+microSD", "microSD"], img: pic(DRAW.microsd),
      desc: "<p>Holds the Pi's operating system and the recordings — about 10 hours of video on 64 GB. Use a reputable brand, U3 / A2 class or faster; slow cards drop frames while recording.</p>" },
    { id: "pigtail", name: "USB-C pigtail", kind: "Electronics", match: ["USB-C\\s+pigtail"], img: pic(DRAW.pigtail),
      desc: "<p>A short lead with a USB-C plug on one end and bare 5 V and ground wires on the other. It carries the buck's 5 V into the Pi's power socket. Keep it short — it carries up to 4 A.</p>" },
    { id: "ring", name: "WS2812B 16-LED ring", kind: "Electronics", match: ["WS2812B\\s+16-LED\\s+ring", "WS2812B"], img: model(["ledring"], board("WS2812B ring", C.black, 120, 120)),
      desc: "<p>A ring of 16 addressable RGB LEDs. Each LED has its own tiny controller, so a single data wire sets every colour individually. Runs on 5 V. It's the camera's status light: blue standby, green searching, red recording.</p>" },
    { id: "shifter", name: "74AHCT125 level shifter", kind: "Electronics", match: ["74AHCT125\\s+level\\s+shifter", "74AHCT125"], img: model(["shifter"], board("74AHCT125")),
      desc: "<p>A 14-pin logic chip used as a buffer. The Pi's pins speak 3.3 V; the LED ring at 5 V wants a data signal close to 5 V. The 74AHCT125 reads 3.3 V as a valid high and outputs a full 5 V signal. Tie its unused inputs to ground.</p>" },
    { id: "glue", name: "CA or hot glue", kind: "Consumable", match: ["CA\\s+or\\s+hot\\s+glue"], img: pic(DRAW.glue),
      desc: "<p><b>CA</b> is cyanoacrylate — super glue. Either it or hot glue is fine for the four dabs that hold the diffuser ring in place. Not for the tripod insert: that needs epoxy.</p>" },
    { id: "epoxy", name: "2-part epoxy", kind: "Consumable", match: ["2-part\\s+epoxy"], img: pic(DRAW.epoxy),
      desc: "<p>A glue that comes as resin and hardener, mixed just before use. It sets hard and very strong, and is what holds the tripod insert — which carries the whole camera — in the floor. Use a slow-setting one and let it cure the full 24 hours.</p>" },
    { id: "ptz", name: "Arducam IMX477 PTZ camera", kind: "Electronics", match: ["Arducam\\s+IMX477\\s+PTZ\\s+camera\\s+with\\s+metal\\s+pan-tilt\\s+base", "Arducam[^,<]*PTZ[^,<]*"], img: model(["ptz_plate", "ptz_pan", "ptz_yoke", "camera", "lens"], board("Arducam PTZ camera", C.steelD)),
      desc: "<p>The camera and both motion axes in one bought assembly: a 12 MP Sony IMX477 sensor behind a motorised zoom-and-focus lens, on a metal pan-tilt base driven by two servos. The Pi controls it over I2C (address 0x0C) and receives video over the ribbon cable.</p><p>Arducam publishes no drawing for the base's bolt pattern, so measure yours — the lid's slots take 30–72 mm.</p>" },
    { id: "ula1", name: "Haorutech ULA1 UWB module", kind: "Electronics", match: ["Haorutech\\s+ULA1\\s+modules?", "ULA1\\s+modules?"], img: model(["uwb_p"], board("ULA1 UWB anchor")),
      desc: "<p>An ultra-wideband (UWB) radio module, 40 × 25 mm, with a USB-A plug on the board. Each one is an <b>anchor</b>: it measures its distance to the wearable tag by timing radio pulses. Three anchors at known positions let the camera work out where the tag is — bearing from A1 and A2, elevation from A3 on the mast.</p><p>Only one anchor sends data to the Pi; the others just need 5 V from a USB port. On the arms they lie <b>across</b> the arm, plug towards the back, so the extension cable's socket end has room.</p>" },
    { id: "usbExt", name: "USB-A extension cable", kind: "Electronics", match: ["USB-A\\s+extensions?", "short\\s+USB\\s+cables"], img: pic(DRAW.usb("USB-A male", "USB-A female", "full extension: data and power")),
      desc: "<p>A USB-A male-to-female extension, about 50 cm. The ULA1 has its USB plug on the board, so it plugs straight into the female end; the male end comes in through the slot high in the enclosure wall to the Pi's USB ports. Extensions carry data by definition, so there's no charge-only trap.</p>" },
    { id: "bank", name: "USB-C PD power bank", kind: "Electronics", match: ["USB-C\\s+PD\\s+power\\s+bank"], img: model(["bank"], DRAW.bank),
      desc: "<p>The battery: a 25 000 mAh (92 Wh) bank that supports USB Power Delivery at 12 V. Expect about 6 hours of tracking and recording. Banks of the same capacity vary by 15 mm in each direction — measure yours against the tray before printing.</p>" },
    { id: "cable100", name: "100 W USB-C cable", kind: "Electronics", match: ["100\\s*W\\s+USB-C\\s+cable"], img: pic(DRAW.usb("USB-C", "USB-C", "e-marked, rated 5 A")),
      desc: "<p>A short USB-C to USB-C cable rated for 100 W (20 V × 5 A). The rating comes from an <b>e-marker</b> chip in the plug. Use the one from the bill of materials: a cheap charge-only cable can leave the PD trigger stuck at 5 V.</p>" },
    { id: "strap", name: "Hook-and-loop strap", kind: "Consumable", match: ["Hook-and-loop\\s+strap"], img: pic(DRAW.strap),
      desc: "<p>A Velcro-style cinch strap, 25 mm wide. It holds the power bank in its tray, or the tray to a tripod leg.</p>" },
    { id: "zip", name: "Zip ties and adhesive tie mounts", kind: "Consumable", match: ["Zip\\s+ties", "adhesive\\s+tie\\s+mounts"], img: pic(DRAW.zipTie),
      desc: "<p>Plastic cable ties for dressing cables, and small self-adhesive squares with a slot that a zip tie threads through, so you can anchor a cable to a flat inside wall.</p>" },
    { id: "dowel", name: "½-inch hardwood dowel", kind: "Bought part", match: ["½-inch\\s+hardwood\\s+dowel"], img: model(["dowel"], DRAW.dowel),
      desc: "<p>A plain round hardwood rod, ½ inch (12.7 mm) across, from any hardware store. Cut to <b>246 mm</b>, it is the mast that holds anchor A3 250 mm above the others. <b>Wood, not metal</b>: metal next to a UWB antenna detunes it.</p>" },
    { id: "tripod", name: "Tripod", kind: "Bought part", match: ["photo\\s+or\\s+video\\s+tripod"], img: model(["tripod"], DRAW.tripod),
      desc: "<p>Any standard photo or video tripod. Photo tripods have a 1/4-20 screw (leave the bushing in); video tripods usually 3/8-16 (take the bushing out). The head is about 30 cm across and light, so a compact one is fine — but spread the legs wide.</p>" },

    // ---- tools
    { id: "printer", name: "3D printer", kind: "Tool", match: ["3D\\s+printer"], img: pic(DRAW.printer),
      desc: "<p>Any FDM printer with at least a <b>170 × 150 × 80 mm</b> build volume, a 0.4 mm nozzle, a 250 °C hotend and an 80 °C heated bed. About 25–35 hours of printing in total.</p><p>Recommended models, with links: <a href='../../../../docs/setup/11-3d-printing.md#printers-to-buy' target='_blank'>printers to buy</a>.</p>" },
    { id: "calipers", name: "Calipers", kind: "Tool", match: ["\\bCalipers\\b"], img: pic(DRAW.calipers),
      desc: "<p>Digital calipers measure outside sizes, inside sizes and depths to 0.01 mm. You need them to measure the parts whose sizes vary by vendor — the Arducam base's bolt spacing, the power bank, the brass insert — before printing.</p>" },
    { id: "iron", name: "Soldering iron", kind: "Tool", match: ["Soldering\\s+iron"], img: pic(DRAW.iron),
      desc: "<p>A temperature-controlled iron for soldering the wiring, and for pressing in heat-set inserts. For inserts, a dedicated insert tip keeps them straight; set about 220–250 °C for PETG.</p>" },
    { id: "drill32", name: "3.2 mm drill bit", kind: "Tool", match: ["3\\.2\\s*mm\\s+drill\\s+bit"], img: pic(DRAW.drill("3.2 mm twist drill")),
      desc: "<p>A twist drill 3.2 mm across — the clearance size for an M3 screw. Run it through each printed M3 hole to clean it to size; turning it by hand in a pin vise or with the drill at low speed is enough.</p>" },
    { id: "stepBit", name: "Drill or step bit", kind: "Tool", match: ["Drill\\s+or\\s+step\\s+bit"], img: pic(DRAW.stepBit),
      desc: "<p>Only needed if your tripod insert is wider than the 12.7 mm bore in the floor. A <b>step bit</b> is a cone with stepped diameters; it enlarges a hole in plastic cleanly, one size at a time, without grabbing.</p>" },
    { id: "cutters", name: "Flush cutters", kind: "Tool", match: ["flush\\s+cutters"], img: pic(DRAW.cutters),
      desc: "<p>Small side cutters ground flat on one face, so they cut flush with a surface. For trimming brims and support off prints, and zip-tie tails.</p>" },
    { id: "flat", name: "Flat screwdriver", kind: "Tool", match: ["Flat\\s+screwdriver"], img: pic(DRAW.driver("flat-blade screwdriver")),
      desc: "<p>A straight-blade screwdriver wide enough to fit the slot across the reducer bushing, about 6 mm.</p>" },
    { id: "multimeter", name: "Multimeter", kind: "Tool", match: ["\\bMultimeter\\b"], img: pic(DRAW.multimeter),
      desc: "<p>Measures voltage, current and resistance, and beeps for continuity. You use it to confirm the PD trigger gives 12 V, set the buck to 5.1 V, and check the 5 V at the Pi under load.</p>" },
    { id: "load", name: "4 A dummy load", kind: "Tool", match: ["4\\s*A\\s+dummy\\s+load"], img: pic(DRAW.load),
      desc: "<p>Something that draws a known current, so you can set the buck's voltage under realistic load. An adjustable electronic load is easiest. Otherwise use a <b>1.2 Ω power resistor rated 50 W</b>, bolted to a metal plate: at 5.1 V it draws about 4.2 A and gets hot — keep the test short.</p>" },
    { id: "driver2", name: "2 mm hex driver", kind: "Tool", match: ["2\\s*mm\\s+driver"], img: pic(DRAW.driver("2 mm hex driver")),
      desc: "<p>A screwdriver with a <b>2 mm hex (Allen)</b> tip — the size for M2.5 socket-head cap screws, like the M2.5 × 6 that hold the Pi down.</p>" },
    { id: "key25", name: "2.5 mm hex key", kind: "Tool", match: ["2\\.5\\s*mm\\s+hex\\s+key"], img: pic(DRAW.hexKey("2.5")),
      desc: "<p>An L-shaped <b>2.5 mm hex (Allen)</b> key — the size for M3 socket-head cap screws. Use the short arm for the final snug so you don't overtighten into plastic.</p>" },
    { id: "marker", name: "Marker", kind: "Tool", match: ["\\bMarker\\b"], img: pic(DRAW.marker),
      desc: "<p>A fine-tip permanent marker, for marking the Arducam base's bolt holes through the lid's slots.</p>" },
    { id: "level", name: "Level", kind: "Tool", match: ["Small\\s+level\\s+or\\s+phone\\s+level\\s+app"], img: pic(DRAW.level),
      desc: "<p>A small spirit level — or a level app on your phone — to check the mast dowel is plumb and the boards are level.</p>" },
    { id: "tape", name: "Tape measure", kind: "Tool", match: ["Tape\\s+measure"], img: pic(DRAW.tape),
      desc: "<p>For checking distances too long for calipers: the 250 mm anchor spacing, and the 5 m range calibration.</p>" },
    { id: "laptop", name: "Laptop on the same Wi-Fi", kind: "Tool", match: ["Laptop\\s+on\\s+the\\s+same\\s+Wi-Fi"], img: pic(DRAW.laptop),
      desc: "<p>Any computer on the same network as the camera, to open an SSH session to the Pi and run the setup and check commands.</p>" },
    { id: "stopwatch", name: "Stopwatch", kind: "Tool", match: ["\\bStopwatch\\b"], img: pic(DRAW.stopwatch),
      desc: "<p>Your phone's is fine — for timing the battery against the gauge's minutes-left estimate.</p>" },
  ];

  /* ---- matching -------------------------------------------------------- */
  const BYID = Object.fromEntries(ENTRIES.map((e) => [e.id, e]));
  const PATS = ENTRIES.flatMap((e) => e.match.map((p) => ({ p, e }))).sort((a, b) => b.p.length - a.p.length);
  const RE = new RegExp(PATS.map((x) => `(${x.p})`).join("|"), "gi");

  // Wrap known names in links. Only plain text is touched: tags are kept
  // as they are, and nothing inside an existing <a> is linked twice.
  function linkify(html) {
    let inA = 0;
    return String(html).split(/(<[^>]+>)/).map((seg) => {
      if (seg.startsWith("<")) {
        if (/^<a[\s>]/i.test(seg)) inA++; else if (/^<\/a>/i.test(seg)) inA = Math.max(0, inA - 1);
        return seg;
      }
      if (inA || !seg) return seg;
      return seg.replace(RE, (m, ...g) => {
        const i = g.findIndex((x, k) => k < PATS.length && x !== undefined);
        return `<a class="cat-link" role="button" tabindex="0" data-cat="${PATS[i].e.id}">${m}</a>`;
      });
    }).join("");
  }

  /* ---- dialog ---------------------------------------------------------- */
  let dlg = null;
  const shots = {};
  function ensureDialog() {
    if (dlg) return dlg;
    dlg = document.createElement("dialog");
    dlg.className = "cat-dialog";
    dlg.innerHTML = `<button type="button" class="cat-close" aria-label="Close">✕</button><div class="cat-img"></div><div class="cat-body"></div>`;
    dlg.querySelector(".cat-close").addEventListener("click", () => dlg.close());
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });   // backdrop
    document.body.appendChild(dlg);
    return dlg;
  }

  function picture(e) {
    const im = e.img || {};
    if (im.printed) return `<img src="../../images/parts/${im.printed}.png" alt="${e.name}" onerror="this.replaceWith(Object.assign(document.createElement('p'),{className:'muted',textContent:'No preview yet — run cad/render_previews.py'}))">`;
    if (im.model && api.snapshot) {
      const key = im.model.join(",");
      if (!(key in shots)) { try { shots[key] = api.snapshot(im.model); } catch (err) { shots[key] = null; console.warn(err); } }
      if (shots[key]) return `<img src="${shots[key]}" alt="${e.name}, as drawn in the 3D model"><div class="cat-cap">as drawn in the 3D model</div>`;
    }
    if (im.svg) return im.svg;
    return "";
  }

  function open(id) {
    const e = BYID[id];
    if (!e) return;
    const d = ensureDialog();
    d.querySelector(".cat-img").innerHTML = picture(e);
    const specs = e.specs ? `<dl class="cat-specs">${e.specs.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>` : "";
    d.querySelector(".cat-body").innerHTML = `<div class="cat-kind">${e.kind}</div><h3>${e.name}</h3>${e.desc}${specs}`;
    if (!d.open) d.showModal();
  }

  // The links are <a role="button"> rather than <button>: a button is laid
  // out as a box and breaks a long name across the list bullet.
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest && ev.target.closest(".cat-link");
    if (b) { ev.preventDefault(); open(b.dataset.cat); }
  });
  document.addEventListener("keydown", (ev) => {
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.classList && ev.target.classList.contains("cat-link")) { ev.preventDefault(); open(ev.target.dataset.cat); }
  });

  const api = { linkify, open, entries: ENTRIES, snapshot: null };
  window.SportcamCatalog = api;
})();
