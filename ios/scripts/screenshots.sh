#!/usr/bin/env bash
# Capture the app's screens on a simulator, light and dark, into $1
# (default docs/app-store/screenshots). Usage:
#   ios/scripts/screenshots.sh [out-dir] [simulator-udid]
# Uses -uiTesting, so no network request and a fresh temporary store.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
out="$(cd "${1:-$root/docs/app-store/screenshots}" 2>/dev/null && pwd || (mkdir -p "$1" && cd "$1" && pwd))"
sim="${2:?pass a simulator UDID (xcrun simctl list devices)}"
derived="$(mktemp -d)"
trap 'rm -rf "$derived"' EXIT
cd "$root/ios"
xcodebuild build-for-testing -project AlgaeAlerts.xcodeproj -scheme AlgaeAlerts \
  -destination "id=$sim" -derivedDataPath "$derived" CODE_SIGN_IDENTITY=- -quiet
for appearance in light dark; do
  xcrun simctl ui "$sim" appearance "$appearance"
  suffix=""
  if [ "$appearance" = dark ]; then suffix="-dark"; fi
  TEST_RUNNER_SCREENSHOT_DIR="$out" TEST_RUNNER_SCREENSHOT_SUFFIX="$suffix" \
    xcodebuild test-without-building -project AlgaeAlerts.xcodeproj -scheme AlgaeAlerts \
    -destination "id=$sim" -derivedDataPath "$derived" CODE_SIGN_IDENTITY=- \
    -only-testing:AlgaeAlertsUITests/ScreenshotUITests -quiet
done
xcrun simctl ui "$sim" appearance light
ls "$out"
