# Tool locations; override any of these in the environment before running the scripts.
export KICAD_APP=${KICAD_APP:-$HOME/Applications/KiCad/KiCad.app}
export JAVA=${JAVA:-/opt/homebrew/opt/openjdk/bin/java}
export FREEROUTING=${FREEROUTING:-$HOME/tools/freerouting/freerouting-2.5.0.jar}
export KCLI=$KICAD_APP/Contents/MacOS/kicad-cli
export WORK=${WORK:-${TMPDIR:-/tmp}/dji-fcc}   # scratch files (DSN/SES, reports)
mkdir -p "$WORK"
