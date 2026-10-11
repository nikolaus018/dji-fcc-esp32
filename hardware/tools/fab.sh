#!/bin/bash
# fab.sh : build everything a fab house / reviewer needs into hardware/fab and hardware/docs
set -e
cd "$(dirname "$0")/.."
source tools/env.sh
export KICAD10_3DMODEL_DIR=$HOME/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels
mkdir -p fab/gerber docs
rm -f fab/gerber/* fab/dji-fcc-gerbers.zip
$KCLI pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts -o fab/gerber/ dji-fcc.kicad_pcb >/dev/null
$KCLI pcb export drill --format excellon --drill-origin absolute --excellon-units mm --excellon-separate-th --generate-map --map-format gerberx2 -o fab/gerber/ dji-fcc.kicad_pcb >/dev/null
(cd fab/gerber && zip -q ../dji-fcc-gerbers.zip *)
# placement file in JLCPCB column layout
$KCLI pcb export pos --format csv --units mm --side front -o /private/tmp/claude-501/pos.csv dji-fcc.kicad_pcb >/dev/null
python3 - <<'PY'
import csv
rows = list(csv.DictReader(open('/private/tmp/claude-501/pos.csv')))
with open('fab/cpl_jlcpcb.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Val', 'Package', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
    for r in rows:
        if r['Ref'].startswith(('H', 'FID', 'TP')):
            continue
        w.writerow([r['Ref'], r['Val'], r['Package'], r['PosX'] + 'mm', r['PosY'] + 'mm', r['Rot'], 'Top'])
print('CPL rows:', len(rows))
PY
python3 bom.py
$KCLI sch export pdf -o docs/schematic.pdf dji-fcc.kicad_sch >/dev/null 2>&1
$KCLI pcb export pdf --layers F.Cu,F.SilkS,Edge.Cuts -o docs/pcb_top.pdf dji-fcc.kicad_pcb >/dev/null 2>&1
$KCLI pcb export pdf --layers B.Cu,B.SilkS,Edge.Cuts --mirror -o docs/pcb_bottom.pdf dji-fcc.kicad_pcb >/dev/null 2>&1
$KCLI pcb render --side top --quality basic -w 2400 -h 1200 --background opaque -o docs/render_top.png dji-fcc.kicad_pcb >/dev/null 2>&1
$KCLI pcb render --side bottom --quality basic -w 2400 -h 1200 --background opaque -o docs/render_bottom.png dji-fcc.kicad_pcb >/dev/null 2>&1
$KCLI pcb export step --subst-models --force -o fab/dji-fcc.step dji-fcc.kicad_pcb >/dev/null 2>&1 || echo "step export failed"
ls -la fab docs | grep -v "^total"
