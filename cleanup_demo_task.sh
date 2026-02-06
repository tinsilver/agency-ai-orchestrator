#!/bin/bash
# Script to delete the created ClickUp task for demo purposes
# Usage: ./cleanup_demo_task.sh TASK_ID

if [ -z "$1" ]; then
    echo "Usage: ./cleanup_demo_task.sh TASK_ID"
    echo "Example: ./cleanup_demo_task.sh 86c7ypme2"
    exit 1
fi

TASK_ID=$1
CLICKUP_API_KEY=$(grep CLICKUP_API_KEY .env | cut -d '=' -f2)

if [ -z "$CLICKUP_API_KEY" ]; then
    echo "Error: CLICKUP_API_KEY not found in .env file"
    exit 1
fi

echo "Deleting ClickUp task: $TASK_ID"
curl -X DELETE "https://api.clickup.com/api/v2/task/$TASK_ID" \
    -H "Authorization: $CLICKUP_API_KEY"

echo ""
echo "✅ Task deleted successfully"
