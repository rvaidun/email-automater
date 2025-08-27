# Automate Recruiter Emails
This is a simple python script that automates the process of sending emails to recruiters. It uses the gmail API to draft emails to recruiters. Currently I use it in conjunction with [Streak CRM](https://www.streak.com/) to manage my job search. I write the draft using this script and then later schedule the email to be sent later manually using the schedule message to send feature which streak has. Gmail also has scheduling built in but I prefer to use Streak since they also provide somewhat accurate read receipts to see when emails have been read. Unfortunately, Google Gmail API does not support schedule sending natively. Instead I reverse engineered the Streak API to schedule the draft emails to be sent later. 
See a demo [here](https://youtu.be/Ef5i8DboJP4).

# Installation
1. Clone the repository
2. Create a virtual environment `python3 -m venv venv`
3. Activate the virtual environment `source venv/bin/activate`
4. Install the requirements `pip install -r requirements.txt`

Steps 2-4 can be skipped if using [uv](https://github.com/astral-sh/uv) package manager.
Simply run `uv sync` and all packages will be installed in virtual environment.


5. Follow the instructions [here](https://developers.google.com/gmail/api/quickstart/python) to enable the Gmail API and download the `credentials.json` file. Save the file in the root directory of the repository.

The `token.json` file will not exist yet if you haven't run the script yet. The `token.json` file stores the login credentials required to access your Google account so you don't have to relogin each time you run the script. If the file does not exist you will be prompted to login to Google using standard Oauth2 flow.

# Usage

```
usage: automate_emails.py [-h] [-ap [ATTACHMENT_PATH]] [-an [ATTACHMENT_NAME]]
                          [-s [SUBJECT]] [-m [MESSAGE_BODY_PATH]]
                          [-tz [TIMEZONE]] [-sch] [-scsv [SCHEDULE_CSV_PATH]]
                          [-e [EMAIL_ADDRESS]] [-t [TOKEN_PATH]]
                          [-c [CREDS_PATH]]
                          recruiter_company recruiter_name recruiter_email

Automates sending emails to recruiters

positional arguments:
  recruiter_company     The company name of the recruiter
  recruiter_name        The full name of the recruiter
  recruiter_email       The email address of the recruiter

options:
  -h, --help            show this help message and exit
  -ap, --attachment_path [ATTACHMENT_PATH]
                        The path to the attachment file, if this is provided,
                        attachment_name must also be provided. Overrides the
                        ATTACHMENT_PATH environment variable
  -an, --attachment_name [ATTACHMENT_NAME]
                        The name of the attachment file. Overrides the
                        ATTACHMENT_NAME environment variable
  -s, --subject [SUBJECT]
                        The subject of the email message as a string template.
                        Overrides the EMAIL_SUBJECT environment variable.
  -m, --message_body_path [MESSAGE_BODY_PATH]
                        The path to the message body template. Overrides the
                        MESSAGE_BODY_PATH environment variable.
  -tz, --timezone [TIMEZONE]
                        The timezone to use for scheduling emails
                        (America/New_York). Overrides the TIMEZONE environment
                        variable. This is used to determine the time range so
                        it should be the recipient's timezone.
  -sch, --schedule      Whether the email should be tracked or not. Overrides
                        the ENABLE_STREAK_SCHEDULING. If set, the streak token
                        must be provided via env variable STREAK_TOKEN
  -scsv, --schedule_csv_path [SCHEDULE_CSV_PATH]
                        CSV to use for scheduling the emails. Overrides the
                        SCHEDULE_CSV_PATH environment variable. Note:
                        --schedule needs to be enabled for this to be used
  -e, --email_address [EMAIL_ADDRESS]
                        The email address to send to the Streak API. Overrides
                        the STREAK_EMAIL_ADDRESS. If not provided, the email
                        address of the authenticated user will be used. Note:
                        --schedule needs to be enabled for this to be used
  -t, --token_path [TOKEN_PATH]
                        The path to the token.json file. The default value is
                        token.json. Overrides the TOKEN_PATH environment
                        variable
  -c, --creds_path [CREDS_PATH]
                        The path to the credentials.json file. The default
                        value is credentials.json. Overrides the CREDS_PATH
                        environment variable

```
## Templating
Both `EMAIL_SUBJECT` and `MESSAGE_BODY_PATH` support templating. The `automate-emails.py` script uses [Python's templating syntax](https://docs.python.org/3.3/tutorial/stdlib2.html#templating) to replace the values represented by these environment variables. The rules of templating are as follows:
- `EMAIL_SUBJECT`: The script will replace the `$recruiter_company` templating variable with the value provided in the command line arguments.
The subject could look like `Interested in $recruiter_company`

- `MESSAGE_BODY_PATH`: The name of the file to process. The file should use Python's templating syntax to have the following variables: `recruiter_name`, `recruiter_company`. The script will replace these variables with the values provided in the command line arguments. For example, the `email_template.txt` file could look like this:
```
Dear $recruiter_name,

I am interested in the position at $recruiter_company.
```

## Sample Environment Variables
The following environment variables are set in my personal environment
```
# Email stuff
EMAIL_SUBJECT=I would like to work at $recruiter_company
MESSAGE_BODY_PATH=email_template.html
ATTACHMENT_PATH=resume.pdf
ATTACHMENT_NAME=FirstName_LastName_Resume.pdf

# Streak stuff
TIMEZONE=America/Los_Angeles
STREAK_TOKEN=classic:C/THIS+IS+/NOT/A/REAL TOKEN
ENABLE_STREAK_SCHEDULING=True
SCHEDULE_CSV_PATH=scheduler.csv
STREAK_EMAIL_ADDRESS=first.last@gmail.com

```

## Schedule Emails
To enable scheduling emails you need to set `ENABLE_STREAK_SCHEDULING`. You also need to provide the `SCHEDULE_CSV_PATH` which is the path to the CSV file which contains the schedule information. The CSV file should have the following columns:
- `DAY`: An integer from 0 to 6 representing the day of the week where 0 is Monday and 6 is Sunday.
- `START_TIME`: The start time of the time range emails should be sent in the format `HH:MM`. 24-hour format.
- `END_TIME`: The end time of the time range emails should be sent in the format `HH:MM`. 24-hour format.

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
The script will send the email to the recruiter at a random time in the earliest possible range. See the following cases which show how the emails will get scheduled if you use the above CSV:
1. If it is Monday 9:15 AM the email will be scheduled for a random time between 10:00 AM and 11:00 AM
2. If it is Monday 10:30 AM the email will be sent now since the time is between 10:00 AM and 11:00 AM
3. If it is Monday 13:00 PM the email will be scheduled for a random time between 14:00 PM and 14:30 PM
4. If it is Monday 15:00 PM the email will be scheduled for a random time between 10:00 AM and 11:00 AM on Tuesday
5. If it is Friday 13:00 PM the email will be scheduled for a random time between 10:00 AM and 11:00 AM on Monday

I like to do this because I can send emails at the optimal time when recruiters are most likely to read them. Sending emails at 10-11 and 2-3 is generally the most optimal based on my research. I also like to send emails at the beginning of the day so that they are at the top of the recruiter's inbox.

You also need to provide `STREAK_TOKEN` via environment variable, you can get this by inspecting the network requests when you schedule an email in Streak. Look for the network request to `https://api.streak.com/api/v2/sendlaters` and copy the `Authorization` header value without the `Bearer` prefix.

You can also set `TIMEZONE` to specify the timezone to use for scheduling emails. The default is `UTC`. This should be the receipients timezone
# Future

I created this just to help me with my job search. I'm not really planning on adding any new features. However, if you have any suggestions or find any bugs feel free to open an issue or a pull request. The only improvement I can think of is to add a feature to schedule the emails to be sent later natively without stripe. This would require significant engineering effort since the project would have to maintain a DB of scheduled emails and send the emails on time. Adding additional template variables would also be a nice feature to have.