#!/usr/bin/env python3
"""Print a SportCam part on a Bambu Lab A1 Mini on your network.

    python3 cad/printer.py --list                     the parts, per build
    python3 cad/printer.py lid                        slice, upload, start, follow
    python3 cad/printer.py anchor_arm --copies 2      two on one plate
    python3 cad/printer.py mast_foot mast_cradle      parts with the same settings share a plate
    python3 cad/printer.py lid --slice-only           just slice (open the .3mf in Bambu Studio to check)
    python3 cad/printer.py --file job.gcode.3mf       print something you sliced yourself
    python3 cad/printer.py --status                   what the printer is doing
    python3 cad/printer.py --watch                    follow the current print

What it does, in order:

  1. Checks the STLs are rendered from the current CAD and part sizes (the
     same stamp cad/fit.py writes), and warns if the part depends on sizes
     still marked MEASURE_TODO in cad/ordered_parts.toml.
  2. Slices the part with Bambu Studio's command line, using its own A1 mini,
     0.20 mm and PETG profiles plus the part's settings from
     docs/setup/11-3d-printing.md (walls, infill, top/bottom layers, brim,
     orientation — the lid is flipped onto its top face). The result goes to
     cad/sliced/<build>/ so you can open it in Bambu Studio.
  3. Asks before printing (skip with --yes), uploads the job to the printer's
     SD card over FTPS, starts it over the printer's local MQTT connection,
     and follows it until it finishes. Ctrl-C stops following, not printing.

Needs:
  * Bambu Studio installed (found in /Applications on a Mac, or give --slicer).
  * An SD card in the printer.
  * The printer reachable on your network, with LAN access on: on the
    printer's screen, Settings → Network (WLAN) → "LAN Only Mode" on, and on
    current firmware "Developer Mode" on too — without it the printer accepts
    the connection but ignores commands from anything but Bambu's own apps.
    The access code is on that screen.
  * Its IP address, serial number and access code, in
    ~/.config/sportcam/printer.toml (outside the repo — the access code is a
    password):

        ip = "192.168.1.50"
        serial = "0309DA4B1234567"     # Settings → Device on the printer
        access_code = "12345678"
        build = "without_uwb"          # or "with_uwb": which build's parts
        # optional:
        # filament = "Generic PETG @BBL A1M"
        # ams_slot = 0                 # AMS lite slot 0–3; leave out for the external spool
        # slicer = "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"

    or BAMBU_IP / BAMBU_SERIAL / BAMBU_ACCESS_CODE in the environment, or
    --ip / --serial / --access-code. Flags beat the environment, which beats
    the file.

Standard library only.
"""
import argparse
import ftplib
import json
import math
import os
import re
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # sport_cam
BUILDS = ("with_uwb", "without_uwb")
CONFIG = os.path.expanduser("~/.config/sportcam/printer.toml")
SLICED = os.path.join(HERE, "sliced")

MACHINE = "Bambu Lab A1 mini 0.4 nozzle"
PROCESS = "0.20mm Standard @BBL A1M"
FILAMENTS = ("Bambu PETG Basic @BBL A1M 0.4 nozzle", "Bambu PETG Basic @BBL A1M", "Generic PETG @BBL A1M")
PLATES = {"textured": "Textured PEI Plate", "smooth": "High Temp Plate", "cool": "Cool Plate",
          "engineering": "Engineering Plate"}

# ----------------------------------------------------------------------------
#  the parts — settings from docs/setup/11-3d-printing.md; keep the two in step
# ----------------------------------------------------------------------------
# walls, infill %, plus any other Bambu Studio process keys. `sizes` are the
# ordered_parts.toml entries the part is shaped by (for the "not measured" warning).
_ALL_INSIDE = ["pi", "shifter", "pd_trigger", "buck", "gauge", "latch", "switch", "jack", "led_ring", "ptz",
               "tripod_nut"]
