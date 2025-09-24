#!/usr/bin/env bash
set -euo pipefail

# Resolve project root (directory of this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
# Find the nearest parent directory containing setup.py or pyproject.toml
PROJECT_ROOT="$SCRIPT_DIR"
while true; do
  if [ -f "$PROJECT_ROOT/pyproject.toml" ] || [ -f "$PROJECT_ROOT/setup.py" ]; then
    break
  fi
  PARENT="$(dirname "$PROJECT_ROOT")"
  if [ "$PARENT" = "$PROJECT_ROOT" ]; then
    echo "Could not locate a Python project root (setup.py or pyproject.toml)." >&2
    exit 1
  fi
  PROJECT_ROOT="$PARENT"
done

# Args:
#  $1: version (optional) OR env name if not a version
#  $2: env name (optional)

# Load previous version if present
VERSION_FILE="${SCRIPT_DIR}/VERSION"
PREV_VERSION=""
if [ -f "$VERSION_FILE" ]; then
  PREV_VERSION="$(cat "$VERSION_FILE" | tr -d '\n' | tr -d '\r')"
fi

is_version() {
  [[ "$1" =~ ^[0-9]+(\.[0-9]+)*$ ]]
}

increment_version() {
  local v="$1"
  IFS='.' read -r -a parts <<< "$v"
  local n=${#parts[@]}
  if [ $n -eq 0 ]; then
    echo "0.1"
    return
  fi
  local last_index=$((n-1))
  local last=${parts[$last_index]}
  if [[ "$last" =~ ^[0-9]+$ ]]; then
    parts[$last_index]=$((last+1))
  else
    # Fallback: append .1
    parts+=("1")
  fi
  (IFS='.'; echo "${parts[*]}")
}

RAW1="${1:-}"
RAW2="${2:-}"

VERSION=""
CONDA_ENV_NAME="record"

if [ -n "$RAW1" ]; then
  if is_version "$RAW1"; then
    VERSION="$RAW1"
    if [ -n "$RAW2" ]; then
      CONDA_ENV_NAME="$RAW2"
    fi
  else
    CONDA_ENV_NAME="$RAW1"
    if [ -n "$RAW2" ] && is_version "$RAW2"; then
      VERSION="$RAW2"
    fi
  fi
fi

if [ -z "$VERSION" ]; then
  if [ -n "$PREV_VERSION" ] && is_version "$PREV_VERSION"; then
    VERSION="$(increment_version "$PREV_VERSION")"
  else
    VERSION="0.1"
  fi
fi

echo "$VERSION" > "$VERSION_FILE"

APP_BASENAME="Gum Recorder"
APP_NAME="${APP_BASENAME} v${VERSION}"
IDENTIFIER="com.local.gumrecorder.v${VERSION}"

echo "==> Building ${APP_NAME} (${IDENTIFIER}) using env: ${CONDA_ENV_NAME}"

echo "==> Initializing conda and activating environment: ${CONDA_ENV_NAME}"
if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  if conda activate "${CONDA_ENV_NAME}" 2>/dev/null; then
    echo "Activated env by name: ${CONDA_ENV_NAME}"
  else
    # Try to find env path from 'conda env list'
    ENV_PATH="$(conda env list | awk -v tgt="${CONDA_ENV_NAME}" '$0 ~ "/envs/"tgt"$" {print $NF}')"
    if [ -z "${ENV_PATH}" ]; then
      # Try matching any path that ends with the target name
      ENV_PATH="$(conda env list | awk -v tgt="/${CONDA_ENV_NAME}$" '$NF ~ tgt {print $NF}')"
    fi
    if [ -n "${ENV_PATH}" ] && conda activate "${ENV_PATH}" 2>/dev/null; then
      echo "Activated env by path: ${ENV_PATH}"
    else
      echo "Conda environment '${CONDA_ENV_NAME}' not found. Create it or pass a different name/version as arguments." >&2
      conda info --envs || true
      exit 1
    fi
  fi
else
  echo "Conda not found on PATH. Please install Miniconda/Anaconda and create 'record' env." >&2
  exit 1
fi

echo "==> Installing/Updating build dependencies"
python -m pip install --upgrade pip wheel
python -m pip install --upgrade pyinstaller

echo "==> Ensuring package is installable"
pushd "$PROJECT_ROOT" >/dev/null
python -m pip install -e .
popd >/dev/null

echo "==> Building macOS .app with PyInstaller"
export PYINSTALLER_APP_NAME="${APP_NAME}"
export PYINSTALLER_BUNDLE_IDENTIFIER="${IDENTIFIER}"
pyinstaller --noconfirm "${SCRIPT_DIR}/Gum Recorder.spec"
unset PYINSTALLER_APP_NAME
unset PYINSTALLER_BUNDLE_IDENTIFIER

APP_PATH="${SCRIPT_DIR}/dist/${APP_NAME}.app"
INFO_PLIST="${APP_PATH}/Contents/Info.plist"

# Post-process Info.plist with version keys
if [ -f "$INFO_PLIST" ]; then
  if /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$INFO_PLIST" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${VERSION}" "$INFO_PLIST" || true
  else
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string ${VERSION}" "$INFO_PLIST" || true
  fi
  if /usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$INFO_PLIST" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${VERSION}" "$INFO_PLIST" || true
  else
    /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string ${VERSION}" "$INFO_PLIST" || true
  fi
  # Ensure Automation usage description for Apple Events (required on macOS for URL retrieval via AppleScript)
  if /usr/libexec/PlistBuddy -c 'Print :NSAppleEventsUsageDescription' "$INFO_PLIST" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Set :NSAppleEventsUsageDescription Uses Apple Events to read the active browser tab URL you are viewing." "$INFO_PLIST" || true
  else
    /usr/libexec/PlistBuddy -c "Add :NSAppleEventsUsageDescription string Uses Apple Events to read the active browser tab URL you are viewing." "$INFO_PLIST" || true
  fi
fi

# Reset TCC permissions for this app bundle identifier (best effort, non-fatal)
echo "==> Resetting TCC permissions for ${IDENTIFIER} (Accessibility, InputMonitoring, ScreenCapture, AppleEvents)"
if command -v tccutil >/dev/null 2>&1; then
  tccutil reset Accessibility "${IDENTIFIER}" || true
  tccutil reset InputMonitoring "${IDENTIFIER}" || true
  tccutil reset ScreenCapture "${IDENTIFIER}" || true
  tccutil reset AppleEvents "${IDENTIFIER}" || true
else
  echo "tccutil not found; skipping TCC reset"
fi

# Prepare entitlements for Apple Events automation (always generated so we can ad-hoc sign if needed)
ENTITLEMENTS_PLIST="${SCRIPT_DIR}/apple_events.entitlements.plist"
cat > "${ENTITLEMENTS_PLIST}" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.automation.apple-events</key>
  <true/>
</dict>
</plist>
EOF

SIGN_IDENTITY_DEFAULT="Mac Developer"
SIGN_IDENTITY="${CODESIGN_IDENTITY:-${SIGN_IDENTITY_DEFAULT}}"
SELECTED_IDENTITY="${SIGN_IDENTITY}"
if [ "${SIGN_IDENTITY}" != "-" ] && ! security find-identity -v -p codesigning 2>/dev/null | grep -q "${SIGN_IDENTITY}"; then
  echo "No code signing identity '${SIGN_IDENTITY}' found; defaulting to ad-hoc signing."
  SELECTED_IDENTITY="-"
fi

echo "==> Code signing app with identity: ${SELECTED_IDENTITY} (Apple Events entitlement)"
if [ "${SELECTED_IDENTITY}" = "-" ]; then
  codesign --deep --force --entitlements "${ENTITLEMENTS_PLIST}" --sign "${SELECTED_IDENTITY}" "${APP_PATH}"
else
  codesign --deep --force --options runtime --entitlements "${ENTITLEMENTS_PLIST}" --sign "${SELECTED_IDENTITY}" "${APP_PATH}"
fi
echo "==> Verifying code signature"
codesign --verify --deep --strict --verbose=2 "${APP_PATH}" || true

echo "==> Build complete"
echo "Open the app at: ${APP_PATH}"
echo "Version: ${VERSION}"
echo "Note: On first run, macOS will ask for Screen Recording, Accessibility, Input Monitoring, and Automation permissions."
