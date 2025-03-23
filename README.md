# Automate Recruiter Emails
This is a simple python script that automates the process of sending emails to recruiters. It uses the gmail API to draft emails to recruiters. Currently I use it in conjunction with [Streak CRM](https://www.streak.com/) to manage my job search. I write the draft using this script and then later schedule the email to be sent later manually using the schedule message to send feature which streak has. Gmail also has scheduling built in but I prefer to use Streak since they also provide somewhat accurate read receipts to see when emails have been read. Unfortunately, Google Gmail API does not support schedule sending natively. Instead I reverse engineered the Streak API to schedule the draft emails to be sent later. 
See a demo [here](https://youtu.be/Ef5i8DboJP4).

# Installation
1. Clone the repository
2. Create a virtual environment `python3 -m venv venv`
3. Activate the virtual environment `source venv/bin/activate`
4. Install the requirements `pip install -r requirements.txt`
5. Follow the instructions [here](https://developers.google.com/gmail/api/quickstart/python) to enable the Gmail API and download the `credentials.json` file. Save the file in the root directory of the repository.

Your directory structure should look like this:
```
.
├── .env
├── .gitignore
├── automate_emails.py
├── credentials.json
├── email_template.txt
├── README.md
├── requirements.txt
├── resume.pdf
└── token.json
```

The `token.json` file will not exist yet if you haven't run the script yet. The `token.json` file stores the login credentials required to access your Google account so you don't have to relogin each time you run the script. If the file does not exist you will be prompted to login to Google using standard Oauth2 flow.

## Environment Variables
The following environment variables should be set:
```
# Email stuff
EMAIL_SUBJECT=I would like to work at $recruiter_company
MESSAGE_BODY_PATH=email_template.txt
ATTACHMENT_PATH=resume.pdf
ATTACHMENT_NAME=FirstName_LastName_Resume.pdf

# Streak stuff
TIMEZONE=America/Los_Angeles
STREAK_TOKEN=classic:C/THIS+IS+/NOT/A/REAL TOKEN
ENABLE_STREAK_SCHEDULING=True
SCHEDULE_CSV_PATH=scheduler.csv
STREAK_EMAIL_ADDRESS=first.last@gmail.com

```
- `EMAIL_SUBJECT`: The subject of the email. The script will replace the `$recruiter_company` variable with the value provided in the command line arguments. Interally the script is using [Python's templating syntax](https://docs.python.org/3.3/tutorial/stdlib2.html#templating) to replace the variables.

- `MESSAGE_BODY_PATH`: The name of the file to process. The file should use Python's templating syntax to have the following variables: `recruiter_name`, `$recruiter_company`. The script will replace these variables with the values provided in the command line arguments. For example, the `email_template.txt` file could look like this:
```
Dear $recruiter_name,

I am interested in the position at $recruiter_company.
```
- `ATTACHMENT_PATH`: The path to the attachment file.
- `ATTACHMENT_NAME`: The name of the attachment file that will be sent to the recruiter.

# Usage

```
usage: automate_emails.py [-h] [--subject [SUBJECT]] [--message_body_path [MESSAGE_BODY_PATH]] [--attachment_path [ATTACHMENT_PATH]]
                          [--attachment_name [ATTACHMENT_NAME]] [--schedule] [--schedule_csv_path [SCHEDULE_CSV_PATH]] [--timezone [TIMEZONE]]
                          [--email_address [EMAIL_ADDRESS]]
                          recruiter_company recruiter_name recruiter_email

Automates sending emails to recruiters

positional arguments:
  recruiter_company     The company name of the recruiter
  recruiter_name        The full name of the recruiter
  recruiter_email       The email address of the recruiter

options:
  -h, --help            show this help message and exit
  --subject [SUBJECT]   The subject of the email message as a string template env: EMAIL_SUBJECT
  --message_body_path [MESSAGE_BODY_PATH]
                        The path to the message body template. env: MESSAGE_BODY_PATH
  --attachment_path [ATTACHMENT_PATH]
                        The path to the attachment file, if this is provided, attachment_name must also be provided env: ATTACHMENT_PATH
  --attachment_name [ATTACHMENT_NAME]
                        The name of the attachment file env: ATTACHMENT_NAME
  --schedule            Whether the email should be tracked or not. env ENABLE_STREAK_SCHEDULING. If set, the streak token must be provided via env
                        variable STREAK_TOKEN
  --schedule_csv_path [SCHEDULE_CSV_PATH]
                        CSV to use for scheduling the emails env: SCHEDULE_CSV_PATH
  --timezone [TIMEZONE]
                        The timezone to use for scheduling emails env: TIMEZONE Note: the argument tracked needs to be passed for this to be used
  --email_address [EMAIL_ADDRESS]
                        The email address to use in streak scheduling emails env: STREAK_EMAIL_ADDRESS If not provided, the email address of the
                        authenticated user will be used Note: the argument tracked needs to be passed for this to be used
```

## Schedule Emails
To enable scheduling emails you need to set the `--schedule` flag. You also need to provide the `--schedule_csv_path` flag which is the path to the CSV file which contains the schedule information. The CSV file should have the following columns:
- `DAY`: An integer from 0 to 6 representing the day of the week where 0 is Monday and 6 is Sunday.
- `START_TIME`: The start time of the email in the format `HH:MM`. 24-hour format.
- `END_TIME`: The end time of the email in the format `HH:MM`. 24-hour format.

For example:
```csv
DAY,START_TIME,END_TIME
0, 10:00, 11:00
0, 14:00, 14:30
1, 10:00, 11:00
1, 14:00, 14:30
2, 10:00, 11:00
2, 14:00, 14:30
3, 10:00, 11:00
3, 14:00, 14:30
4, 10:00, 11:00
```
The script will send the email to the recruiter at a random time in the earliest possible range. See the following cases:
1. If it is Monday 9:15 AM we should send email at a random time between 10:00 AM and 11:00 AM
2. If it is Monday 10:30 AM we should send email right now since the time is between 10:00 AM and 11:00 AM
3. If it is Monday 13:00 PM we should send email at a random time between 14:00 PM and 14:30 PM
4. If it is Monday 15:00 PM we should send email at a random time between 10:00 AM and 11:00 AM on Tuesday
5. If it is Friday 13:00 PM we should send email at a random time between 10:00 AM and 11:00 AM on Monday

I like to do this because I can send emails at the optimal time when recruiters are most likely to read them. I also like to send emails at the beginning of the day so that they are at the top of the recruiter's inbox.

You also need to provide `STREAK_TOKEN` via environment variable, you can get this by inspecting the network requests when you schedule an email in Streak. Look for the network request to `https://api.streak.com/api/v2/sendlaters` and copy the `Authorization` header value without the `Bearer` prefix.

You can also set the `--timezone` flag to specify the timezone to use for scheduling emails. The default is `UTC`.

# Future

I created this just to help me with my job search. I'm not really planning on adding any new features. However, if you have any suggestions or find any bugs feel free to open an issue or a pull request. The only improvement I can think of is to add a feature to schedule the emails to be sent later natively without stripe. This would require significant engineering effort since the project would have to maintain a DB of scheduled emails and send the emails on time. Adding additional template variables would also be a nice feature to have.
