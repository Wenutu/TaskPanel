#!/bin/bash
LOG_FILE=${@: -1}

echo "==> [$$] Running tests..."
sleep 3 &
JOB_ID=$!
echo "Captured Job ID: $JOB_ID"
echo "$JOB_ID" >> "$LOG_FILE"
wait $JOB_ID
echo "==> Tests passed."
exit 0