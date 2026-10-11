import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
ok = pcbnew.ExportSpecctraDSN(b, sys.argv[2])
print("dsn", ok)
