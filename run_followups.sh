#!/bin/bash
# Script to run follow-up emails - designed to be used in a cron job

# Change to the script directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the follow-up script
python send_followups.py

# Log the execution time
echo "Follow-up script executed at $(date)" >> followup.log 