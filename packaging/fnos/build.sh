#!/usr/bin/env bash
# packaging/fnos/build.sh - Build LangBot fnOS FPK package (in-repo version)
# 在 LangBot 仓库内直接打包飞牛 fnOS 应用
# Usage:
#   bash packaging/fnos/build.sh                    # 版本取 manifest 中 version=
#   FPK_VERSION=4.10.9 bash packaging/fnos/build.sh # 注入版本（CI 用 release tag）
# Dependencies: python3+Pillow, node+npm, fnpack
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"   # LangBot 仓库根
FPK_DIR="${SCRIPT_DIR}"

echo "==> LangBot fnOS FPK builder (in-repo)"
echo "    Source root: ${SRC_ROOT}"
echo "    FPK dir:     ${FPK_DIR}"

# --- 0. Inject version (release tag) ---
if [ -n "${FPK_VERSION:-}" ]; then
    sed -i "s/^version=.*/version=${FPK_VERSION#v}/" "${FPK_DIR}/manifest"
else
    # 无注入版本时自动跟进仓库主版本（pyproject.toml）
    PY_VER=$(grep -m1 '^version = ' "${SRC_ROOT}/pyproject.toml" | cut -d'"' -f2)
    if [ -n "${PY_VER}" ]; then
        sed -i "s/^version=.*/version=${PY_VER}/" "${FPK_DIR}/manifest"
    fi
fi
MANIFEST_VER=$(grep '^version=' "${FPK_DIR}/manifest" | cut -d= -f2)
echo "    FPK version: ${MANIFEST_VER}"

# --- 1. Build frontend ---
echo "[1/5] Building frontend (web/dist)..."
cd "${SRC_ROOT}/web"
if command -v pnpm >/dev/null 2>&1; then
    pnpm install --frozen-lockfile 2>/dev/null || pnpm install
    pnpm build
else
    npm install
    npx vite build
fi
[ -d dist ] || { echo "ERROR: web/dist missing" >&2; exit 1; }
echo "    Frontend built"

# --- 2. Sync source into packaging/fnos/app/langbot/ ---
echo "[2/5] Syncing source to app/langbot/..."
rm -rf "${FPK_DIR}/app/langbot"
mkdir -p "${FPK_DIR}/app/langbot"
cd "${SRC_ROOT}"
rsync -a \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='web/node_modules' \
    --exclude='web/.vite' \
    --exclude='tests' \
    --exclude='packaging' \
    --exclude='.pytest_cache' \
    --exclude='.mypy_cache' \
    --exclude='.ruff_cache' \
    --exclude='data' \
    --exclude='*.log' \
    --exclude='.dockerignore' \
    --exclude='Dockerfile' \
    --exclude='docker/' \
    --exclude='kubernetes.yaml' \
    --exclude='.github/' \
    --exclude='docs/' \
    --exclude='examples/' \
    --exclude='res/' \
    ./ "${FPK_DIR}/app/langbot/"

[ -d "${FPK_DIR}/app/langbot/web/dist" ] || { echo "ERROR: web/dist missing after rsync!" >&2; exit 1; }
echo "    Source synced ($(du -sh "${FPK_DIR}/app/langbot" | cut -f1))"

# --- 2.5 Download bundled uv binaries (offline install on NAS) ---
echo "[2.5/5] Downloading bundled uv binaries..."
UV_VERSION="0.12.9"
mkdir -p "${FPK_DIR}/app/bin"
for arch in x86_64 aarch64; do
    out="${FPK_DIR}/app/bin/uv-${arch}"
    if [ -x "${out}" ]; then
        echo "    uv-${arch} already present, skip"
        continue
    fi
    tmp="$(mktemp -d)"
    if curl -sSL -o "${tmp}/uv.tar.gz" \
        "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${arch}-unknown-linux-gnu.tar.gz" \
        && tar xzf "${tmp}/uv.tar.gz" -C "${tmp}" \
        && cp "${tmp}/uv-${arch}-unknown-linux-gnu/uv" "${out}"; then
        chmod +x "${out}"
        echo "    uv-${arch} downloaded (${UV_VERSION})"
    else
        echo "    WARNING: failed to download uv for ${arch}, install will fall back to online install" >&2
    fi
    rm -rf "${tmp}"
done

