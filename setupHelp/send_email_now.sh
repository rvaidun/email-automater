#!/bin/bash

# Navigate to the project directory (in case this script is run from elsewhere) change the path back a directory if needed.
cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Check if correct number of arguments are provided
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 \"Company Name\" \"Recruiter Name\" \"recruiter@email.com\""
    exit 1
fi

# Run the direct email sender script
python setupHelp/send_email_directly.py "$1" "$2" "$3"

# Check if the script executed successfully
if [ $? -eq 0 ]; then
    echo "📨 Email sent successfully!"
else
    echo "❌ Error sending email. Please check the error message above."
    
    # Check for common issues
    if [ ! -f "credentials.json" ]; then
        echo ""
        echo "------------------------------------------------------"
        echo "credentials.json file is missing! Please:"
        echo "1. Follow the instructions in setupHelp/GMAIL_API_SETUP.md"
        echo "2. Download the credentials.json file from Google Cloud Console"
        echo "3. Place it in this directory"
        echo "------------------------------------------------------"
    fi
fi 