"""Import the Freerouting session into the board, add the ground pours, tidy silkscreen, save.

Run with KiCad's python:  tools/kpy route.py <session.ses>
"""
import os
import sys

import pcbnew
from pcbnew import FromMM as mm, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "dji-fcc.kicad_pcb")
W, H = 80.0, 34.0
INSET = 0.3


def add_pour(board, layer, net):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.25))
    z.SetThermalReliefSpokeWidth(mm(0.35))
    z.SetLocalClearance(mm(0.2))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in [(INSET, INSET), (W - INSET, INSET), (W - INSET, H - INSET), (INSET, H - INSET)]:
        ol.Append(mm(x), mm(y))
    board.Add(z)


def silk_labels(board):
    for t in [d for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT"]:
        board.Remove(t)
    for text, x, y, size in [("dji-fcc-esp32 rA", 14.0, 32.6, 0.9), ("J1 REMOTE", 4.0, 22.8, 0.8),
                             ("J2 CHARGE", 64.5, 31.3, 0.8), ("+", 35.0, 33.2, 1.0), ("-", 37.0, 33.2, 1.0), ("BAT", 31.6, 33.2, 0.8)]:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.F_SilkS)
        t.SetPosition(VECTOR2I(mm(x), mm(y)))
        t.SetTextSize(VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(0.15))
        board.Add(t)


