import sys, os, pcbnew
FP = os.path.join(os.environ.get("KICAD_APP", os.path.expanduser("~/Applications/KiCad/KiCad.app")), "Contents/SharedSupport/footprints")
for arg in sys.argv[1:]:
    lib, name = arg.split(":")
    fp = pcbnew.FootprintLoad(f"{FP}/{lib}.pretty", name)
    bb = fp.GetBoundingBox(False)  # no text
    mm = pcbnew.ToMM
    cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox() if fp.GetCourtyard(pcbnew.F_CrtYd).OutlineCount() else None
    print(f"{arg}: bbox x[{mm(bb.GetLeft()):.2f},{mm(bb.GetRight()):.2f}] y[{mm(bb.GetTop()):.2f},{mm(bb.GetBottom()):.2f}]",
          f"crtyd x[{mm(cy.GetLeft()):.2f},{mm(cy.GetRight()):.2f}] y[{mm(cy.GetTop()):.2f},{mm(cy.GetBottom()):.2f}]" if cy else "")
    if "-v" in os.environ.get("FPV",""):
        for p in fp.Pads():
            print("   pad", p.GetNumber(), f"({mm(p.GetX()-fp.GetX()):.2f},{mm(p.GetY()-fp.GetY()):.2f})", f"{mm(p.GetSizeX()):.2f}x{mm(p.GetSizeY()):.2f}", p.GetAttribute())
