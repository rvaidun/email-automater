"""GmailAPI class to interact with the Gmail API."""

import base64
import logging
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://mail.google.com/"]


class GmailAPI:
    """A class to interact with the Gmail API."""

    def __init__(self) -> None:
        """Initialize the GmailAPI object."""

    def login(self, token: dict | None = None) -> Credentials:
        """
        Log in to the Gmail API and sets self.service to the authenticated service.

        Args:
            token (dict): The token information to use for authentication.
            Defaults to None.
            If None, the user will be prompted to log in.

        Returns:
            Credentials: The credentials to use for authentication for next run.


        """
        creds = None
        if token:
            creds = Credentials.from_authorized_user_info(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
        self.service = build(
            "gmail", "v1", credentials=creds, cache_discovery=False)
        return creds

    def save_draft(
        self,
        message: EmailMessage,
    ) -> dict | bool:
        """
        Save a draft message in Gmail.

        Args:
            message (EmailMessage): The message to save as a draft.

        Returns:
            dict: True if the draft was saved successfully, False otherwise.

        """
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        try:
            draft_message = {"message": {"raw": encoded_message}}
            draft = (
                self.service.users()
                .drafts()
                .create(userId="me", body=draft_message)
                .execute()
            )

            logger.info(
                "Draft id: %s\nDraft message: %s", draft["id"], draft["message"]
            )
        except HttpError:
            logger.exception("An error occurred saving the draft")
            return False
        return draft

    def send_now(
        self,
        message: EmailMessage,
    ) -> dict | bool:
        """
        Send a message immediately using the Gmail API.

        Args:
            message (EmailMessage): The message to send.

        Returns:
            dict: True if the message was sent successfully, False otherwise.

        """
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        try:
            sent_message = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": encoded_message})
                .execute()
            )

            logger.info(
                "Message id: %s\nMessage snippet: %s",
                sent_message["id"],
                sent_message["snippet"],
            )
        except HttpError:
            logger.exception("An error occurred sending the message")
            return False
        return sent_message
