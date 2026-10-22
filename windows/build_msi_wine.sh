#!/bin/bash

# Build a Windows MSI installer on Linux using Wine.

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_VERSION=3.14.8
DOSBOX_VERSION=0.83.0
DOSBOX_SHA256=725b915e325a6d410ce30a10989fd492fdad07f6611fff40ff77f160478810f4

export WINEDEBUG=-all
prefix="${WINEPREFIX:-$HOME/.wine}"
pydir="Python$(echo "${PYTHON_VERSION%.*}" | tr -d .)"
python="$prefix/drive_c/$pydir/python.exe"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

if [ ! -f "$python" ]; then
    echo "Installing Python $PYTHON_VERSION in $prefix ..."
    wineboot -i >/dev/null 2>&1
    installer="python-$PYTHON_VERSION-amd64.exe"
    curl -sSfL -o "$work/$installer" \
        "https://www.python.org/ftp/python/$PYTHON_VERSION/$installer"
    wine "$work/$installer" /quiet InstallAllUsers=0 "TargetDir=C:\\$pydir" \
        Include_test=0 Include_launcher=0 Shortcuts=0 AssociateFiles=0
fi

echo "Installing cx_Freeze and pygame-ce ..."
wine "$python" -m pip install -q --disable-pip-version-check --no-warn-script-location --upgrade cx_Freeze pygame-ce

echo "Copying source files ..."
mkdir "$work/src"
git ls-files -z | tar --null -T - -cf - | tar -xf - -C "$work/src"

echo "Writing the metadata of all games ..."
(cd "$work/src" && python3 -c 'import games, pathlib; games.write_metadata(pathlib.Path("games/metadata.json"))')

mkdir -p dist
zip="dosbox-staging-windows-x64-v$DOSBOX_VERSION.zip"
if ! echo "$DOSBOX_SHA256  dist/$zip" | sha256sum -c --quiet --status 2>/dev/null; then
    echo "Downloading DOSBox Staging $DOSBOX_VERSION ..."
    curl -sSfL -o "$work/$zip" \
        "https://github.com/dosbox-staging/dosbox-staging/releases/download/v$DOSBOX_VERSION/$zip"
    echo "$DOSBOX_SHA256  $work/$zip" | sha256sum -c --quiet
    mv "$work/$zip" "dist/$zip"
fi
unzip -q "dist/$zip" -d "$work/staging" -x "*/dosbox_with_debugger.exe"
mv "$work/staging/dosbox-staging-v$DOSBOX_VERSION" "$work/dosbox-staging"

echo "Building MSI ..."
log=dist/build_msi_wine.log
# Add DOSBox Staging between freezing and packaging, because cx_Freeze
# would leave out its Visual C++ runtime DLLs.
if ! (
    cd "$work/src" &&
    wine "$python" windows/setup_win.py build_exe &&
    mv "$work/dosbox-staging" build/exe.*/ &&
    wine "$python" windows/setup_win.py bdist_msi --skip-build
) >"$log" 2>&1; then
    tail -n 20 "$log"
    echo "Build failed, see $log"
    exit 1
fi
msi=$(cd "$work/src/dist" && ls -- *.msi)
cp "$work/src/dist/$msi" dist/
rm -f ~/ialauncher.iso
xorriso -as mkisofs -J -r -V IALAUNCHER -o ~/ialauncher.iso -graft-points "$msi=dist/$msi"

cat << EOF
Successfully built $PWD/dist/$msi

To install and run it in Wine:

    wine msiexec /i "$PWD/dist/$msi"
    wine "C:\\Program Files\\IA Launcher\\ialauncher.exe"

To install it on Windows, burn ~/ialauncher.iso to a CD and then
insert the CD into a Windows machine :-)

EOF
