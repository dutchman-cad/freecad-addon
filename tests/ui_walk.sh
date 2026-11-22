#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Run on a desktop-capable worker. All application state belongs to this walk.
set -euo pipefail
root=$PWD
# Optional: a directory with extra tools (Xvfb, xdotool, ImageMagick) laid out as usr/.
if [ -n "${UI_WALK_TOOLS:-}" ]; then
    export PATH="$UI_WALK_TOOLS/bin:$PATH"
    export LD_LIBRARY_PATH="$UI_WALK_TOOLS/lib64:$UI_WALK_TOOLS/lib:${LD_LIBRARY_PATH:-}"
fi
: "${DUTCHMAN_FIXTURES:?set DUTCHMAN_FIXTURES to a directory containing synthetic_cube.ipt, solidworks_cube.sldprt and README.md}"
round=${WALK_ROUND:-$(python3 - <<'ROUND'
from pathlib import Path
rounds = [int(p.name.removeprefix('round-')) for p in Path('walk').glob('round-*')
          if p.is_dir() and p.name.removeprefix('round-').isdigit()]
print(f'{max(rounds, default=0) + 1:02d}')
ROUND
)}
export WALK_DIR="$root/walk/round-$round"
mkdir -p "$WALK_DIR/shots" "$root/walk/fixtures"
rm -f "$WALK_DIR/finished" "$WALK_DIR/shot-request" "$WALK_DIR/action-request" "$WALK_DIR/error.txt"
python3 -m unittest discover -s tests > "$WALK_DIR/unit-tests.log" 2>&1
fixtures=$DUTCHMAN_FIXTURES
for f in synthetic_cube.ipt solidworks_cube.sldprt README.md; do
    cp "$fixtures/$f" "$root/walk/fixtures/$f"
done
cp tests/fixtures/generated_unit_cube.f3d "$root/walk/fixtures/"
# This public archive is smaller than 30 KB, so use half its bytes to ensure
# the failure case really is truncated rather than an unchanged valid archive.
python3 - <<'TRUNCATE'
from pathlib import Path
source = Path('tests/fixtures/generated_unit_cube.f3d').read_bytes()
cut = min(30000, max(1, len(source) // 2))
Path('walk/fixtures/truncated.f3d').write_bytes(source[:cut])
Path('walk/fixtures/truncation.txt').write_text(
    f'Original: {len(source)} bytes; truncated prefix: {cut} bytes. '
    'The public fixture is smaller than 30000 bytes.\n')
TRUNCATE
private=$(mktemp -d /tmp/dutchman-ui-XXXXXX)
chmod 700 "$private"
trap 'kill "${screen_pid:-}" "${xvfb_pid:-}" 2>/dev/null || true; rm -rf "$private"' EXIT
mkdir -p "$private"/{home,config,data,cache,runtime,freecad,stubs}
chmod 700 "$private/runtime"
cp -r "$root/walk/fixtures" "$private/fixtures"
export WALK_PRIVATE="$private"
cat > "$private/stubs/open-stub" <<'STUB'
#!/bin/sh
printf '%s\n' "$0 $*" >> "$WALK_DIR/opened.log"
STUB
chmod +x "$private/stubs/open-stub"
for tool in xdg-open x-www-browser sensible-browser firefox chromium chromium-browser google-chrome gio; do
    ln -s open-stub "$private/stubs/$tool"
done
Xvfb -displayfd 3 -screen 0 1440x1000x24 -nolisten tcp 3> "$private/display" > "$WALK_DIR/xvfb.log" 2>&1 &
xvfb_pid=$!
sleep 2
export DISPLAY=":"$(cat "$private/display")
# Capture the actual display, including dialogs. The macro requests numbered shots.
(
 while [ ! -e "$WALK_DIR/finished" ]; do
    if [ -e "$WALK_DIR/shot-request" ]; then
        shot=$(cat "$WALK_DIR/shot-request")
        import -window root "$WALK_DIR/shots/$shot.png"
        rm -f "$WALK_DIR/shot-request"
    fi
    if [ -e "$WALK_DIR/action-request" ]; then
        read -r op first second < "$WALK_DIR/action-request"
        case "$op" in
            click) xdotool mousemove --sync "$first" "$second" click 1 ;;
            key) xdotool key --clearmodifiers "$first" ;;
            focus) xdotool windowfocus --sync "$first" ;;
            *) exit 2 ;;
        esac
        rm -f "$WALK_DIR/action-request"
    fi
    sleep 0.3
 done
) &
screen_pid=$!
export DUTCHMAN_BIN="${DUTCHMAN_BIN:-dutchman}"
"$DUTCHMAN_BIN" --version > "$WALK_DIR/binary-version.txt"
export QTWEBENGINE_DISABLE_SANDBOX=1
# Flatpak itself uses its registered installation; only the app receives private HOME/XDG.
set +e
timeout 12m dbus-run-session -- flatpak run --no-documents-portal --filesystem=host --filesystem="$private" \
 --env=HOME="$private/home" --env=XDG_CONFIG_HOME="$private/config" \
 --env=XDG_DATA_HOME="$private/data" --env=XDG_CACHE_HOME="$private/cache" \
 --env=XDG_RUNTIME_DIR="$private/runtime" \
 --env=FREECAD_USER_HOME="$private/freecad" \
 --env=BROWSER="$private/stubs/xdg-open" \
 --env=PATH="$private/stubs:/app/bin:/usr/bin" \
 --env=WALK_DIR="$WALK_DIR" --env=WALK_PRIVATE="$private" \
 --env=WALK_ROOT="$root" --env=DUTCHMAN_BIN="$DUTCHMAN_BIN" \
 org.freecad.FreeCAD "$root/tests/ui_walk.FCMacro" > "$WALK_DIR/freecad.log" 2>&1
result=$?
set -e
if [ -d "$private/converted" ]; then
    cp -r "$private/converted" "$WALK_DIR/converted"
fi
test "$result" = 0
test -e "$WALK_DIR/finished"
