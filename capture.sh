#!/bin/bash

BASE="/home/curdog/New_lapse"
CAPTURE_SCRIPT="$BASE/capture.py"
LOG_DIR="$BASE/logs"
RUN_LOG="$LOG_DIR/capture_loop.log"

mkdir -p "$LOG_DIR"

echo "========================================" >> "$RUN_LOG"
echo "Starting capture loop: $(date)" >> "$RUN_LOG"
echo "========================================" >> "$RUN_LOG"

while true; do
  echo "--- Capture start: $(date) ---" >> "$RUN_LOG"

  "$BASE/.venv/bin/python" "$CAPTURE_SCRIPT" 2>&1 | tee -a "$RUN_LOG"
  EXIT_CODE=${PIPESTATUS[0]}

  if [ $EXIT_CODE -ne 0 ]; then
    echo "Capture failed with exit code $EXIT_CODE at $(date)" | tee -a "$RUN_LOG"
  else
    echo "Capture complete: $(date)" | tee -a "$RUN_LOG"
  fi

  echo "Sleeping 15 minutes..." | tee -a "$RUN_LOG"
  sleep 900
done
