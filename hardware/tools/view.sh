#!/bin/bash
# view.sh [layers] -> $WORK/pcb.png  (PDF export of the board, rendered at 20 px/mm)
cd "$(dirname "$0")/.."
source tools/env.sh
K=$KCLI
LAYERS=${1:-"F.Cu,B.Cu,F.SilkS,Edge.Cuts,F.CrtYd"}
$K pcb export pdf --layers "$LAYERS" -o $WORK/pcb.pdf dji-fcc.kicad_pcb >/dev/null 2>&1
uv run --quiet --with pypdfium2 --with pillow python -I - <<PY
import pypdfium2 as p
d=p.PdfDocument('$WORK/pcb.pdf')
im=d[0].render(scale=${SCALE:-6}).to_pil()
bb=im.convert('L').point(lambda v:0 if v>250 else 255).getbbox()
if bb: im=im.crop((max(bb[0]-10,0),max(bb[1]-10,0),bb[2]+10,bb[3]+10))
im.save('$WORK/pcb.png'); print(im.size)
PY
