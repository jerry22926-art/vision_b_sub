#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="/boot/firmware/config.txt"

usage() {
  cat <<'EOF'
Usage:
  ./configure_camera_overlay.sh <sensor>

Common sensors:
  ov5647  Raspberry Pi Camera Module v1
  imx219  Raspberry Pi Camera Module v2
  imx477  Raspberry Pi HQ Camera
  imx519  Some Arducam autofocus modules

Example:
  ./configure_camera_overlay.sh imx219

Note:
  Raspberry Pi Camera Module 3 uses imx708. This Ubuntu image does not appear
  to include imx708.dtbo, so Camera Module 3 probably needs newer firmware/OS.
EOF
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

SENSOR="$1"
OVERLAY="/boot/firmware/overlays/${SENSOR}.dtbo"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing $CONFIG_FILE"
  exit 1
fi

if [[ ! -f "$OVERLAY" ]]; then
  echo "Missing overlay: $OVERLAY"
  echo "Available camera overlays:"
  ls /boot/firmware/overlays | grep -E '^(imx|ov).*\.dtbo$' | sed 's/\.dtbo$//' | sort
  exit 1
fi

echo "Configuring camera overlay: $SENSOR"
sudo cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%Y%m%d%H%M%S)"

# Manual camera overlay is more reliable than auto detect on some Ubuntu raspi images.
if grep -q '^camera_auto_detect=' "$CONFIG_FILE"; then
  sudo sed -i 's/^camera_auto_detect=.*/camera_auto_detect=0/' "$CONFIG_FILE"
else
  echo 'camera_auto_detect=0' | sudo tee -a "$CONFIG_FILE" >/dev/null
fi

sudo sed -i '/^dtoverlay=\(ov5647\|imx219\|imx258\|imx290\|imx296\|imx378\|imx477\|imx519\|ov2311\|ov7251\|ov9281\)/d' "$CONFIG_FILE"
echo "dtoverlay=$SENSOR" | sudo tee -a "$CONFIG_FILE" >/dev/null

echo
echo "Updated $CONFIG_FILE. Reboot now:"
echo "  sudo reboot"
echo
echo "After reboot, check:"
echo "  vcgencmd get_camera"
echo "  v4l2-ctl --list-devices"
echo "  python3 -c 'from picamera2 import Picamera2; print(Picamera2.global_camera_info())'"
