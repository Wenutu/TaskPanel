#!/bin/bash
LOG_FILE=${@: -1}

echo "==> [$$] Running tests..."
echo "long message test: This is a very long message to test the logging functionality of the TaskPanel application. It should be able to handle and display long messages properly without any issues. Let's see how it manages this message in the log file."
sleep 3 &
JOB_ID=$!
echo "Captured Job ID: $JOB_ID"
wait $JOB_ID
echo "==> Tests passed."
exit 0