#!/bin/bash
cd "$(dirname "$0")/.."
source tools/env.sh
$KCLI pcb drc --severity-all --format json --all-track-errors --units mm -o "$WORK/drc.json" dji-fcc.kicad_pcb >/dev/null 2>&1 || true
python3 - <<'PY'
import json, collections, os
d = json.load(open(os.environ['WORK'] + '/drc.json'))
c = collections.Counter()
for sec in ('violations', 'unconnected_items', 'schematic_parity'):
    for v in d.get(sec, []):
        c[(sec, v['severity'], v['type'])] += 1
for k, n in sorted(c.items()):
    print(n, *k)
print("--- samples")
seen = collections.Counter()
for sec in ('violations', 'unconnected_items'):
    for v in d.get(sec, []):
        if seen[v['type']] < int(__import__('os').environ.get('SAMPLES', '3')):
            seen[v['type']] += 1
            it = v['items']
            pos = [f"({i['pos']['x']:.1f},{i['pos']['y']:.1f})" for i in it]
            print(v['type'], '|', v['description'][:90], '|', ' ; '.join(i['description'][:60] for i in it), pos)
PY
