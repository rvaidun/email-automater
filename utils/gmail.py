"""Helpers for interacting with the Gmail API."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)
SCOPES = ["https://mail.google.com/"]

if TYPE_CHECKING:
    from email.message import EmailMessage


class GmailAPI:
    """A class to interact with the Gmail API."""

    def __init__(self) -> None:
        """Initialize the GmailAPI object."""
        self.service = None

    def login(
        self, token: dict | None = None, credentials_path: str | None = None
    ) -> Credentials:
        """
        Log in to the Gmail API and sets self.service to the authenticated service.

        If credentials_path is provided token will be ignored
        Args:
            token (dict): The token information to use for authentication.
                Defaults to None.
            credentials_path (str): The path to the credentials file.
                Defaults to None
            If None, the user will be prompted to log in.

        Returns:
            Credentials: The credentials to use for authentication for next run.


        """
        creds = None
        if credentials_path is not None:
            logger.debug("Using credentials from %s", credentials_path)
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        elif token is not None:
            logger.debug("Using token for authentication")
            creds = Credentials.from_authorized_user_info(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds:
            logger.error(
                "No credentials provided. Please pass either token dict or \
                    credentials path."
            )
            msg = "No credentials provided."
            raise ValueError(msg)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                logger.debug("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                logger.error("No valid credentials available.")
                msg = "No valid credentials available."
                raise ValueError(msg)
        self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return creds

    def _build_message_payload(
        self,
        message: EmailMessage,
        *,
        thread_id: str | None = None,
    ) -> dict[str, str]:
        """Build the encoded message payload accepted by Gmail."""
        payload = {
            "raw": base64.urlsafe_b64encode(message.as_bytes()).decode(),
        }
        if thread_id:
            payload["threadId"] = thread_id
        return payload

    def save_draft(
        self,
        message: EmailMessage,
        *,
        thread_id: str | None = None,
    ) -> dict | bool:
        """
        Save a draft message in Gmail.

        Args:
            message (EmailMessage): The message to save as a draft.
            thread_id (str | None): Optional Gmail thread identifier.

        Returns:
            dict: True if the draft was saved successfully, False otherwise.

        """
        try:
            draft_message = {
                "message": self._build_message_payload(message, thread_id=thread_id)
            }
            draft = (
                self.service.users()
                .drafts()
                .create(userId="me", body=draft_message)
                .execute()
            )
            logger.debug("Draft: %s", draft)
            logger.debug("Draft saved")
        except HttpError:
            logger.exception("An error occurred saving the draft")
            return False
        return draft

    def send_now(
        self,
        message: EmailMessage,
        *,
        thread_id: str | None = None,
    ) -> dict | bool:
        """
        Send a message immediately using the Gmail API.

        Args:
            message (EmailMessage): The message to send.
            thread_id (str | None): Optional Gmail thread identifier.

        Returns:
            dict: True if the message was sent successfully, False otherwise.

        """
        try:
            sent_message = (
                self.service.users()
                .messages()
                .send(
                    userId="me",
                    body=self._build_message_payload(message, thread_id=thread_id),
                )
                .execute()
            )

            logger.info(
                "Message id: %s \nMessage: %s", sent_message["id"], sent_message
            )
        except HttpError:
            logger.exception("An error occurred sending the message")
            return False
        return sent_message

    def get_current_user(self) -> dict:
        """
        Get the current user's information.

        Returns:
            dict: The current user's information.

        """
        return self.service.users().getProfile(userId="me").execute()

    def get_thread(
        self,
        thread_id: str,
        *,
        message_format: str = "full",
    ) -> dict | bool:
        """Fetch a Gmail thread."""
        try:
            return (
                self.service.users()
                .threads()
                .get(userId="me", id=thread_id, format=message_format)
                .execute()
            )
        except HttpError:
            logger.exception("An error occurred fetching thread %s", thread_id)
            return False
