# Automate Recruiter Emails (Go Version)

This is a Go rewrite of the Python email automation script that automates the process of sending emails to recruiters. It uses the Gmail API to draft emails to recruiters and integrates with [Streak CRM](https://www.streak.com/) to schedule emails for optimal delivery times.

## Features

- **Gmail Integration**: Uses Gmail API to create and save draft emails
- **Template Support**: Supports templating for email subjects and body content
- **Attachment Support**: Can include file attachments with emails
- **Streak Scheduling**: Integrates with Streak CRM to schedule emails for optimal delivery times
- **Timezone Support**: Handles different timezones for scheduling
- **OAuth2 Authentication**: Secure authentication with Google services

## Installation

1. **Prerequisites**: Make sure you have Go 1.21+ installed
2. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd emailer
   ```
3. **Install dependencies**:
   ```bash
   go mod download
   ```
4. **Build the application**:
   ```bash
   go build -o emailer
   ```

## Setup

1. **Gmail API Setup**: Follow the instructions [here](https://developers.google.com/gmail/api/quickstart/go) to enable the Gmail API and download the `credentials.json` file. Save it in the root directory.

2. **Environment Variables**: Create a `.env` file with your configuration:
   ```env
   # Email configuration
   EMAIL_SUBJECT=I would like to work at $recruiter_company
   MESSAGE_BODY_PATH=email_template.html
   ATTACHMENT_PATH=resume.pdf
   ATTACHMENT_NAME=FirstName_LastName_Resume.pdf

   # Streak configuration
   TIMEZONE=America/Los_Angeles
   STREAK_TOKEN=your_streak_token_here
   ENABLE_STREAK_SCHEDULING=true
   SCHEDULE_CSV_PATH=scheduler.csv
   STREAK_EMAIL_ADDRESS=your_email@gmail.com
   ```

## Usage

### Basic Usage

```bash
./emailer "Company Name" "Recruiter Name" "recruiter@company.com"
```

### Command Line Options

```bash
./emailer [OPTIONS] "Company Name" "Recruiter Name" "recruiter@company.com"

Options:
  -ap string
        The path to the attachment file
  -an string
        The name of the attachment file
  -s string
        The subject of the email message as a string template
  -m string
        The path to the message body template
  -tz string
        The timezone to use for scheduling emails
  -sch
        Whether the email should be scheduled
  -scsv string
        CSV to use for scheduling the emails
  -e string
        The email address to send to the Streak API
  -t string
        The path to the token.json file (default "token.json")
  -c string
        The path to the credentials.json file (default "credentials.json")
```

### Examples

1. **Send a simple email**:
   ```bash
   ./emailer "Google" "John Doe" "john.doe@google.com"
   ```

2. **Send with custom subject and template**:
   ```bash
   ./emailer -s "Interested in $recruiter_company" -m "my_template.html" "Google" "John Doe" "john.doe@google.com"
   ```

3. **Send with attachment**:
   ```bash
   ./emailer -ap "resume.pdf" -an "John_Doe_Resume.pdf" "Google" "John Doe" "john.doe@google.com"
   ```

4. **Schedule email for optimal delivery**:
   ```bash
   ./emailer -sch -scsv "scheduler.csv" "Google" "John Doe" "john.doe@google.com"
   ```

## Templating

The application supports templating for both email subjects and body content using Go's template syntax.

### Subject Templating
The `EMAIL_SUBJECT` environment variable supports templating with the `$recruiter_company` variable:
```
EMAIL_SUBJECT=I would like to work at $recruiter_company
```

### Body Templating
The message body template file supports the following variables:
- `$recruiter_name`: The recruiter's full name
- `$recruiter_company`: The company name

Example template (`email_template.html`):
```html
<!DOCTYPE html>
<html>
<body>
    <p>Dear $recruiter_name,</p>
    <p>I am interested in opportunities at $recruiter_company.</p>
    <p>Best regards,<br>Your Name</p>
</body>
</html>
```

## Scheduling

To enable email scheduling, you need:

1. **Streak Token**: Get your Streak API token by inspecting network requests when scheduling an email in Streak. Look for the request to `https://api.streak.com/api/v2/sendlaters` and copy the `Authorization` header value (without the `Bearer` prefix).

2. **Schedule CSV**: Create a CSV file with the following columns:
   - `DAY`: Day of week (0=Monday, 6=Sunday)
   - `START_TIME`: Start time in HH:MM format
   - `END_TIME`: End time in HH:MM format

Example `scheduler.csv`:
```csv
DAY,START_TIME,END_TIME
0,10:00,11:00
0,14:00,14:30
1,10:00,11:00
1,14:00,14:30
2,10:00,11:00
2,14:00,14:30
3,10:00,11:00
3,14:00,14:30
4,10:00,11:00
```

The application will schedule emails at random times within the earliest available time range.

## Authentication

The application uses OAuth2 for Gmail API authentication:

1. **First Run**: You'll be prompted to authenticate with Google. Follow the browser link and enter the authorization code.
2. **Token Storage**: After successful authentication, a `token.json` file is created for future use.
3. **Token Refresh**: The application automatically refreshes expired tokens.

## Project Structure

```
emailer/
├── main.go                 # Main application entry point
├── go.mod                 # Go module file
├── go.sum                 # Go module checksums
├── internal/
│   ├── config/            # Configuration constants
│   ├── gmail/             # Gmail API integration
│   ├── scheduler/         # Email scheduling logic
│   └── streak/            # Streak API integration
├── credentials.json       # Gmail API credentials (not in repo)
├── token.json            # OAuth token (generated after first run)
├── scheduler.csv         # Email schedule configuration
└── email_template.html   # Email template
```

## Differences from Python Version

- **Performance**: Go version is compiled and generally faster
- **Dependencies**: Fewer runtime dependencies, single binary distribution
- **Error Handling**: More explicit error handling with Go's error system
- **Concurrency**: Better support for concurrent operations (though not utilized in this version)
- **Deployment**: Easier deployment as a single binary

## Troubleshooting

1. **Authentication Issues**: Delete `token.json` and re-authenticate
2. **Gmail API Errors**: Ensure your `credentials.json` is valid and Gmail API is enabled
3. **Streak Scheduling Issues**: Verify your Streak token is valid and not expired
4. **Timezone Issues**: Use IANA timezone names (e.g., "America/Los_Angeles")

## License

This project is open source. Feel free to contribute or modify as needed.
