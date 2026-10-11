#!/bin/bash
# finish.sh: rebuild board from placement + last saved routing session, then DRC
SKIP_ROUTE=1 "$(dirname "$0")/route.sh"
