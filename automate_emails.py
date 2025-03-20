#!/usr/bin/env python
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import argparse
from string import Template
import base64
from email.message import EmailMessage

from dotenv import load_dotenv
load_dotenv()


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://mail.google.com/"]


def get_gmail_service():
    """
    Return a gmail service object
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    service = build("gmail", "v1", credentials=creds)
    return service


def parse_args():
    parser = argparse.ArgumentParser(
        description="Automates sending emails to recruiters")
    parser.add_argument("recruiter_company", type=str,
                        help="The company name of the recruiter")
    parser.add_argument("recruiter_name", type=str,
                        help="The full name of the recruiter")

    parser.add_argument("recruiter_email", type=str,
                        help="The email address of the recruiter")
    parser.add_argument("--template_path", type=str,
                        help="The path to the attachment file", default=os.getenv("MESSAGE_BODY_PATH"), nargs='?')
    return parser.parse_args()


def process_file(filename, **kwargs):
    with open(filename, 'r') as file:
        file_contents = file.read()

    template = Template(file_contents)

    substituted_contents = template.substitute(**kwargs)

    return substituted_contents


def process_subject(s, **kwargs):
    template = Template(s)
    return template.substitute(**kwargs)


def save_draft(service, user_id, message_body, to_address=None, subject=None, attachment=None):
    message = EmailMessage()

    message.set_content(message_body, subtype='html')
    if attachment:
        with open(attachment, 'rb') as file:
            content = file.read()
            message.add_attachment(content, maintype='application',
                                   subtype='octet-stream', filename=os.getenv("ATTACHMENT_NAME", attachment))

    message['To'] = to_address
    message['Subject'] = subject

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        draft_message = {'message': {'raw': encoded_message}}
        draft = service.users().drafts().create(
            userId=user_id, body=draft_message).execute()
        print(f"Draft id: {draft['id']}\nDraft message: {draft['message']}")
        return draft
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


if __name__ == "__main__":
    args = parse_args()
    service = get_gmail_service()
    recruiter = args.recruiter_name
    recruiter_name = args.recruiter_name
    recruiter_company = args.recruiter_company
    recruiter_email = args.recruiter_email
    filename = args.template_path
    subject = os.getenv("EMAIL_SUBJECT")
    attachment = os.getenv("ATTACHMENT_PATH")
    email_contents = process_file(
        filename, recruiter_name=recruiter_name, recruiter_company=recruiter_company)
    subject = process_subject(subject, recruiter_company=recruiter_company)
    save_draft(service, 'me', email_contents, to_address=recruiter_email,
               subject=subject, attachment=attachment)
