"""Print pins of KiCad library symbols: libinfo.py Lib:Symbol [Lib:Symbol...]  |  libinfo.py --find pattern"""
import sys, glob, os, re
from kiutils.symbol import SymbolLib
SYM = os.path.join(os.environ.get("KICAD_APP", os.path.expanduser("~/Applications/KiCad/KiCad.app")), "Contents/SharedSupport/symbols")
if sys.argv[1] == "--find":
    pat = re.compile(sys.argv[2], re.I)
    for f in sorted(glob.glob(SYM + "/*.kicad_sym")):
        for s in SymbolLib.from_file(f).symbols:
            if pat.search(s.entryName):
                fp = next((p.value for p in s.properties if p.key == "Footprint"), "")
                print(f"{os.path.basename(f)[:-10]}:{s.entryName}   fp={fp}")
else:
    for arg in sys.argv[1:]:
        lib, name = arg.split(":")
        L = SymbolLib.from_file(f"{SYM}/{lib}.kicad_sym")
        s = next(x for x in L.symbols if x.entryName == name)
        if s.extends:
            s = next(x for x in L.symbols if x.entryName == s.extends)
        print(f"== {arg}")
        for u in s.units:
            for p in u.pins:
                print(f"  {p.number:>4} {p.name:<14} {p.electricalType}  at({p.position.X},{p.position.Y},{p.position.angle})")
