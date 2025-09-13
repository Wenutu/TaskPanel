#!/bin/bash
# Simulates a bsub job and captures its "Job ID" (in this case, the PID)
LOG_FILE=${@: -1} # The temp file is the last argument

echo "==> [$$] Starting checkout..."
sleep 5 & # Run in background to get a PID
JOB_ID=$!
echo "Captured Job ID: $JOB_ID"
wait $JOB_ID # Wait for it to finish
echo "==> Checkout complete."
exit 0