def stitch(board, filler, pitch=4.0, ring=0.55):
    """Add GND vias on a grid wherever both pours are free of other copper, linking top and bottom pours."""
    import math
    gnd = board.FindNet("GND")
    zf = next(z for z in board.Zones() if z.GetLayer() == pcbnew.F_Cu and not z.GetIsRuleArea())
    zb = next(z for z in board.Zones() if z.GetLayer() == pcbnew.B_Cu and not z.GetIsRuleArea())
    added = 0
    y = 2.0
    while y < H - 1.5:
        x = 2.0
        while x < W - 1.5:
            ok = True
            for dx, dy in [(0, 0)] + [(ring * math.cos(a * math.pi / 4), ring * math.sin(a * math.pi / 4)) for a in range(8)]:
                p = VECTOR2I(mm(x + dx), mm(y + dy))
                if not (zf.HitTestFilledArea(pcbnew.F_Cu, p) and zb.HitTestFilledArea(pcbnew.B_Cu, p)):
                    ok = False
                    break
            if ok:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(VECTOR2I(mm(x), mm(y)))
                v.SetWidth(mm(0.6))
                v.SetDrill(mm(0.3))
                v.SetNet(gnd)
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                board.Add(v)
                added += 1
            x += pitch
        y += pitch
    filler.Fill(board.Zones())
    # Every pour fragment (both layers) must end up electrically joined to the main ground plane.
    # Build a union-find over fill outlines linked by GND vias / through-hole pads, then add vias until
    # a single cluster remains.
    ring = 0.5
    LAYERS = [(pcbnew.F_Cu, zf), (pcbnew.B_Cu, zb)]
    KEEP = []

    def gather():
        outs = []  # (layer, zone, outline)
        for layer, zone in LAYERS:
            fp = zone.GetFilledPolysList(layer)
            KEEP.append(fp)   # outlines point into this set; it must outlive them
            for i in range(fp.OutlineCount()):
                outs.append((layer, zone, fp.Outline(i)))
        return outs

    def clear_ring(xx, yy):
        for layer, zone in LAYERS:
            for a in range(8):
                q = VECTOR2I(xx + int(mm(ring) * math.cos(a * math.pi / 4)), yy + int(mm(ring) * math.sin(a * math.pi / 4)))
                if not zone.HitTestFilledArea(layer, q):
                    return False
            if not zone.HitTestFilledArea(layer, VECTOR2I(xx, yy)):
                return False
        return True

    for _ in range(12):
        outs = gather()
        parent = list(range(len(outs)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        links = [t.GetPosition() for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNet().GetNetname() == "GND"]
        for f in board.GetFootprints():
            for pad in f.Pads():
                if pad.GetNetname() == "GND" and pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    links.append(pad.GetPosition())
        for p in links:
            hit = [i for i, (l, z, o) in enumerate(outs) if o.PointInside(p)]
            for h in hit[1:]:
                parent[find(h)] = find(hit[0])

        def area(o):
            bb = o.BBox()
            return pcbnew.ToMM(bb.GetWidth()) * pcbnew.ToMM(bb.GetHeight())

        main = find(max(range(len(outs)), key=lambda i: area(outs[i][2])))
        loose = [i for i in range(len(outs)) if find(i) != main]
        if not loose:
            break
        extra = 0
        for i in loose:
            if find(i) == main:
                continue
            layer, zone, ol = outs[i]
            bb = ol.BBox()
            placed = False
            yy = bb.GetTop()
            while yy <= bb.GetBottom() and not placed:
                xx = bb.GetLeft()
                while xx <= bb.GetRight() and not placed:
                    p = VECTOR2I(xx, yy)
                    if ol.PointInside(p):
                        other = [j for j, (l, z, o) in enumerate(outs) if l != layer and o.PointInside(p)]
                        if other and find(other[0]) == main and clear_ring(xx, yy):
                            v = pcbnew.PCB_VIA(board)
                            v.SetPosition(p)
                            v.SetWidth(mm(0.6))
                            v.SetDrill(mm(0.3))
                            v.SetNet(gnd)
                            v.SetViaType(pcbnew.VIATYPE_THROUGH)
                            board.Add(v)
                            parent[find(i)] = main
                            placed = True
                            extra += 1
                    xx += mm(0.15)
                yy += mm(0.15)
        added += extra
        filler.Fill(board.Zones())
        if not extra:
            for i in loose:
                bb = outs[i][2].BBox()
                print(f"  UNRESOLVED {'F' if outs[i][0] == pcbnew.F_Cu else 'B'}.Cu fragment x[{pcbnew.ToMM(bb.GetLeft()):.1f},{pcbnew.ToMM(bb.GetRight()):.1f}] y[{pcbnew.ToMM(bb.GetTop()):.1f},{pcbnew.ToMM(bb.GetBottom()):.1f}]")
            break
    print("stitching vias added:", added)


def main():
    board = pcbnew.LoadBoard(PCB)
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        ok = pcbnew.ImportSpecctraSES(board, sys.argv[1])
        print("ses import:", ok)

    # top-side pour is added after routing so every GND pad is tied to the bottom plane by a real via
    if not any(z.GetLayer() == pcbnew.F_Cu and not z.GetIsRuleArea() for z in board.Zones()):
        add_pour(board, pcbnew.F_Cu, board.FindNet("GND"))
    # the autorouter sometimes mixes the 0.6 via size with the 0.4 drill of the power class
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            v = pcbnew.Cast_to_PCB_VIA(t)
            # imported vias carry no explicit drill; pin it to the size they were routed with
            v.SetDrill(mm(0.3 if pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)) < 0.7 else 0.4))
    for fp in board.GetFootprints():
        if fp.GetReference().startswith(("R", "C", "TP", "FID", "H", "U1")) and fp.GetReference() != "U10":
            for g in fp.GraphicalItems():
                if g.GetLayer() == pcbnew.F_SilkS:
                    g.SetLayer(pcbnew.F_Fab)
        fp.Value().SetVisible(False)
        for fld in fp.GetFields():
            if fld.GetName() not in ("Reference", "Value"):
                fld.SetVisible(False)
        ref = fp.Reference()
        ref.SetLayer(pcbnew.F_Fab)
        ref.SetTextSize(VECTOR2I(mm(0.8), mm(0.8)))
        ref.SetTextThickness(mm(0.12))
    silk_labels(board)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    stitch(board, filler)
    board.Save(PCB)
    tracks = sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T)
    vias = sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T)
    print(f"saved: {tracks} track segments, {vias} vias")


if __name__ == "__main__":
    main()