PARTS = {
    "base_housing": dict(aliases=["enclosure", "housing"], walls=4, infill=20, sizes=_ALL_INSIDE,
                         note={"with_uwb": "the three wall bosses print without support and droop a little "
                                           "underneath (nobody sees it); --supports adds tree supports from the plate"}),
    "shelf": dict(aliases=[], walls=3, infill=20, sizes=["pi", "shifter", "led_ring"],
                  note="white or natural PETG if you have it: its underside bounces the LED ring's light out"),
    "lid": dict(aliases=[], walls=5, infill=40, flip=True, sizes=["ptz"] + _ALL_INSIDE,
                note="printed top face down (flipped automatically): it carries the whole camera"),
    "led_diffuser_ring": dict(aliases=["diffuser", "band", "led_diffuser"], walls=2, infill=0,
                              extra={"top_shell_layers": "0", "bottom_shell_layers": "0",
                                     "top_shell_thickness": "0", "bottom_shell_thickness": "0",
                                     "brim_type": "outer_only", "brim_width": "5"},
                              sizes=_ALL_INSIDE, white=True,
                              note="needs WHITE or natural PETG loaded — it has to pass the LEDs' light"),
    "battery_tray": dict(aliases=["tray"], walls=3, infill=20, sizes=["power_bank"]),
    "anchor_arm": dict(aliases=["arm", "arms"], walls=4, infill=25, builds=["with_uwb"], sizes=["ula1", "usb_extension"],
                       note="you need two: --copies 2 puts both on one plate"),
    "mast_foot": dict(aliases=["foot"], walls=4, infill=25, builds=["with_uwb"], sizes=["dowel"]),
    "mast_cradle": dict(aliases=["cradle"], walls=4, infill=25, builds=["with_uwb"], sizes=["dowel", "ula1"]),
    "wearable_case": dict(aliases=["pod", "wearable"], walls=2, infill=20, builds=["with_uwb"],
                          sizes=["tag_bank", "ula1"]),
}


def part_name(name):
    n = name.lower().replace("-", "_").removesuffix(".stl")
    for k, p in PARTS.items():
        if n == k or n in p["aliases"]:
            return k
    raise SystemExit(f"no part called {name!r}. Parts: " + ", ".join(PARTS) + "  (python3 cad/printer.py --list)")


def process_overrides(part, supports):
    p = PARTS[part]
    o = {"wall_loops": str(p["walls"]), "sparse_infill_density": f"{p['infill']}%", "layer_height": "0.2"}
    o.update(p.get("extra", {}))
    if supports:
        o.update({"enable_support": "1", "support_type": "tree(auto)", "support_on_build_plate_only": "1"})
    return o


def part_note(part, build):
    n = PARTS[part].get("note")
    return n.get(build) if isinstance(n, dict) else n


# ----------------------------------------------------------------------------
#  settings: file < environment < flags
# ----------------------------------------------------------------------------

def settings(a):
    s = {}
    if os.path.exists(CONFIG):
        with open(CONFIG, "rb") as f:
            s.update(tomllib.load(f))
    for k, env in (("ip", "BAMBU_IP"), ("serial", "BAMBU_SERIAL"), ("access_code", "BAMBU_ACCESS_CODE"),
                   ("build", "SPORTCAM_BUILD"), ("slicer", "BAMBU_STUDIO")):
        if os.environ.get(env):
            s[k] = os.environ[env]
    for k in ("ip", "serial", "access_code", "build", "slicer", "profiles", "filament", "ams_slot", "plate"):
        v = getattr(a, k, None)
        if v is not None:
            s[k] = v
    return s


def need(s, *keys):
    missing = [k for k in keys if not s.get(k)]
    if missing:
        raise SystemExit(
            f"missing {', '.join(missing)}. Put them in {CONFIG}:\n\n"
            '    ip = "192.168.1.50"\n    serial = "0309DA4B1234567"\n    access_code = "12345678"\n'
            '    build = "without_uwb"\n\n'
            "(the printer shows them under Settings → Network and Settings → Device), "
            "or pass --ip / --serial / --access-code / --build.")


