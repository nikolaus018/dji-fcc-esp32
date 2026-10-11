"""Compare the netlist exported from the schematic with design.py (independent check of the generator)."""
import sys, re, xml.etree.ElementTree as ET
sys.path.insert(0, "..")
import design
root = ET.parse(sys.argv[1]).getroot()
got = {}
for net in root.find("nets"):
    name = net.get("name").lstrip("/")
    for node in net:
        got.setdefault(name, set()).add((node.get("ref"), node.get("pin")))
# expected: from design, resolving pin names -> numbers via the exported component pin lists
pinmap = {}
for comp in root.find("libparts"):
    for pin in (comp.find("pins") if comp.find("pins") is not None else []):
        pinmap.setdefault((comp.get("lib"), comp.get("part")), []).append((pin.get("num"), pin.get("name")))
exp = {}
comps = {c.get("ref"): c for c in root.find("components")}
for ref, p in design.PARTS.items():
    c = comps[ref]
    ls = c.find("libsource")
    pins = pinmap.get((ls.get("lib"), ls.get("part")), [])
    for num, name in pins:
        for key in (num, name, f"{name}#{num}"):
            if key in p["pins"]:
                exp.setdefault(p["pins"][key], set()).add((ref, num))
                break
bad = 0
for net in sorted(set(exp) | set(got)):
    e, g = exp.get(net, set()), got.get(net, set())
    if net.startswith("unconnected") or net.startswith("Net-"):
        continue
    if e != g:
        bad += 1
        print("MISMATCH", net, "missing:", sorted(e - g), "extra:", sorted(g - e))
print("nets checked:", len(exp), "mismatches:", bad)
