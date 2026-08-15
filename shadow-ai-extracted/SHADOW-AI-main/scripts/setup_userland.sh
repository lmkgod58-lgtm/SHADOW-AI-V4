#!/bin/bash
set -e
echo "[ Shadow AI 3.0 Setup — UserLAnd ]"
sudo apt update
sudo apt install -y python3-pip python3-venv git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libffi-dev libssl-dev cmake libsqlite3-dev
python3 -m venv ~/shadowai-venv
source ~/shadowai-venv/bin/activate
pip install --upgrade pip
pip install buildozer cython kivy

echo "[ DONE ] Environment ready."
echo "Copy this project's frontend folder to /sdcard/Download/shadow-ai/frontend"
echo "Then run: bash scripts/build_apk.sh"