# ----------------------------------------------------------------------------
#  checks before slicing
# ----------------------------------------------------------------------------

def stl_path(build, part):
    return os.path.join(ROOT, build, "cad", "stl", part + ".stl")


def check_fresh(build):
    """Same test as fit.py's "STLs are rendered from the current CAD and part sizes"."""
    sys.path.insert(0, HERE)
    import fit  # noqa: E402
    stamp = os.path.join(ROOT, build, "cad", "stl", fit.STAMP)
    have = open(stamp).read().strip() if os.path.exists(stamp) else ""
    return have == fit.inputs_hash(build)


def unmeasured(build, parts):
    """Parts this job is shaped by that still have a MEASURE_TODO in ordered_parts.toml."""
    sys.path.insert(0, HERE)
    import fit  # noqa: E402
    with open(os.path.join(HERE, "ordered_parts.toml"), "rb") as f:
        P = tomllib.load(f)
    todo = fit.measure_todos()
    names = []
    for part in parts:
        for k in PARTS[part]["sizes"]:
            e = P.get(k)
            if e and k in todo and build in e.get("builds", BUILDS) and e["name"] not in names:
                names.append(e["name"])
    return names


# ----------------------------------------------------------------------------
#  slicing with Bambu Studio's command line
# ----------------------------------------------------------------------------

def find_slicer(s):
    cands = [s.get("slicer"), "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
             os.path.expanduser("~/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
             shutil.which("bambu-studio"), shutil.which("BambuStudio")]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise SystemExit("Bambu Studio not found. Install it (bambulab.com/en/download/studio), or pass "
                     "--slicer /path/to/BambuStudio (on a Mac: …/BambuStudio.app/Contents/MacOS/BambuStudio).")


def find_profiles(s, slicer):
    if s.get("profiles"):
        return s["profiles"]
    d = os.path.dirname(os.path.realpath(slicer))
    for _ in range(4):                         # …/MacOS → …/Contents/Resources, or an unpacked AppImage
        for sub in ("Resources/profiles/BBL", "resources/profiles/BBL"):
            if os.path.isdir(os.path.join(d, sub)):
                return os.path.join(d, sub)
        d = os.path.dirname(d)
    raise SystemExit("can't find Bambu Studio's printer profiles next to it; pass --profiles "
                     ".../resources/profiles/BBL")


def flatten(profiles, kind, name):
    """A system profile complete with everything it inherits: Bambu Studio's
    command line loads only complete profiles. The app ships them resolved in
    <kind>_full/; failing that, merge the `inherits` chain (parents are named
    by file) ourselves."""
    full = os.path.join(profiles, kind + "_full", name + ".json")
    if os.path.exists(full):
        with open(full, encoding="utf-8") as f:
            return json.load(f)
    chain, n = [], name
    while n:
        path = os.path.join(profiles, kind, n + ".json")
        if not os.path.exists(path):
            raise SystemExit(f"no {kind} profile {n!r} in {profiles}/{kind}")
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        chain.append(d)
        n = d.get("inherits")
    out = {}
    for d in reversed(chain):
        out.update(d)
    out.pop("inherits", None)
    out["name"] = name
    return out


def pick_filament(s, profiles):
    if s.get("filament"):
        return s["filament"]
    for f in FILAMENTS:
        if os.path.exists(os.path.join(profiles, "filament", f + ".json")):
            return f
    raise SystemExit("no PETG profile for the A1 mini found; pass --filament with one from "
                     f"{profiles}/filament")


def read_stl(path):
    """Triangles of an STL, binary or ASCII."""
    data = open(path, "rb").read()
    n = struct.unpack_from("<I", data, 80)[0] if len(data) >= 84 else 0
    if len(data) == 84 + 50 * n:
        tris = []
        for i in range(n):
            v = struct.unpack_from("<12f", data, 84 + 50 * i)
            tris.append((v[3:6], v[6:9], v[9:12]))
        return tris
    pts = [tuple(map(float, m)) for m in re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data)]
    return [tuple(pts[i:i + 3]) for i in range(0, len(pts), 3)]


