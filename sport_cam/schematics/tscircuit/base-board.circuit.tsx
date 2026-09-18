/**
 * SportCam base-controller carrier board — tscircuit source.
 *
 * This is the one custom PCB in the project (everything else is off-the-shelf
 * modules on headers). It carries the ESP32 DevKitC, a TMC2209 stepstick, the
 * 12 V input, buck #1, and screw terminals for the LED ring, stepper, and slip
 * ring feed.
 *
 * Preview / export:
 *   npm create tscircuit@latest   (or add to an existing tscircuit project)
 *   tsci dev        — live schematic + PCB preview in the browser
 *   tsci export     — gerbers / schematic SVG
 */
export default () => (
  <board width="70mm" height="55mm">
    {/* ESP32 DevKitC on two 19-pin female headers */}
    <chip
      name="U1"
      footprint="dip38_w25.4mm_p2.54mm"
      pinLabels={{
        pin1: "3V3", pin2: "EN", pin15: "GND",
        pin9: "G25_STEP", pin10: "G26_DIR", pin11: "G27_NEN",
        pin28: "G17_UART", pin30: "G18_LED", pin19: "VIN_5V",
      }}
      schX={0}
      schY={0}
    />

    {/* TMC2209 stepstick on 2×8 headers */}
    <chip
      name="U2"
      footprint="dip16_w15.24mm_p2.54mm"
      pinLabels={{
        pin1: "EN", pin2: "MS1", pin3: "MS2", pin4: "PDN_UART",
        pin5: "CLK", pin6: "STEP", pin7: "DIR", pin8: "GND",
        pin9: "VM_12V", pin10: "GND_M", pin11: "B2", pin12: "B1",
        pin13: "A1", pin14: "A2", pin15: "VDD_5V", pin16: "GND_L",
      }}
      schX={6}
      schY={0}
    />

    {/* Buck #1: MP1584 module on a 4-pin header */}
    <chip
      name="U3"
      footprint="dip4_w10.16mm_p2.54mm"
      pinLabels={{ pin1: "VIN_12V", pin2: "GND_I", pin3: "VOUT_5V", pin4: "GND_O" }}
      schX={-6}
      schY={2}
    />

    {/* Connectors */}
    <chip name="J1" footprint="pinrow2" pinLabels={{ pin1: "V12", pin2: "GND" }} schX={-9} schY={0} />       {/* 12V barrel in */}
    <chip name="J2" footprint="pinrow4" pinLabels={{ pin1: "A1", pin2: "A2", pin3: "B1", pin4: "B2" }} schX={10} schY={0} />  {/* stepper */}
    <chip name="J3" footprint="pinrow3" pinLabels={{ pin1: "V5", pin2: "DIN", pin3: "GND" }} schX={6} schY={-4} />            {/* LED ring */}
    <chip name="J4" footprint="pinrow2" pinLabels={{ pin1: "V12", pin2: "GND" }} schX={-9} schY={-3} />       {/* slip ring feed */}

    <resistor name="R1" resistance="330" footprint="0805" schX={3} schY={-4} />
    <capacitor name="C1" capacitance="100uF" footprint="1206" schX={8} schY={3} />

    {/* Control signals */}
    <trace from=".U1 > .G25_STEP" to=".U2 > .STEP" />
    <trace from=".U1 > .G26_DIR" to=".U2 > .DIR" />
    <trace from=".U1 > .G27_NEN" to=".U2 > .EN" />
    <trace from=".U1 > .G17_UART" to=".U2 > .PDN_UART" />
    <trace from=".U1 > .G18_LED" to=".R1 > .pin1" />
    <trace from=".R1 > .pin2" to=".J3 > .DIN" />

    {/* Stepper coils */}
    <trace from=".U2 > .A1" to=".J2 > .A1" />
    <trace from=".U2 > .A2" to=".J2 > .A2" />
    <trace from=".U2 > .B1" to=".J2 > .B1" />
    <trace from=".U2 > .B2" to=".J2 > .B2" />

    {/* Power */}
    <trace from=".J1 > .V12" to=".U3 > .VIN_12V" />
    <trace from=".J1 > .V12" to=".U2 > .VM_12V" />
    <trace from=".J1 > .V12" to=".J4 > .V12" />
    <trace from=".C1 > .pin1" to=".U2 > .VM_12V" />
    <trace from=".C1 > .pin2" to=".U2 > .GND_M" />
    <trace from=".U3 > .VOUT_5V" to=".U1 > .VIN_5V" />
    <trace from=".U3 > .VOUT_5V" to=".U2 > .VDD_5V" />
    <trace from=".U3 > .VOUT_5V" to=".J3 > .V5" />

    {/* Grounds */}
    <trace from=".J1 > .GND" to=".U3 > .GND_I" />
    <trace from=".U3 > .GND_O" to=".U1 > .GND" />
    <trace from=".U3 > .GND_O" to=".U2 > .GND" />
    <trace from=".U3 > .GND_O" to=".J3 > .GND" />
    <trace from=".U3 > .GND_O" to=".J4 > .GND" />
  </board>
);
