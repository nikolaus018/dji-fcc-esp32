"""Generate dji-fcc.kicad_pcb (placement only) from design.py, then export a Specctra DSN for routing.

Run with KiCad's python:  tools/kpy gen_pcb.py
Pipeline: gen_pcb.py -> (freerouting) -> route.py -> fill zones / DRC / fab outputs.
"""
import json
import os
import sys

import pcbnew
from pcbnew import FromMM as mm, VECTOR2I

import design

HERE = os.path.dirname(os.path.abspath(__file__))
FP = os.path.join(os.environ.get("KICAD_APP", os.path.expanduser("~/Applications/KiCad/KiCad.app")), "Contents/SharedSupport/footprints")
PCB = os.path.join(HERE, "dji-fcc.kicad_pcb")

W, H = 80.0, 34.0          # board size, mm
RAD = 2.0                  # corner radius
MX, MY = 38.0, 10.0        # ESP module origin (antenna end flush with the top edge)

# ref -> (x, y, rotation)
PLACE = {
    "U1": (MX, MY, 0),
    # J1 (remote) on the left edge facing -X, J2 (charge) on the right edge facing +X
    "J1": (4.07, 17.0, 270), "J2": (W - 4.07, 17.0, 90),
    "H1": (W - 3.0, H - 3.0, 0), "H2": (3.0, H - 3.0, 0),
    "FID1": (2.8, 2.8, 0), "FID2": (77.5, 8.0, 0), "FID3": (78.0, 25.0, 0),
}
PLACE.update(json.load(open(os.path.join(HERE, "placement.json"))) if os.path.exists(os.path.join(HERE, "placement.json")) else {})