# --- 3. Regenerate icons from res/logo-blue.png ---
echo "[3/5] Generating icons from res/logo-blue.png..."
export LOGO_SRC="${SRC_ROOT}/res/logo-blue.png"
export OUT_DIR="${FPK_DIR}"
python3 << 'PYEOF'
from PIL import Image
import os, sys

src = os.environ.get("LOGO_SRC")
out_dir = os.environ.get("OUT_DIR")
if not src or not out_dir:
    print("ERROR: LOGO_SRC or OUT_DIR not set", file=sys.stderr)
    sys.exit(1)

if not os.path.isfile(src):
    print(f"ERROR: logo source not found: {src}", file=sys.stderr)
    sys.exit(1)

img = Image.open(src).convert("RGBA")

for size, name in [(64, "ICON.PNG"), (256, "ICON_256.PNG")]:
    img.resize((size, size), Image.LANCZOS).save(os.path.join(out_dir, name))

ui_dir = os.path.join(out_dir, "app/ui/images")
os.makedirs(ui_dir, exist_ok=True)
for size in [64, 256]:
    img.resize((size, size), Image.LANCZOS).save(os.path.join(ui_dir, f"icon-{size}.png"))

desktop_dir = os.path.join(out_dir, "app/desktop/images")
os.makedirs(desktop_dir, exist_ok=True)
for size in [64, 256]:
    img.resize((size, size), Image.LANCZOS).save(os.path.join(desktop_dir, f"icon-{size}.png"))

print("    Icons generated")
PYEOF

# --- 4. Validate structure ---
echo "[4/5] Validating FPK structure..."
ERRORS=0
[ -f "${FPK_DIR}/manifest" ] || { echo "  MISSING: manifest"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/config/privilege" ] || { echo "  MISSING: config/privilege"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/config/resource" ] || { echo "  MISSING: config/resource"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/ICON.PNG" ] || { echo "  MISSING: ICON.PNG"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/ICON_256.PNG" ] || { echo "  MISSING: ICON_256.PNG"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/app/ui/config" ] || { echo "  MISSING: app/ui/config"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/app/ui/images/icon-64.png" ] || { echo "  MISSING: app/ui/images/icon-64.png"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/app/ui/images/icon-256.png" ] || { echo "  MISSING: app/ui/images/icon-256.png"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/app/desktop/ai.langbot.main.url" ] || { echo "  MISSING: app/desktop/ai.langbot.main.url"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/app/desktop/images/icon-64.png" ] || { echo "  MISSING: app/desktop/images/icon-64.png"; ERRORS=$((ERRORS+1)); }
[ -f "${FPK_DIR}/app/desktop/images/icon-256.png" ] || { echo "  MISSING: app/desktop/images/icon-256.png"; ERRORS=$((ERRORS+1)); }
[ -d "${FPK_DIR}/cmd" ] || { echo "  MISSING: cmd/"; ERRORS=$((ERRORS+1)); }
[ -d "${FPK_DIR}/wizard" ] || { echo "  MISSING: wizard/"; ERRORS=$((ERRORS+1)); }

for script in "${FPK_DIR}/cmd/"*; do
    [ -x "${script}" ] || { echo "  NOT EXECUTABLE: cmd/$(basename "$script")"; ERRORS=$((ERRORS+1)); }
done

if [ "${ERRORS}" -gt 0 ]; then
    echo "FAILED: ${ERRORS} validation errors" >&2
    exit 1
fi
echo "    Structure OK"

# --- 5. Build FPK ---
echo "[5/5] Building .fpk..."
if ! command -v fnpack >/dev/null 2>&1; then
    echo "ERROR: fnpack not found in PATH." >&2
    echo "  Download from https://developer.fnnas.com/docs/cli/fnpack" >&2
    exit 1
fi

cd "${FPK_DIR}"
fnpack build
FPK_FILE=$(ls -t *.fpk 2>/dev/null | head -1)
if [ -n "${FPK_FILE}" ]; then
    echo ""
    echo "==> Done! FPK: ${FPK_DIR}/${FPK_FILE}"
    echo "    Size: $(du -sh "${FPK_FILE}" | cut -f1)"
else
    echo "WARNING: fnpack finished but no .fpk found in ${FPK_DIR}" >&2
    exit 1
fi
