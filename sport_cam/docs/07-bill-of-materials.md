# 07 — Bill of materials

Sourcing strategy: everything below is stocked on **Amazon US (Prime, 1–2 day)**
or **Adafruit (ships same/next business day)** so the whole build arrives in
under a week. Amazon listings churn, so Amazon links are search links pinned
to the exact part name — take the Prime-badged result that matches the name.
Prices are typical street prices (Sep 2026); expect ±15 %.

## Electronics

| # | Part | Qty | ≈ Price | Source | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | Raspberry Pi 5, 4 GB | 1 | $110 | [raspberrypi.com resellers](https://www.raspberrypi.com/products/raspberry-pi-5/) · [CanaKit](https://www.canakit.com/raspberry-pi-5-4gb.html) · [Amazon](https://www.amazon.com/s?k=raspberry+pi+5+4gb) | was $60 at launch; 2026 memory-driven price rises pushed it to ~$101–110. 8 GB unnecessary; avoid the $45 1 GB variant (too tight for encode + CV) |
| 2 | Official Pi 5 Active Cooler | 1 | $5 | [Adafruit 5815](https://www.adafruit.com/product/5815) · [Amazon](https://www.amazon.com/s?k=raspberry+pi+5+active+cooler) | head runs warm while encoding |
| 3 | microSD 64 GB A2 | 1 | $10 | [Amazon](https://www.amazon.com/s?k=sandisk+extreme+64gb+microsd+a2) | recordings land here |
| 4 | **Arducam 8 MP IMX219 motorized zoom/focus camera (B0167 “PTZ” lens kit)** | 1 | $70 | [Arducam store](https://www.arducam.com/product-category/cameras-for-raspberry-pi/) · [Amazon](https://www.amazon.com/s?k=arducam+ptz+camera+raspberry+pi+zoom) | the optical-zoom heart of the build; we use its camera + lens, not its little PT bracket. Budget alt: Pi Camera Module 3 ($25, digital zoom only) |
| 5 | Pi 5 camera FFC 300 mm (22-pin ↔ 15-pin) | 1 | $4 | [Adafruit 5819](https://www.adafruit.com/product/5819) · [Amazon](https://www.amazon.com/s?k=raspberry+pi+5+camera+cable+300mm) | Pi 5 uses the small 22-pin CSI |
| 6 | ESP32 DevKitC (×2-pack) | 1 | $12 | [Amazon](https://www.amazon.com/s?k=esp32+devkitc+38+pin) | one for base, one spare |
| 7 | **ESP32 + DW1000 UWB module** | 3 | $36 ea | [Makerfabs](https://www.makerfabs.com/esp32-uwb-ultra-wideband.html) · [Amazon](https://www.amazon.com/s?k=esp32+uwb+dw1000+module) | 2 anchors + 1 tag. Amazon carries Makerfabs-compatible boards with Prime; DW3000 version also works (same code family, better battery) |
| 8 | NEMA17 stepper, 59 N·cm | 1 | $14 | [Amazon](https://www.amazon.com/s?k=nema+17+stepper+59ncm) | any 1.5–2 A 17HS series |
| 9 | TMC2209 driver (stepstick) | 1 | $9 (3-pk) | [Amazon](https://www.amazon.com/s?k=tmc2209+v3+stepper+driver) | UART mode, StealthChop = silent pan |
| 10 | DS3225 / DS3218 25 kg **270°** servo | 1 | $17 | [Amazon](https://www.amazon.com/s?k=ds3225+25kg+servo+270+degree) | confirm the 270° variant in the listing |
| 11 | Slip ring 22 mm, 12 wire × 2 A | 1 | $25 | [Adafruit 736](https://www.adafruit.com/product/736) · [Amazon](https://www.amazon.com/s?k=slip+ring+12+wire+2a+22mm) | parallel 4+4 wires for power |
| 12 | WS2812B LED ring, 16 px | 1 | $10 | [Adafruit 1463](https://www.adafruit.com/product/1463) · [Amazon](https://www.amazon.com/s?k=ws2812b+ring+16+led) | status indicator |
| 13 | 12 V 5 A desktop PSU (5.5×2.1 barrel) | 1 | $16 | [Amazon](https://www.amazon.com/s?k=12v+5a+power+supply+barrel) | UL-listed brand |
| 14 | 12 V→5 V 5 A buck (USB-C out or bare) | 1 | $11 | [Amazon](https://www.amazon.com/s?k=12v+to+5v+5a+buck+converter+usb+c) | buck #2 — Pi rail; must hold 5.0 V at 5 A |
| 15 | MP1584 / LM2596 mini buck | 2 | $9 (6-pk) | [Amazon](https://www.amazon.com/s?k=mp1584+buck+converter) | buck #1 (base) + buck #3 (servo) |
| 16 | A3144 hall sensor + magnets | 1 | $7 | [Amazon](https://www.amazon.com/s?k=a3144+hall+effect+sensor+module) | pan homing |
| 17 | TP4056 USB-C charger w/ protection | 1 | $7 (5-pk) | [Amazon](https://www.amazon.com/s?k=tp4056+usb+c+lipo+charger+protection) | wearable |
| 18 | LiPo 1000 mAh 3.7 V (503450, JST) | 1 | $10 | [Adafruit 258](https://www.adafruit.com/product/258) · [Amazon](https://www.amazon.com/s?k=3.7v+1000mah+lipo+jst) | wearable battery |
| 19 | Barrel jack, JST kit, 18/22 AWG silicone wire, heatshrink | — | $15 | [Amazon](https://www.amazon.com/s?k=jst+connector+kit+22awg) | consumables |

## Mechanical

| # | Part | Qty | ≈ Price | Source | Notes |
| --- | --- | --- | --- | --- | --- |
| 20 | GT2 pulley 20T (5 mm bore) + 200 mm closed belt | 1 | $9 | [Amazon](https://www.amazon.com/s?k=gt2+20t+pulley+200mm+belt) | 60T side is printed |
| 21 | Lazy-susan bearing 3" | 1 | $8 | [Amazon](https://www.amazon.com/s?k=3+inch+lazy+susan+bearing) | pan stage |
| 22 | 6701ZZ bearing (12×18×4) ×4 | 1 | $7 | [Amazon](https://www.amazon.com/s?k=6701zz+bearing) | tilt idler side |
| 23 | M2.5/M3/M4 screw + brass-insert kit | 1 | $15 | [Amazon](https://www.amazon.com/s?k=m3+screw+assortment+brass+inserts+3d+printing) | |
| 24 | 1/4-20 brass insert + screw | 1 | $6 | [Amazon](https://www.amazon.com/s?k=1%2F4-20+brass+insert) | tripod interface |
| 25 | PETG filament 1 kg | 1 | $20 | [Amazon](https://www.amazon.com/s?k=petg+filament+1kg) | all printed parts |
| 26 | Aluminium tripod (1/4-20 head) | 1 | $26 | [Amazon](https://www.amazon.com/s?k=aluminum+camera+tripod) | skip if you own one |
| 27 | Watch-style strap + velcro pouch | 1 | $8 | [Amazon](https://www.amazon.com/s?k=elastic+armband+pouch+small) | wearable mounting |

## Totals

| Configuration | Total |
| --- | --- |
| **Full build** (optical zoom + UWB, own tripod) | **≈ $485** |
| Full build + tripod | ≈ $510 |
| Budget build (Camera Module 3 digital zoom, DW1000 boards from AliExpress at ~$25 — 2–3 week wait) | ≈ $360 |

Totals reflect the 2026 Raspberry Pi price rises (4 GB Pi 5 ≈ $110, up from
its $60 launch MSRP due to LPDDR4 shortages). Avoid Amazon "Pi 5 kits" at
$150–200 — they bundle a PSU/case/HDMI you don't need here.

## Sourcing notes

- **Fastest path (< 1 week)**: order items 1–5, 11, 12, 18 from Adafruit/Arducam
  (both ship next day; Arducam ships from US stock via their Amazon storefront
  too) and everything else on Amazon Prime.
- **Cheapest path**: AliExpress halves the price of items 6–17 but adds 2–4
  weeks — order the long-lead UWB boards there early if you're not in a hurry,
  since they're the single biggest line item.
- The only genuinely substitution-sensitive parts: the **270° servo** (a 180°
  DS3218 silently caps your tilt range — check the listing) and the **5 A
  Pi-rail buck** (cheap 3 A units brown-out a Pi 5 under encode load).
