#!/bin/bash

export DISPLAY=:99

for attempt in $(seq 1 240); do
  MAIN_WINDOW="$(xdotool search --name "Cooja: The Contiki Network Simulator" 2>/dev/null | head -n 1)"

  if [ -n "${MAIN_WINDOW}" ]; then
    LOADING_WINDOW="$(xdotool search --name "Loading .*ranger-core-5nodes-onehop.csc" 2>/dev/null | head -n 1)"

    if [ -z "${LOADING_WINDOW}" ]; then
      sleep 5
      xdotool windowactivate "${MAIN_WINDOW}" >/dev/null 2>&1 || true
      xdotool key --window "${MAIN_WINDOW}" ctrl+s >/dev/null 2>&1 || true
      echo "RANGER_GUI_AUTOSTART_SENT"
      break
    fi
  fi

  sleep 2
done
