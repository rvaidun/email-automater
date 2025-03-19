# Email Automater Helper Scripts

This directory contains additional helper scripts and documentation to make using the Email Automater tool easier.

## Files Included

- **send_email.sh**: Simple shell script to draft emails using the main automate_emails.py script
- **send_email_directly.py**: Python script to send emails immediately (without creating a draft)
- **send_email_now.sh**: Shell script wrapper for send_email_directly.py
- **test_gmail_api.py**: Test script to verify your Gmail API connection is working
- **run_test.sh**: Shell script wrapper for test_gmail_api.py
- **GMAIL_API_SETUP.md**: Detailed instructions for setting up the Gmail API
- **USAGE_GUIDE.md**: Guide for using all the email automation scripts

## Quick Start

1. First, make sure your Gmail API is set up correctly:
   ```
   ./run_test.sh
   ```

2. To create an email draft:
   ```
   ./send_email.sh "Company Name" "Recruiter Name" "recruiter@email.com"
   ```

3. To send an email immediately:
   ```
   ./send_email_now.sh "Company Name" "Recruiter Name" "recruiter@email.com"
   ```

Refer to USAGE_GUIDE.md for more detailed instructions. 







## Setting Up Your Email Template

1. Edit the `email_template.txt` file to personalize your email
2. Replace placeholders like `[specific area]`, `[value]`, `[achievement/product launch/news]`, etc. with more specific information about each company
3. Replace `[YOUR FULL NAME]`, `[YOUR PHONE NUMBER]`, `[YOUR EMAIL ADDRESS]`, and `[YOUR LINKEDIN PROFILE URL]` with your information
4. You can keep the `$recruiter_name` and `$recruiter_company` variables - these will be automatically replaced when you run the script

## Preparing Your Resume

1. Replace the placeholder `resume.pdf` with your actual resume

## Running the Script

You have two options for sending emails:

### Option 1: Creating Draft Emails 

This creates a draft email that you can review and manually send later:

```bash
./send_email.sh "Company Name" "Recruiter Name" "recruiter@email.com"
```

### Option 2: Sending Emails Immediately

This sends the email immediately:

```bash
./send_email_now.sh "Company Name" "Recruiter Name" "recruiter@email.com"
```





# Gmail API Setup Guide

This guide will help you set up the Gmail API for your email automater project.

## Step 1: Enable the Gmail API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. In the API Library, search for "Gmail API" and enable it

## Step 2: Configure the OAuth Consent Screen

1. In the Google Cloud Console, go to "OAuth consent screen"
2. Select "Internal" user type (if you're using a Google Workspace account) or "External" (if using a personal Gmail account)
3. Fill in the required app information:
   - App name: "Email Automater"
   - User support email: Your email address
   - Developer contact information: Your email address
4. Click "Save and Continue"
5. For scopes, you don't need to add any at this stage
6. Click "Save and Continue"
7. Add test users if you selected "External" user type
8. Click "Save and Continue"

## Step 3: Create OAuth Credentials

1. In the Google Cloud Console, go to "Credentials"
2. Click "Create Credentials" and select "OAuth client ID"
3. Select "Desktop app" as the application type
4. Name it "Email Automater Desktop Client"
5. Click "Create"
6. Download the JSON file
7. Save the file as `credentials.json` in your project directory

## Step 4: Test the Setup

1. Ensure you have the necessary Python packages installed:
   ```
   pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
   ```

2. Run the test script to verify your setup:
   ```
   ./test_gmail_api.py
   ```

3. The first time you run it, a browser window will open asking you to authorize the application
4. Sign in with your Google account
5. Grant the requested permissions
6. The script will create a `token.json` file in your project directory
7. You should see your Gmail labels listed in the terminal

## Step 5: Use the API in Your Application

1. Now that you have `credentials.json` and `token.json`, your main application can use these to authenticate
2. The `automate_emails.py` script is already set up to use these files
3. You can run it with:
   ```
   ./automate_emails.py "Company Name" "Recruiter Name" "recruiter@example.com"
   ```

4. Check your Gmail drafts folder to see the created email 



If any issues:

Go to the Google Cloud Console: https://console.cloud.google.com/
Select your project
Go to "APIs & Services" > "OAuth consent screen"
Under "Test users", click "Add users"
Add your email address