def write_flipped(src, dst):
    """Turn a part over (180° about X) and stand it on z = 0."""
    tris = [tuple((x, -y, -z) for x, y, z in t) for t in read_stl(src)]
    zmin = min(v[2] for t in tris for v in t)
    with open(dst, "wb") as f:
        f.write(b"SportCam: flipped for printing".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            a, b, c = [(x, y, z - zmin) for x, y, z in t]
            u = [b[i] - a[i] for i in range(3)]
            w = [c[i] - a[i] for i in range(3)]
            nx, ny, nz = u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            f.write(struct.pack("<12fH", nx / ln, ny / ln, nz / ln, *a, *b, *c, 0))


def slice_parts(s, build, parts, copies, supports, plate, out):
    slicer = find_slicer(s)
    profiles = find_profiles(s, slicer)
    filament = pick_filament(s, profiles)
    groups = {json.dumps(process_overrides(p, supports), sort_keys=True) for p in parts}
    if len(groups) > 1:
        raise SystemExit("those parts print with different settings; print them one at a time")
    label = "+".join(parts) + (f" ×{copies}" if copies > 1 else "")
    with tempfile.TemporaryDirectory() as td:
        machine = flatten(profiles, "machine", MACHINE)
        process = flatten(profiles, "process", PROCESS)
        process.update(process_overrides(parts[0], supports))
        # a user preset on top of the system one, as Bambu Studio saves them
        process.update({"name": f"SportCam {'+'.join(parts)}", "from": "User", "inherits": PROCESS})
        fil = flatten(profiles, "filament", filament)
        files = {}
        for kind, d in (("machine", machine), ("process", process), ("filament", fil)):
            files[kind] = os.path.join(td, kind + ".json")
            with open(files[kind], "w", encoding="utf-8") as f:
                json.dump(d, f, indent=1)
        stls = []
        for p in parts:
            src = stl_path(build, p)
            if not os.path.exists(src):
                raise SystemExit(f"{src} missing — run python3 cad/fit.py")
            if PARTS[p].get("flip"):
                dst = os.path.join(td, p + ".stl")
                write_flipped(src, dst)
                src = dst
            stls += [src] * copies
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cmd = [slicer, "--load-settings", f"{files['machine']};{files['process']}",
               "--load-filaments", files["filament"], "--curr-bed-type", PLATES[plate],
               "--arrange", "1", "--orient", "0", "--slice", "0",
               "--outputdir", os.path.dirname(out), "--export-3mf", os.path.basename(out), *stls]
        print(f"slicing {label} ({build}) with Bambu Studio — {filament}, {PLATES[plate]} …")
        if os.path.exists(out):
            os.remove(out)
        result = os.path.join(os.path.dirname(out), "result.json")
        if os.path.exists(result):
            os.remove(result)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out):
            why = ""
            if os.path.exists(result):         # the CLI records why it gave up here
                with open(result, encoding="utf-8") as f:
                    why = json.load(f).get("error_string", "")
            tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-15:])
            raise SystemExit(f"Bambu Studio couldn't slice it (exit {r.returncode})"
                             + (f": {why}" if why else "") + (f"\n{tail}" if tail else ""))
    return out, filament


