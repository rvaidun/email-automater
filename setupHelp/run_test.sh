#!/bin/bash

# Navigate to the project directory (in case this script is run from elsewhere). Change the path to the test_gmail_api.py file if needed.
cd "$(dirname "$0")/.."

# Activate the virtual environment
source venv/bin/activate

# Run the test script. Change the path to the test_gmail_api.py file if needed.
python setupHelp/test_gmail_api.py

# Provide helpful message about next steps
if [ $? -ne 0 ]; then
  echo ""
  echo "------------------------------------------------------"
  echo "If you're seeing a credentials.json error, please:"
  echo "1. Follow the instructions in setupHelp/GMAIL_API_SETUP.md"
  echo "2. Download the credentials.json file from Google Cloud Console"
  echo "3. Place it in this directory"
  echo "4. Run this script again"
  echo "------------------------------------------------------"
fi 