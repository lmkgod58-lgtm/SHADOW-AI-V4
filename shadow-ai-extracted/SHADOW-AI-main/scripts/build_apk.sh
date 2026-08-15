#!/bin/bash
set -e
# Shadow AI 3.0 APK Builder for UserLAnd Ubuntu

source ~/shadowai-venv/bin/activate
mkdir -p ~/shadowai-apk
cp -r /sdcard/Download/shadow-ai/frontend/* ~/shadowai-apk/
cd ~/shadowai-apk

if [ ! -f main.py ]; then
  echo "ERROR: frontend files were not copied."
  exit 1
fi

echo "[ Shadow AI ] Building APK..."
echo "Backend URL is already configured in main.py."
echo "Put your chosen intro.mp4 and background.jpg beside main.py before building."

buildozer android debug

mkdir -p /sdcard/Download
cp -f bin/*.apk /sdcard/Download/
echo "[ DONE ] APK copied to /sdcard/Download/"
ls -lh /sdcard/Download/shadowai*.apk 2>/dev/null || true
