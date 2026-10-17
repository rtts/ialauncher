#!/bin/bash

# Build a Windows MSI installer on Linux using Wine.

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_VERSION=3.14.8
DOSBOX_VERSION=0.74-3

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

if [ ! -d "$prefix/drive_c/Program Files (x86)/DOSBox-$DOSBOX_VERSION" ]; then
    echo "Installing DOSBox $DOSBOX_VERSION in $prefix ..."
    installer="DOSBox$DOSBOX_VERSION-win32-installer.exe"
    curl -sSfL -o "$work/$installer" \
        "https://sourceforge.net/projects/dosbox/files/dosbox/$DOSBOX_VERSION/$installer/download"
    wine "$work/$installer" /S
fi

echo "Installing cx_Freeze and pygame-ce ..."
wine "$python" -m pip install -q --disable-pip-version-check --no-warn-script-location --upgrade cx_Freeze pygame-ce

echo "Copying source files ..."
mkdir "$work/src"
git ls-files -z | tar --null -T - -cf - | tar -xf - -C "$work/src"

echo "Building MSI ..."
mkdir -p dist
log=dist/build_msi_wine.log
if ! (cd "$work/src" && wine "$python" windows/setup_win.py bdist_msi) >"$log" 2>&1; then
    tail -n 20 "$log"
    echo "Build failed, see $log"
    exit 1
fi
msi=$(cd "$work/src/dist" && ls -- *.msi)
cp "$work/src/dist/$msi" dist/
xorriso -as mkisofs -J -r -V IALAUNCHER -o ~/ialauncher.iso -graft-points "$msi=dist/$msi"

cat << EOF
Successfully built $PWD/dist/$msi

To install and run it in Wine:

    wine msiexec /i "$PWD/dist/$msi"
    wine "C:\\Program Files\\IA Launcher\\ialauncher.exe"

To install it on Windows, burn ~/ialauncher.iso to a CD and then
insert the CD into a Windows machine :-)

EOF
