"""Generate dji-fcc.kicad_sch from design.py.

Run with:  uv run --with kiutils python gen_sch.py
Connectivity is expressed with local net labels placed on every pin end, so the sheet is ERC-clean
and readable by net name rather than by wire routing.
"""
import copy
import os
import sys
import uuid

from kiutils.symbol import SymbolLib

import design

HERE = os.path.dirname(os.path.abspath(__file__))
SYMDIR = os.path.join(os.environ.get("KICAD_APP", os.path.expanduser("~/Applications/KiCad/KiCad.app")), "Contents/SharedSupport/symbols")
PROJECT = "dji-fcc"
ROOT = str(uuid.uuid5(uuid.NAMESPACE_DNS, "dji-fcc-esp32-root"))
_libs = {}


def uid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "dji-fcc/" + "/".join(map(str, parts))))


def lib_symbol(libid):
    """Return a flattened (extends-resolved) kiutils Symbol named for embedding in the schematic."""
    lib, name = libid.split(":")
    if lib not in _libs:
        path = os.path.join(HERE, "lib", lib + ".kicad_sym") if lib == "dji_parts" else f"{SYMDIR}/{lib}.kicad_sym"
        _libs[lib] = SymbolLib.from_file(path)
    syms = {s.entryName: s for s in _libs[lib].symbols}
    sym = syms[name]
    if sym.extends:
        parent = copy.deepcopy(syms[sym.extends])
        for p in sym.properties:
            for q in parent.properties:
                if q.key == p.key:
                    q.value = p.value
        parent.entryName = name
        parent.extends = None
        for u in parent.units:
            u.entryName = f"{name}_{u.unitId}_{u.styleId}"
        sym = parent
    else:
        sym = copy.deepcopy(sym)
    sym.libId = libid
    return sym


def pins_of(sym):
    out = []
    for u in sym.units:
        for p in u.pins:
            out.append(p)
    return out


def label_angle(pin_angle):
    return {0: 180, 180: 0, 90: 270, 270: 90}[int(pin_angle) % 360]


def sexp_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------------------------
# placement (mm on an A3 sheet): ref -> (x, y)
# --------------------------------------------------------------------------------------------
POS = {
    # MCU block
    "U1": (70, 110), "R1": (125, 60), "C1": (140, 60), "C2": (155, 60), "C3": (170, 60),
    "TP1": (100, 170), "TP2": (110, 170), "TP3": (120, 170), "TP4": (130, 170),
    "TP5": (140, 170), "TP6": (150, 170), "TP7": (160, 170), "TP8": (170, 170),
    # 3V3 LDO
    "U2": (230, 60), "C4": (260, 60), "C5": (275, 60),
    # status LEDs + sensing
    "R17": (300, 45), "D6": (300, 70), "R18": (320, 45), "D7": (320, 70), "R19": (340, 45), "D8": (340, 70),
    "R20": (365, 45), "R21": (365, 75), "C14": (380, 60), "R22": (395, 45), "R23": (395, 75),
    # remote side (J1, USLC6, boost, switch)
    "J1": (45, 235), "R15": (85, 220), "R16": (100, 220), "D5": (115, 220), "U7": (140, 225),
    "U5": (200, 225), "L1": (235, 205), "D4": (255, 205), "C9": (275, 205), "C10": (290, 205), "C11": (305, 205),
    "R9": (235, 245), "R10": (250, 245), "R11": (265, 245),
    "U6": (200, 275), "R12": (235, 275), "R13": (250, 275), "R14": (265, 275), "C12": (280, 275), "C13": (295, 275),
    # charge side
    "J2": (45, 165), "R2": (85, 150), "R3": (100, 150), "D1": (115, 150), "C6": (130, 150),
    "U3": (215, 160), "R4": (250, 150), "C7": (265, 150),
    "J3": (340, 130), "U4": (340, 175), "Q1": (385, 180), "R7": (340, 215), "C8": (355, 215), "R8": (370, 215),
    "U9": (75, 262), "U8": (118, 262), "C15": (145, 262),
    "H1": (400, 260), "H2": (415, 260), "FID1": (400, 275), "FID2": (410, 275), "FID3": (420, 275),
}
for i, ref in enumerate(["R17"]):
    pass

TEXTS = [
    (30, 25, "dji-fcc-esp32: ESP32-S3 USB host that sends the DJI N1 'FCC patch'"),
    (30, 40, "MCU (ESP32-S3-MINI-1) + programming/test pads"),
    (215, 35, "3V3 LDO"), (290, 30, "Status RGB LED + battery/charger sense"),
    (30, 205, "REMOTE PORT (J1): USB host, 5V from boost via current-limited switch"),
    (190, 190, "5 V boost (MT3608) + TPS2553 switch (520 mA)"),
    (65, 250, "USB data switch (U8): J2 plugged into a computer -> ESP on J2, else ESP on J1"),
    (30, 135, "CHARGE PORT (J2): charge only, 5.1k Rd on CC"),
    (195, 130, "TP4056 charger (255 mA)"),
    (330, 110, "Battery J3 + DW01A/FS8205A protection"),
]


