#!/usr/bin/env bash
# Vendoriza una skill completa desde mattpocock/skills (SKILL.md + ficheros de soporte).
# Uso: .vendor.sh <upstream_dir> <local_name>
#   ej: .vendor.sh skills/engineering/tdd tdd
# No toca el bloque LAIA: solo baja upstream. El bloque <!-- LAIA:START..END --> se añade aparte.
set -euo pipefail

SHA="0288510dd61ff6ef7c2003834082ab8f2387e80e"
REPO="mattpocock/skills"
UPSTREAM_DIR="$1"; LOCAL_NAME="$2"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$ROOT/$LOCAL_NAME"

mkdir -p "$DEST"
# Lista todos los blobs bajo el dir upstream y los baja preservando subrutas.
curl -s "https://api.github.com/repos/$REPO/git/trees/$SHA?recursive=1" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin); pref='$UPSTREAM_DIR/'
for p in d.get('tree',[]):
    if p['type']=='blob' and p['path'].startswith(pref):
        print(p['path'][len(pref):])
" | while read -r rel; do
    [ -z "$rel" ] && continue
    mkdir -p "$DEST/$(dirname "$rel")"
    curl -s "https://raw.githubusercontent.com/$REPO/$SHA/$UPSTREAM_DIR/$rel" -o "$DEST/$rel"
    echo "  $LOCAL_NAME/$rel"
done
echo "vendored: $LOCAL_NAME"
