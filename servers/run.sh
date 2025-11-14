#!/usr/bin/env bash
set -euo pipefail

EXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
SERVERS_DIR="$EXT_DIR/servers"
VENV="$SERVERS_DIR/filesearch"

# 0) Detect a suitable Python (>= 3.10)
find_python() {
  for bin in python3.11 python3.10 python3 python; do
    if command -v "$bin" >/dev/null 2>&1; then
      ver=$("$bin" - <<EOF
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
EOF
)
      major=${ver%.*}
      minor=${ver#*.}
      if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
        echo "$bin"
        return 0
      fi
    fi
  done

  echo "[ERROR] Python >= 3.10 is required but not found." >&2
  echo "        Install Python 3.10+ or set \$PYTHON_BIN manually." >&2
  exit 1
}

PYTHON_BIN="${PYTHON_BIN:-$(find_python)}"

echo "[filesearch] using Python: $PYTHON_BIN" >&2

# 1) Create venv if missing
if [ ! -x "$VENV/bin/python3" ]; then
  echo "[filesearch] creating venv at $VENV" >&2
  "$PYTHON_BIN" -m venv "$VENV" 1>&2
  "$VENV/bin/pip" install -U pip wheel setuptools --disable-pip-version-check -q 1>&2
fi

# 2) Install requirements
if [ -f "$SERVERS_DIR/requirements.txt" ]; then
  "$VENV/bin/pip" install -r "$SERVERS_DIR/requirements.txt" \
    --disable-pip-version-check --no-input -q 1>&2
fi

# 3) Exec server
exec "$VENV/bin/python3" "$SERVERS_DIR/file_search.py"
