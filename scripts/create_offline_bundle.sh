#!/usr/bin/env bash
# Copyright 2024, Massachusetts Institute of Technology
# SPDX-License-Identifier: MIT
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BUNDLE_DIR="${ROOT_DIR}/dist/offline_bundle"
WHEELS_DIR="${BUNDLE_DIR}/wheels"
VERSION="2.2.0"
ARCHIVE_NAME="qrdm-${VERSION}-offline-bundle.tar.gz"

echo "=== Building QRDM Offline Bundle ==="
rm -rf "${BUNDLE_DIR}"
mkdir -p "${WHEELS_DIR}"

echo "1. Building QRDM wheel..."
python -m pip install --upgrade build >/dev/null 2>&1 || true
python -m build --wheel --outdir "${WHEELS_DIR}" "${ROOT_DIR}"

echo "2. Downloading runtime dependency wheels..."
python -m pip download \
    --dest "${WHEELS_DIR}" \
    --only-binary=:all: \
    "${ROOT_DIR}" || {
        echo "Note: Some dependencies may need source distribution fallback..."
        python -m pip download --dest "${WHEELS_DIR}" "${ROOT_DIR}"
    }

echo "3. Creating offline installer script..."
cat << 'EOF' > "${BUNDLE_DIR}/install.sh"
#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WHEELS_DIR="${BUNDLE_DIR}/wheels"

echo "=== Installing QRDM from offline bundle ==="
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required to install QRDM." >&2
    exit 1
fi

python3 -m pip install --no-index --find-links="${WHEELS_DIR}" qrdm

echo "=== Installation complete! ==="
echo "You can now run: qrdm --help"
EOF
chmod +x "${BUNDLE_DIR}/install.sh"

echo "4. Packaging archive..."
tar -czf "${ROOT_DIR}/dist/${ARCHIVE_NAME}" -C "${BUNDLE_DIR}" .

echo "=== Successfully created offline bundle: dist/${ARCHIVE_NAME} ==="

