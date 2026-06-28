#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="/boot/firmware/config.txt"

echo "Installing camera tools for Ubuntu Raspberry Pi..."
sudo apt update
sudo apt install -y \
  libcamera-tools \
  libcamera0 \
  libcamera-dev \
  v4l-utils \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad

echo "Ensuring the current user is in the video group..."
sudo usermod -aG video "$USER"

if [[ -f "$CONFIG_FILE" ]]; then
  echo "Checking $CONFIG_FILE..."
  sudo cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%Y%m%d%H%M%S)"

  if grep -q '^camera_auto_detect=' "$CONFIG_FILE"; then
    sudo sed -i 's/^camera_auto_detect=.*/camera_auto_detect=1/' "$CONFIG_FILE"
  else
    echo 'camera_auto_detect=1' | sudo tee -a "$CONFIG_FILE" >/dev/null
  fi

  if ! grep -q '^dtoverlay=vc4-kms-v3d' "$CONFIG_FILE"; then
    echo 'dtoverlay=vc4-kms-v3d' | sudo tee -a "$CONFIG_FILE" >/dev/null
  fi
else
  echo "Warning: $CONFIG_FILE was not found."
fi

echo
echo "Done. Reboot is required:"
echo "  sudo reboot"
echo
echo "After reboot, test with:"
echo "  vcgencmd get_camera"
echo "  cam --list"
echo "  source /home/vitamind/vitamin_d/vitamin_d/bin/activate"
echo "  python /home/vitamind/vitamin_d/vitamin_d/testcamera.py"
echo
echo "Expected vcgencmd result must include detected=1 or libcamera interfaces > 0."