def job_info(path):
    """Plate gcode, print time and filament from a sliced .gcode.3mf."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        plates = sorted(n for n in names if re.fullmatch(r"Metadata/plate_\d+\.gcode", n))
        if not plates:
            raise SystemExit(f"{path} has no sliced plate in it — slice it (in Bambu Studio: Slice, then "
                             "File → Export → Export plate sliced file)")
        info = {"plate": plates[0], "plates": len(plates)}
        if "Metadata/slice_info.config" in names:
            x = z.read("Metadata/slice_info.config").decode("utf-8", "replace")
            m = re.search(r'key="prediction" value="(\d+)"', x)
            if m:
                info["seconds"] = int(m.group(1))
            m = re.search(r'key="weight" value="([\d.]+)"', x)
            if m:
                info["grams"] = float(m.group(1))
            m = re.search(r'<filament [^>]*type="([^"]+)"', x)
            if m:
                info["filament_type"] = m.group(1)
    return info


def hm(sec):
    sec = int(sec)
    return f"{sec // 3600} h {sec % 3600 // 60:02d} min" if sec >= 3600 else f"{sec // 60} min"


# ----------------------------------------------------------------------------
#  the printer: FTPS for the file, MQTT for everything else
# ----------------------------------------------------------------------------

def _tls():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False          # the printer's certificate is self-signed by Bambu
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class ImplicitFTPS(ftplib.FTP_TLS):
    """Bambu printers speak FTP over TLS from the first byte (port 990), and
    want the data connection to resume the control connection's TLS session."""

    def __init__(self):
        super().__init__(context=_tls())
        self._sock = None

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, value):
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
        return conn, size


def upload(s, local, remote):
    ftp = ImplicitFTPS()
    ftp.connect(s["ip"], 990, timeout=30)
    ftp.login("bblp", str(s["access_code"]))
    ftp.prot_p()
    size = os.path.getsize(local)
    sent = [0]

    def cb(block):
        sent[0] += len(block)
        print(f"\r  uploading {remote}: {100 * sent[0] // size:3d} %", end="", flush=True)

    with open(local, "rb") as f:
        ftp.storbinary(f"STOR {remote}", f, blocksize=64 * 1024, callback=cb)
    print()
    try:
        ftp.quit()
    except (OSError, EOFError, ftplib.Error):
        pass          # some firmware drops the connection instead of answering QUIT


