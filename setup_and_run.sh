#!/bin/bash
# ONE-CLICK SETUP & RUN SCRIPT
# Usage: ./setup_and_run.sh "Company" "Name" "email@company.com"

set -e

echo "=========================================="
echo "   Email Outreach Tool - Auto Setup"
echo "=========================================="
echo ""

# Check if we have arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: ./setup_and_run.sh \"Company Name\" \"Recruiter Name\" \"email@company.com\""
    echo ""
    echo "Example:"
    echo "  ./setup_and_run.sh \"Google\" \"John Smith\" \"john.smith@google.com\""
    exit 1
fi

COMPANY="$1"
NAME="$2"
EMAIL="$3"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="mac"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
else
    OS="windows"
fi

echo "Detected OS: $OS"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv (Python package manager)..."
    if [[ "$OS" == "mac" ]]; then
        # Check if brew is installed
        if command -v brew &> /dev/null; then
            brew install uv
        else
            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.local/bin:$PATH"
        fi
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    echo "✅ uv installed"
else
    echo "✅ uv already installed"
fi

# Install dependencies if .venv doesn't exist
if [ ! -d ".venv" ]; then
    echo ""
    echo "Installing dependencies..."
    uv sync
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

echo ""
echo "=========================================="
echo "Sending email to: $NAME at $COMPANY"
echo "Email: $EMAIL"
echo "=========================================="
echo ""

# Run the email script
.venv/bin/python automate_emails.py "$COMPANY" "$NAME" "$EMAIL"

echo ""
echo "✅ Done! Email sent."
echo "   Check Gmail for delivery status."