def write_project():
    pro = {
        "meta": {"filename": "dji-fcc.kicad_pro", "version": 3},
        "board": {"design_settings": {
            "defaults": {"copper_line_width": 0.2, "copper_text_size_h": 1.0, "copper_text_size_v": 1.0},
            "rules": {"min_clearance": 0.15, "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25,
                      "min_hole_to_hole": 0.25, "min_through_hole_diameter": 0.3, "min_track_width": 0.1,
                      "min_via_annular_width": 0.13, "min_via_diameter": 0.5, "min_via_annular_width": 0.13, "min_connection_width": 0.2,
                      "min_text_height": 0.8, "min_text_thickness": 0.12, "min_silk_clearance": 0.0,
                      "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1, "solder_mask_to_copper_clearance": 0.0,
                      "min_resolved_spokes": 1},
        }},
        "net_settings": {
            "classes": [
                {"name": "Default", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
                 "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3,
                 "microvia_drill": 0.1, "priority": 2147483647, "pcb_color": "rgba(0, 0, 0, 0.000)",
                 "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6, "bus_width": 12, "line_style": 0},
                {"name": "Power", "clearance": 0.15, "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4,
                 "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3,
                 "microvia_drill": 0.1, "priority": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
                 "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6, "bus_width": 12, "line_style": 0},
                {"name": "Mid", "clearance": 0.15, "track_width": 0.35, "via_diameter": 0.6, "via_drill": 0.3,
                 "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "microvia_diameter": 0.3,
                 "microvia_drill": 0.1, "priority": 1, "pcb_color": "rgba(0, 0, 0, 0.000)",
                 "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6, "bus_width": 12, "line_style": 0},
            ],
            "netclass_patterns": (
                [{"netclass": "Power", "pattern": n} for n in
                 ["VBAT", "VBOOST", "VBUS_REM", "VBUS_CHG", "VSW", "BNEG", "DW_MID", "GND_PWR"]]
                + [{"netclass": "Mid", "pattern": n} for n in ["+3V3", "CHG_A", "DONE_A"]]),
        },
    }
    json.dump(pro, open(os.path.join(HERE, "dji-fcc.kicad_pro"), "w"), indent=2)


def outline(board):
    """Rounded-rectangle board edge on Edge.Cuts."""
    pts = [(RAD, 0, W - RAD, 0), (W, RAD, W, H - RAD), (W - RAD, H, RAD, H), (0, H - RAD, 0, RAD)]
    for x1, y1, x2, y2 in pts:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        s.SetStart(VECTOR2I(mm(x1), mm(y1)))
        s.SetEnd(VECTOR2I(mm(x2), mm(y2)))
        board.Add(s)
    corners = [(RAD, RAD, 180, 270), (W - RAD, RAD, 270, 360), (W - RAD, H - RAD, 0, 90), (RAD, H - RAD, 90, 180)]
    import math
    for cx, cy, a0, a1 in corners:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        am = math.radians((a0 + a1) / 2)
        s.SetArcGeometry(
            VECTOR2I(mm(cx + RAD * math.cos(math.radians(a0))), mm(cy + RAD * math.sin(math.radians(a0)))),
            VECTOR2I(mm(cx + RAD * math.cos(am)), mm(cy + RAD * math.sin(am))),
            VECTOR2I(mm(cx + RAD * math.cos(math.radians(a1))), mm(cy + RAD * math.sin(math.radians(a1)))))
        board.Add(s)


def pad_net_map(ref, part, fp, symbol_pins):
    """pad number -> net, using the symbol's pin names/numbers (same resolution rule as gen_sch)."""
    m = {}
    for num, name in symbol_pins:
        for key in (num, name, f"{name}#{num}"):
            if key in part["pins"]:
                m[num] = part["pins"][key]
                break
    return m


def build():
    write_project()
    if os.path.exists(PCB):
        os.remove(PCB)
    board = pcbnew.NewBoard(PCB)
    ds = board.GetDesignSettings()
    board.SetCopperLayerCount(2)

    # symbol pin lists (num, name) from the exported schematic netlist-independent source: kiutils via gen_sch
    pinmap = json.load(open(os.path.join(HERE, "pinmap.json")))
    nets = {}

    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            nets[name] = n
        return nets[name]

    missing = [r for r in design.PARTS if r not in PLACE]
    if missing:
        sys.exit(f"no placement for {missing}")

    for ref, p in design.PARTS.items():
        lib, name = p["fp"].split(":")
        fp = pcbnew.FootprintLoad(f"{FP}/{lib}.pretty", name)
        if fp is None:
            sys.exit(f"footprint not found {p['fp']}")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        import uuid as _u
        root = str(_u.uuid5(_u.NAMESPACE_DNS, "dji-fcc-esp32-root"))
        symuuid = str(_u.uuid5(_u.NAMESPACE_DNS, "dji-fcc/sym/" + ref))
        fp.SetPath(pcbnew.KIID_PATH(f"/{root}/{symuuid}"))
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        x, y, rot = PLACE[ref]
        fp.SetPosition(VECTOR2I(mm(x), mm(y)))
        fp.SetOrientationDegrees(rot)
        pmap = pad_net_map(ref, p, fp, pinmap[ref])
        names = dict(pinmap[ref])
        for pad in fp.Pads():
            n = pmap.get(pad.GetNumber())
            if n:
                pad.SetNet(net(n))
            elif pad.GetNumber() in names and p["pins"] or (pad.GetNumber() in names and ref.startswith("J")):
                # named after KiCad's own convention so schematic parity checks line up
                pad.SetNet(net(f"unconnected-({ref}-{names[pad.GetNumber()]}-Pad{pad.GetNumber()})"))
        for k, v in p["props"].items():
            fp.SetField(k.upper(), str(v)) if hasattr(fp, "SetField") else None
        if ref.startswith(("H", "FID")):
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM)
        board.Add(fp)

    outline(board)
    import route
    gnd = board.FindNet("GND")
    route.add_pour(board, pcbnew.B_Cu, gnd)   # router sees a ground plane on the bottom layer only
    board.Save(PCB)
    print("placement written:", PCB)


if __name__ == "__main__":
    build()
