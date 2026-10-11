import sys, collections, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
st = collections.defaultdict(lambda: [1e9, 0.0, 0, 0])
for t in b.GetTracks():
    n = t.GetNetname()
    if t.Type() == pcbnew.PCB_TRACE_T:
        w = pcbnew.ToMM(t.GetWidth())
        st[n][0] = min(st[n][0], w); st[n][1] += pcbnew.ToMM(t.GetLength()); st[n][2] += 1
    elif t.Type() == pcbnew.PCB_VIA_T:
        st[n][3] += 1
for n, (w, l, s, v) in sorted(st.items(), key=lambda kv: -kv[1][1]):
    if n and n != "GND":
        print(f"{n:14s} minW {w:4.2f}  len {l:6.1f} mm  segs {s:3d}  vias {v}")