class MQTT:
    """Just enough MQTT 3.1.1 to talk to one printer: connect, subscribe,
    publish at QoS 0, keep alive."""

    def __init__(self, host, password, port=8883, keepalive=60):
        raw = socket.create_connection((host, port), timeout=15)
        self.s = _tls().wrap_socket(raw, server_hostname=host)
        self.keepalive, self.last, self.buf = keepalive, time.monotonic(), b""
        cid = f"sportcam-{os.getpid()}".encode()
        user, pw = b"bblp", str(password).encode()
        var = self._str(b"MQTT") + bytes([4, 0xC2]) + struct.pack(">H", keepalive)
        self._send(0x10, var + self._str(cid) + self._str(user) + self._str(pw))
        try:
            kind, body = self._read()
        except TimeoutError:
            raise SystemExit("the printer didn't answer the connection") from None
        if kind != 0x20 or len(body) < 2 or body[1] != 0:
            code = body[1] if kind == 0x20 and len(body) > 1 else None
            raise SystemExit("the printer refused the connection"
                             + (" — wrong access code?" if code in (4, 5) else f" (code {code})"))

    @staticmethod
    def _str(b):
        return struct.pack(">H", len(b)) + b

    def _send(self, header, body):
        n, ln = len(body), b""
        while True:
            d, n = n % 128, n // 128
            ln += bytes([d | (0x80 if n else 0)])
            if not n:
                break
        self.s.sendall(bytes([header]) + ln + body)
        self.last = time.monotonic()

    def _packet(self):
        """One whole packet from the buffer, or None if it hasn't all arrived."""
        b, i, mult, n = self.buf, 1, 1, 0
        while True:
            if i >= len(b):
                return None
            d = b[i]
            n += (d & 0x7F) * mult
            mult *= 128
            i += 1
            if not d & 0x80:
                break
        if len(b) < i + n:
            return None
        self.buf = b[i + n:]
        return b[0] & 0xF0, b[i:i + n]

    def _read(self, timeout=15.0):
        """Next packet; a timeout loses nothing, partial packets stay buffered."""
        end = time.monotonic() + timeout
        while True:
            p = self._packet()
            if p:
                return p
            left = end - time.monotonic()
            if left <= 0:
                raise TimeoutError
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except (socket.timeout, TimeoutError):
                raise TimeoutError from None
            if not chunk:
                raise ConnectionError("the printer closed the connection")
            self.buf += chunk

    def subscribe(self, topic):
        self._send(0x82, struct.pack(">H", 1) + self._str(topic.encode()) + b"\x00")

    def publish(self, topic, payload):
        self._send(0x30, self._str(topic.encode()) + json.dumps(payload).encode())

    def messages(self, timeout):
        """JSON messages on our subscription, until `timeout` seconds pass quietly."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if time.monotonic() - self.last > self.keepalive / 2:
                self._send(0xC0, b"")
            try:
                kind, body = self._read(max(0.1, min(5.0, end - time.monotonic())))
            except TimeoutError:
                continue
            if kind != 0x30:
                continue
            tl = struct.unpack_from(">H", body)[0]
            try:
                yield json.loads(body[2 + tl:].decode("utf-8", "replace"))
            except ValueError:
                continue

    def close(self):
        try:
            self._send(0xE0, b"")
            self.s.close()
        except OSError:
            pass


class Printer:
    def __init__(self, s):
        need(s, "ip", "serial", "access_code")
        self.serial = str(s["serial"])
        try:
            self.m = MQTT(s["ip"], s["access_code"])
        except (OSError, ssl.SSLError) as e:
            raise SystemExit(f"can't reach the printer at {s['ip']}:8883 ({e}). Is it on, on this network, "
                             "with LAN Only Mode on?")
        self.m.subscribe(f"device/{self.serial}/report")
        self.state = {}
        self.seq = 0

    def send(self, section, command, **kw):
        self.seq += 1
        self.m.publish(f"device/{self.serial}/request",
                       {section: {"sequence_id": str(self.seq), "command": command, **kw}})

    def refresh(self, timeout=8):
        self.send("pushing", "pushall")
        for msg in self.m.messages(timeout):
            if "print" in msg:
                self.state.update(msg["print"])
                if "gcode_state" in msg["print"]:
                    return self.state
        raise SystemExit("the printer didn't report its state — check the serial number")

    def updates(self, timeout):
        for msg in self.m.messages(timeout):
            if "print" in msg:
                self.state.update(msg["print"])
                yield msg["print"]

    def start(self, remote, plate, name, ams_slot):
        self.send("print", "project_file",
                  param=plate, url=f"file:///sdcard/{remote}", subtask_name=name,
                  project_id="0", profile_id="0", task_id="0", subtask_id="0", md5="",
                  bed_type="auto", bed_leveling=True, flow_cali=True, vibration_cali=True,
                  layer_inspect=False, timelapse=False,
                  use_ams=ams_slot is not None, ams_mapping=[int(ams_slot or 0)])


BUSY = ("RUNNING", "PREPARE", "PAUSE", "SLICING")


def describe(st, temps=True):
    g = st.get("gcode_state", "?")
    out = [g]
    if g in BUSY or g == "FINISH":
        if st.get("subtask_name"):
            out.append(st["subtask_name"])
        if "mc_percent" in st:
            out.append(f"{st['mc_percent']} %")
        if st.get("total_layer_num"):
            out.append(f"layer {st.get('layer_num', 0)}/{st['total_layer_num']}")
        if g in BUSY and st.get("mc_remaining_time") is not None:
            out.append(f"{hm(60 * int(st['mc_remaining_time']))} left")
    if temps and st.get("nozzle_temper") is not None:
        out.append(f"nozzle {float(st['nozzle_temper']):.0f}°/{float(st.get('nozzle_target_temper', 0)):.0f}°")
    if temps and st.get("bed_temper") is not None:
        out.append(f"bed {float(st['bed_temper']):.0f}°/{float(st.get('bed_target_temper', 0)):.0f}°")
    if st.get("print_error"):
        out.append(f"ERROR {st['print_error']:#x} (see the printer's screen)")
    return " · ".join(out)


def spool(st):
    t = st.get("vt_tray") or {}
    if t.get("tray_type"):
        return f"{t['tray_type']}" + (f", colour #{t['tray_color'][:6]}" if t.get("tray_color") else "")
    return None


def follow(pr, started=False, stall=300, name=None):
    """Print each change of state until the job ends. Returns the final state,
    or None if you stop following (Ctrl-C)."""
    last, t0, seen_busy = None, time.monotonic(), not started
    try:
        while True:
            for _ in pr.updates(60):
                g = pr.state.get("gcode_state")
                line = describe(pr.state, temps=g == "PREPARE")   # temperatures jitter; show them while it heats
                if line != last:
                    print(time.strftime("%H:%M:%S ") + line, flush=True)
                    last = line
                if g in BUSY:
                    seen_busy = True
                elif seen_busy and g in ("FINISH", "FAILED", "IDLE"):
                    return g
                elif g == "FAILED" and name and pr.state.get("subtask_name") == name:
                    return g          # refused our job before it began
                if not seen_busy and time.monotonic() - t0 > stall:
                    break
            if not seen_busy and time.monotonic() - t0 > stall:
                raise SystemExit("the printer hasn't started the job after 5 minutes — look at its screen. "
                                 "If it shows nothing, turn Developer Mode on (Settings → Network) and try again.")
            pr.send("pushing", "pushall")        # a quiet minute: ask, in case we missed something
    except KeyboardInterrupt:
        print("\nstopped following; the print carries on. python3 cad/printer.py --watch to follow it again.")
        return None


# ----------------------------------------------------------------------------

def list_parts(build):
    print(f"{'part':20} {'also':24} {'walls':>5} {'infill':>6}  builds")
    for k, p in PARTS.items():
        bl = p.get("builds", list(BUILDS))
        if build and build not in bl:
            continue
        print(f"{k:20} {', '.join(p['aliases']):24} {p['walls']:>5} {p['infill']:>5}%  {', '.join(bl)}")
        if part_note(k, build or "with_uwb"):
            print(f"{'':20} {part_note(k, build or 'with_uwb')}")


def confirm(q, yes):
    if yes:
        return True
    if not sys.stdin.isatty():
        raise SystemExit("not starting without --yes (no terminal to ask)")
    return input(q + " [y/N] ").strip().lower() in ("y", "yes")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 epilog="Full notes: the top of cad/printer.py.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parts", nargs="*", help="part(s) to print, e.g. lid, enclosure, tray (see --list)")
    ap.add_argument("--build", choices=BUILDS, help="which build's parts (default: `build` in the config file)")
    ap.add_argument("--list", action="store_true", help="list the parts and their settings")
    ap.add_argument("--status", action="store_true", help="show what the printer is doing")
    ap.add_argument("--watch", action="store_true", help="follow the current print")
    ap.add_argument("--file", help="print this sliced .gcode.3mf instead of slicing a part")
    ap.add_argument("--slice-only", action="store_true", help="slice, then stop (nothing is sent)")
    ap.add_argument("--copies", type=int, default=1, help="copies of the part on the plate")
    ap.add_argument("--supports", action="store_true", help="tree supports from the plate (off by default)")
    ap.add_argument("--plate", choices=PLATES, help="build plate fitted (default textured)")
    ap.add_argument("--filament", help=f"Bambu Studio filament profile (default: {FILAMENTS[0]})")
    ap.add_argument("--ams-slot", type=int, choices=range(4), help="feed from this AMS lite slot (default: external spool)")
    ap.add_argument("--no-follow", action="store_true", help="start the print and exit")
    ap.add_argument("--force", action="store_true", help="slice even if the STLs are out of date")
    ap.add_argument("-y", "--yes", action="store_true", help="don't ask before starting the print")
    ap.add_argument("--ip"), ap.add_argument("--serial"), ap.add_argument("--access-code", dest="access_code")
    ap.add_argument("--slicer", help="path to the Bambu Studio executable")
    ap.add_argument("--profiles", help="Bambu Studio's resources/profiles/BBL folder")
    a = ap.parse_args()
    s = settings(a)

    if a.list:
        return list_parts(s.get("build"))
    if a.status or a.watch:
        pr = Printer(s)
        st = pr.refresh()
        print(describe(st))
        if spool(st):
            print("spool: " + spool(st))
        if a.watch and st.get("gcode_state") in BUSY:
            follow(pr)
        pr.m.close()
        return

    if bool(a.parts) == bool(a.file):
        ap.error("name a part (or several with the same settings), or give --file")

    # ---- the job ----------------------------------------------------------
    if a.file:
        job, label, filament, warn = a.file, os.path.basename(a.file).split(".")[0], None, []
        remote = re.sub(r"[^\w.-]", "_", os.path.basename(a.file))
        if not remote.endswith(".3mf"):
            ap.error("--file wants a sliced .gcode.3mf")
    else:
        need(s, "build")
        build = s["build"]
        if build not in BUILDS:
            raise SystemExit(f"build must be one of {', '.join(BUILDS)}")
        parts = list(dict.fromkeys(part_name(p) for p in a.parts))
        for p in parts:
            if build not in PARTS[p].get("builds", BUILDS):
                raise SystemExit(f"{p} is only in the {', '.join(PARTS[p]['builds'])} build (--build)")
        if not check_fresh(build) and not a.force:
            raise SystemExit(f"the {build} STLs are out of date with the CAD or the part sizes — run "
                             "python3 cad/fit.py first (or --force to print them as they are)")
        tag = "_".join(parts) + (f"_x{a.copies}" if a.copies > 1 else "")
        label = f"sportcam_{build}_{tag}"
        job = os.path.join(SLICED, build, label + ".gcode.3mf")
        job, filament = slice_parts(s, build, parts, max(1, a.copies), a.supports, s.get("plate", "textured"), job)
        remote = label + ".gcode.3mf"
        warn = unmeasured(build, parts)
        for p in parts:
            if part_note(p, build):
                print(f"  {p}: {part_note(p, build)}")

    info = job_info(job)
    print(f"  {os.path.relpath(job)}"
          + (f" — {hm(info['seconds'])}" if "seconds" in info else "")
          + (f", {info['grams']:.0f} g" if "grams" in info else "")
          + (f" of {info['filament_type']}" if "filament_type" in info else ""))
    if info["plates"] > 1:
        print(f"  note: {info['plates']} plates in the file; printing {info['plate']}")
    if warn:
        print("  sizes still marked MEASURE_TODO in cad/ordered_parts.toml (docs/*/setup/15-verification.md, 'Before you print'):\n    "
              + "\n    ".join(warn))
    if a.slice_only:
        return

    # ---- the printer ------------------------------------------------------
    pr = Printer(s)
    st = pr.refresh()
    print("printer: " + describe(st))
    if st.get("gcode_state") in BUSY:
        raise SystemExit("the printer is busy; wait for it to finish (--watch), or stop it on its screen")
    sp = spool(st)
    if a.ams_slot is None and s.get("ams_slot") is None:
        print("spool: " + (sp or "external spool (type not set on the printer)"))
        if sp and info.get("filament_type") and info["filament_type"].upper() not in sp.upper():
            print(f"  WARNING: the job is sliced for {info['filament_type']} but the printer says {sp}")
    if not confirm(f"Print {label} on the A1 Mini now?" + (" (sizes above not yet measured)" if warn else ""), a.yes):
        print("not printing")
        return
    upload(s, job, remote)
    pr.start(remote, info["plate"], label, s.get("ams_slot"))
    print("started — the printer levels the bed and calibrates first, so the first few minutes look idle")
    if a.no_follow:
        return
    end = follow(pr, started=True, name=label)
    if end == "FINISH":
        print("done. Let the plate cool before you take the part off.")
    elif end:
        sys.exit(f"the print ended {end} — check the printer's screen")


if __name__ == "__main__":
    main()