def build():
    syms = {}
    for ref, p in design.PARTS.items():
        syms[p["sym"]] = syms.get(p["sym"]) or lib_symbol(p["sym"])
    flag = lib_symbol("power:PWR_FLAG")

    out = []
    out.append("(kicad_sch\n\t(version 20250114)\n\t(generator \"dji-gen\")\n\t(generator_version \"1\")")
    out.append(f"\t(uuid \"{ROOT}\")\n\t(paper \"A3\")\n\t(lib_symbols")
    seen = set()
    for libid, s in list(syms.items()) + [("power:PWR_FLAG", flag)]:
        if libid in seen:
            continue
        seen.add(libid)
        out.append(s.to_sexpr(indent=2, newline=False).rstrip("\n"))
    out.append("\t)")

    for x, y, text in TEXTS:
        out.append(f'\t(text {sexp_str(text)}\n\t\t(exclude_from_sim no)\n\t\t(at {x} {y} 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 2.54 2.54)\n\t\t\t\t(bold yes)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "{uid("text", text)}")\n\t)')

    labels, ncs, flagsout = [], [], []
    missing = [r for r in design.PARTS if r not in POS]
    if missing:
        sys.exit(f"no position for {missing}")

    def add_label(net, x, y, ang, key):
        just = "left" if ang in (0, 90) else "right"
        labels.append(
            f'\t(global_label {sexp_str(net)}\n\t\t(shape passive)\n\t\t(at {fmt(x)} {fmt(y)} {ang})\n\t\t(fields_autoplaced yes)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{uid("label", key)}")\n\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"\n\t\t\t(at {fmt(x)} {fmt(y)} 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n\t)')

    problems = []
    for ref, p in design.PARTS.items():
        sym = syms[p["sym"]]
        X, Y = (round(v / 2.54) * 2.54 for v in POS[ref])
        X, Y = round(X, 2), round(Y, 2)
        out.append(f'\t(symbol\n\t\t(lib_id {sexp_str(p["sym"])})\n\t\t(at {X} {Y} 0)\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom {"no" if ref.startswith(("H", "FID")) else "yes"})\n\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "{uid("sym", ref)}")')
        props = [("Reference", ref, False), ("Value", p["value"], False), ("Footprint", p["fp"], True), ("Datasheet", "~", True)]
        for k, v in p["props"].items():
            props.append((k.upper(), str(v), True))
        for i, (k, v, hide) in enumerate(props):
            dy = -4.0 if k == "Reference" else (4.0 if k == "Value" else 0)
            h = "\n\t\t\t\t(hide yes)" if hide else ""
            out.append(f'\t\t(property {sexp_str(k)} {sexp_str(v)}\n\t\t\t(at {X} {Y + dy} 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){h}\n\t\t\t)\n\t\t)')
        pins = pins_of(sym)
        for pin in pins:
            out.append(f'\t\t(pin {sexp_str(pin.number)}\n\t\t\t(uuid "{uid("pin", ref, pin.number)}")\n\t\t)')
        out.append(f'\t\t(instances\n\t\t\t(project {sexp_str(PROJECT)}\n\t\t\t\t(path "/{ROOT}"\n\t\t\t\t\t(reference {sexp_str(ref)})\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)')

        # connectivity labels / no-connects
        used_keys = set()
        for pin in pins:
            net = None
            for key in (pin.number, pin.name, f"{pin.name}#{pin.number}"):
                if key in p["pins"]:
                    net = p["pins"][key]
                    used_keys.add(key)
                    break
            px, py = X + pin.position.X, Y - pin.position.Y
            if net is None:
                if pin.electricalType == "no_connect" or p["pins"] or ref.startswith("TP"):
                    ncs.append(f'\t(no_connect\n\t\t(at {fmt(px)} {fmt(py)})\n\t\t(uuid "{uid("nc", ref, pin.number)}")\n\t)')
                continue
            add_label(net, px, py, label_angle(pin.position.angle or 0), f"{ref}.{pin.number}")
        for key in p["pins"]:
            if key not in used_keys:
                problems.append(f"{ref}: pin key {key!r} not found in {p['sym']}")

    # PWR_FLAGs: each in its own spot, label gives it the net
    fx = 30.48
    flagn = 0
    for net in design.PWR_FLAGS:
        fx += 15.24
        flagn += 1
        fpin = pins_of(flag)[0]
        out.append(f'\t(symbol\n\t\t(lib_id "power:PWR_FLAG")\n\t\t(at {fx} 284.48 0)\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom no)\n\t\t(on_board no)\n\t\t(dnp no)\n\t\t(uuid "{uid("flag", net)}")\n\t\t(property "Reference" "#FLG0{flagn}"\n\t\t\t(at {fx} 281 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n\t\t(property "Value" "PWR_FLAG"\n\t\t\t(at {fx} 281 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n\t\t(pin "1"\n\t\t\t(uuid "{uid("flagpin", net)}")\n\t\t)\n\t\t(instances\n\t\t\t(project {sexp_str(PROJECT)}\n\t\t\t\t(path "/{ROOT}"\n\t\t\t\t\t(reference "#FLG0{flagn}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)')
        add_label(net, fx + fpin.position.X, 284.48 - fpin.position.Y, 0, f"flag.{net}")

    out += labels + ncs
    out.append(f'\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)')
    if problems:
        print("\n".join(problems))
        sys.exit("pin mapping problems")
    path = os.path.join(HERE, f"{PROJECT}.kicad_sch")
    open(path, "w").write("\n".join(out) + "\n")

    # minimal project + symbol library table so KiCad finds the custom symbols
    open(os.path.join(HERE, "sym-lib-table"), "w").write(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "dji_parts")(type "KiCad")(uri "${KIPRJMOD}/lib/dji_parts.kicad_sym")(options "")(descr "dji-fcc custom symbols"))\n)\n')
    import json
    pm = {ref: [(pin.number, pin.name) for pin in pins_of(syms[pt["sym"]])] for ref, pt in design.PARTS.items()}
    json.dump(pm, open(os.path.join(HERE, "pinmap.json"), "w"))
    print("wrote", path)


if __name__ == "__main__":
    build()
