#!/bin/bash
# Simple script to send an email to a recruiter
# Usage: ./send_email.sh "Company Name" "Recruiter Name" "email@company.com"

if [ "$#" -ne 3 ]; then
    echo "Usage: ./send_email.sh \"Company Name\" \"Recruiter Name\" \"email@company.com\""
    echo ""
    echo "Example:"
    echo "  ./send_email.sh \"Google\" \"John Smith\" \"john.smith@google.com\""
    exit 1
fi

COMPANY="$1"
NAME="$2"
EMAIL="$3"

echo "Sending email to: $NAME at $COMPANY ($EMAIL)"
echo ""

python3 automate_emails.py "$COMPANY" "$NAME" "$EMAIL"




