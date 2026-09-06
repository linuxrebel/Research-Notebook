#!/usr/bin/env bash
# Notebook uninstaller. Removes the /usr/local/bin symlink and /opt/Notebook.
# Leaves user data (~/research and Obsidian vaults) untouched.
#   sudo /opt/Notebook/uninstall.sh
set -euo pipefail

DEST="${DEST:-/opt/Notebook}"
BIN="${BIN:-/usr/local/bin/Notebook}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Must run as root. Try: sudo $DEST/uninstall.sh" >&2
  exit 1
fi

rm -f "$BIN"
rm -rf "$DEST"

echo "Notebook removed."
echo "Your research (~/research) and Obsidian vaults were left untouched."
