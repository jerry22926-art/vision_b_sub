#!/usr/bin/env bash
set -euo pipefail

cd /home/vitamind/vitamin_d

echo "Step 1/3: install/repair Ubuntu camera tools"
./repair_camera_stack.sh

echo
echo "Step 2/3: force IMX219 camera overlay"
./configure_camera_overlay.sh imx219

echo
echo "Step 3/3: reboot is required"
echo "Run now:"
echo "  sudo reboot"
