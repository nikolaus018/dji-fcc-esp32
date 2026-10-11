#!/bin/bash
# route.sh : placement -> pours -> DSN -> Freerouting -> import SES -> fill -> DRC summary
set -e
cd "$(dirname "$0")/.."
source tools/env.sh
tools/kpy gen_pcb.py 2>&1 | grep -v assert
tools/kpy tools/dsn_export.py dji-fcc.kicad_pcb /private/tmp/claude-501/dji.dsn 2>&1 | grep -v assert
if [ -z "$SKIP_ROUTE" ]; then
for attempt in 1 2 3 4 5 6 7 8; do
  rm -f /private/tmp/claude-501/dji.ses
  $JAVA -Djava.awt.headless=true -jar $FREEROUTING -de /private/tmp/claude-501/dji.dsn -do /private/tmp/claude-501/dji.ses -mp ${PASSES:-60} > /private/tmp/claude-501/fr.log 2>&1
  if grep -q "Auto-routing stage completed.*(0 unrouted" /private/tmp/claude-501/fr.log; then break; fi
  echo "attempt $attempt left unrouted connections, retrying"
done
grep -E "Auto-routing stage completed|Optimization stage completed" /private/tmp/claude-501/fr.log | tail -2 | cut -c1-260
fi
grep -E "Auto-routing stage completed|Optimization stage completed|final score" /private/tmp/claude-501/fr.log | tail -2 | cut -c1-260
tools/kpy route.py /private/tmp/claude-501/dji.ses 2>&1 | grep -v assert
tools/drc.sh
