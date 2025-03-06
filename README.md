# Automate Recruiter Emails
This is a simple python script that automates the process of sending emails to recruiters. It uses the gmail API to draft emails to recruiters. Currently I use it in conjunction with [Streak CRM](https://www.streak.com/) to manage my job search. I write the draft using this script and then later schedule the email to be sent later manually using the schedule message to send feature which streak has. Gmail also has scheduling built in but I prefer to use Streak since they also provide somewhat accurate read receipts to see when emails have been read. Unfortunately, Google Gmail API does not support schedule sending natively. See a demo [here](https://youtu.be/Ef5i8DboJP4).

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
EMAIL_SUBJECT=I would like to work at $recruiter_company
MESSAGE_BODY_PATH=email_template.txt
ATTACHMENT_PATH=resume.pdf
ATTACHMENT_NAME=FirstName_LastName_Resume.pdf
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

```bash
(venv) ➜  emailer git:(main) ✗ ./automate_emails.py -h                                
usage: automate_emails.py [-h] recruiter_company recruiter_name recruiter_email

Automates sending emails to recruiters

positional arguments:
  recruiter_company  The company name of the recruiter
  recruiter_name     The full name of the recruiter
  recruiter_email    The email address of the recruiter

options:
  -h, --help         show this help message and exit
(venv) ➜  emailer git:(main) ✗ 
```

# Future

I created this just to help me with my job search. I'm not really planning on adding any new features. However, if you have any suggestions or find any bugs feel free to open an issue or a pull request. The only improvement I can think of is to add a feature to schedule the emails to be sent later and adding more template variables.
