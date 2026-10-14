#!/bin/bash

export DISPLAY=:99
export HOME=/root
RANGER_COOJA_SCENARIO="${RANGER_COOJA_SCENARIO:-/workspace/experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.csc}"

echo "============================================================"
echo "RANGER-IoT COOJA GUI"
echo "DISPLAY=${DISPLAY}"
echo "noVNC=http://127.0.0.1:6080/vnc.html"
echo "============================================================"

mkdir -p /tmp/.X11-unix
mkdir -p /root/.gradle

Xvfb :99 \
  -screen 0 1920x1080x24 \
  -ac \
  -noreset \
  >/tmp/xvfb.log 2>&1 &

sleep 2

openbox-session \
  >/tmp/openbox.log 2>&1 &

x11vnc \
  -display :99 \
  -forever \
  -shared \
  -nopw \
  -rfbport 5900 \
  -localhost \
  >/tmp/x11vnc.log 2>&1 &

websockify \
  --web=/usr/share/novnc \
  0.0.0.0:6080 \
  127.0.0.1:5900 \
  >/tmp/websockify.log 2>&1 &

sleep 2

cd /workspace/third_party/contiki-ng/tools/cooja

# RANGER GUI SCRIPTED AUTOSTART
/bin/bash /workspace/experiments/cooja/gui/autostart-ranger.sh &

echo "Starting Cooja GUI..."

# Use bash explicitly because the repository is bind-mounted
# from Windows and the executable bit is not reliable.
exec /bin/bash ./gradlew run --args="${RANGER_COOJA_SCENARIO}"
