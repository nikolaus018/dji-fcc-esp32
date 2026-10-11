"""Write fab/bom_jlcpcb.csv (JLCPCB BOM format) and fab/bom_full.csv from design.py."""
import csv, os, collections
import design
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(f"{HERE}/fab", exist_ok=True)

def lcsc(ref, p):
    if ref in design.LCSC_REF:
        return design.LCSC_REF[ref]
    if p["sym"] == "Device:R":
        return design.LCSC_R.get(p["value"], "")
    if p["sym"] == "Device:C":
        size = "0805" if "0805" in p["fp"] else "0603"
        return design.LCSC_C.get((p["value"], size), "")
    return ""

rows = collections.defaultdict(list)
for ref, p in design.PARTS.items():
    if ref.startswith(("H", "FID", "TP")):
        continue
    # J1/J2 are the same part with different schematic values; JLCPCB wants one line per part number
    value = "USB-C" if ref in ("J1", "J2") else p["value"]
    rows[(value, p["fp"].split(":")[1], lcsc(ref, p), p["props"].get("mpn", ""))].append(ref)

def key(r):
    return min(int(''.join(c for c in x if c.isdigit()) or 0) for x in r[1])
items = sorted(rows.items(), key=lambda kv: (kv[1][0][0], key((None, kv[1]))))
with open(f"{HERE}/fab/bom_jlcpcb.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, fp, c, mpn), refs in items:
        w.writerow([val, ",".join(sorted(refs, key=lambda x: (x[0], int(''.join(ch for ch in x if ch.isdigit()) or 0)))), fp, c])
with open(f"{HERE}/fab/bom_full.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Qty", "Value", "Designators", "Footprint", "MPN", "LCSC", "Missing LCSC?"])
    for (val, fp, c, mpn), refs in items:
        w.writerow([len(refs), val, " ".join(sorted(refs, key=lambda x: (x[0], int(''.join(ch for ch in x if ch.isdigit()) or 0)))), fp, mpn, c, "" if c else "YES"])
miss = [r for (v, f_, c, m), rs in items if not c for r in rs]
print("BOM lines:", len(items), "parts:", sum(len(r) for _, r in items), "missing LCSC:", miss)
