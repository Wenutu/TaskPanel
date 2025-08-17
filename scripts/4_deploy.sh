#!/bin/bash
LOG_FILE=${@: -1}

echo "==> [$$] Deploying..."
sleep 2 &
JOB_ID=$!
echo "Captured Job ID: $JOB_ID"
wait $JOB_ID
echo "==> Deployment finished."
exit 0