#!/bin/bash
TASK_NAME=$1
LOG_FILE=${@: -1}

echo "==> [$$] Starting build for task $TASK_NAME..."
# Simulate two bsub jobs in this step
for i in {1..30}; do
    # test long output
    echo "Building... $i/30"
    sleep 2
done
for i in {1..2}; do
    echo "Submitting build job $i..."
    sleep 2 &
    JOB_ID=$!
    echo "Captured Job ID: $JOB_ID"
    wait $JOB_ID
done

if [ "$TASK_NAME" == "Task-B" ]; then
  echo "==> Build FAILED for $TASK_NAME!" >&2
  exit 1
else
  echo "==> Build successful for $TASK_NAME."
  exit 0
fi