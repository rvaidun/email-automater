"""Shared argument parsing for email automation scripts."""

import argparse
import os
from enum import Enum

from dotenv import load_dotenv

from utils.funcs import str_to_bool

load_dotenv()


class EnvironmentVariables(Enum):
    """Environment variables used across email automation scripts."""

    # Common variables
    EMAIL_SUBJECT = "EMAIL_SUBJECT"
    MESSAGE_BODY_PATH = "MESSAGE_BODY_PATH"
    TIMEZONE = "TIMEZONE"
    STREAK_TOKEN = "STREAK_TOKEN"  # noqa: S105
    STREAK_EMAIL_ADDRESS = "STREAK_EMAIL_ADDRESS"
    SCHEDULE_CSV_PATH = "SCHEDULE_CSV_PATH"
    ENABLE_STREAK_SCHEDULING = "ENABLE_STREAK_SCHEDULING"

    # Follow-up specific variables
    FOLLOWUP_BODY_PATH = "FOLLOWUP_BODY_PATH"
    FOLLOWUP_SUBJECT = "FOLLOWUP_SUBJECT"
    FOLLOWUP_DB_PATH = "FOLLOWUP_DB_PATH"
    FOLLOWUP_WAIT_DAYS = "FOLLOWUP_WAIT_DAYS"
    ENABLE_FOLLOWUP = "ENABLE_FOLLOWUP"

    # Initial email specific variables
    ATTACHMENT_PATH = "ATTACHMENT_PATH"
    ATTACHMENT_NAME = "ATTACHMENT_NAME"


def get_arg_or_env(
    arg_value: str | None,
    env_var: EnvironmentVariables,
    *,
    required: bool = False,
    default: str | None = None,
) -> str | None:
    """
    Get value from argument or environment variable, prioritizing argument.

    Args:
        arg_value: The value from command line argument
        env_var: The environment variable to check
        required: Whether this value is required
        default: Default value to use if neither arg nor env var is set

    Returns:
        The value from arg, env var, or default, in that order of precedence

    Raises:
        ValueError: If required is True and no value is found

    """
    if arg_value is not None:
        return arg_value
    value = os.getenv(env_var.value)
    if value is not None:
        return value
    if required:
        s = f"Missing required argument or environment variable: {env_var.value}"
        raise ValueError(s)
    return default


def get_bool_arg_or_env(
    arg_value: bool | None,
    env_var: EnvironmentVariables,
) -> bool:
    """
    Get boolean value from argument or environment variable prioritizing argument.

    Args:
        arg_value: The value from command line argument (can be None)
        env_var: The environment variable to check

    Returns:
        True if arg_value is True or env_var is set to a truthy value
        False if arg_value is False or env_var is set to a falsy value
        The value from env_var if arg_value is None and env_var is set

    """
    if arg_value is not None:
        return arg_value
    value = os.getenv(env_var.value)
    if value is None:
        return False
    return str_to_bool(value)


def add_common_email_args(parser: argparse.ArgumentParser) -> None:
    """Add common email arguments to the parser."""
    parser.add_argument(
        "-s",
        "--subject",
        type=str,
        help=f"The subject of the email message as a string template env: \
            {EnvironmentVariables.EMAIL_SUBJECT.value}",
        nargs="?",
    )
    parser.add_argument(
        "-m",
        "--message_body_path",
        type=str,
        help=f"The path to the message body template. env: \
            {EnvironmentVariables.MESSAGE_BODY_PATH.value}",
        nargs="?",
    )
    parser.add_argument(
        "-tz",
        "--timezone",
        type=str,
        help=f"The timezone to use for scheduling emails (America/New_York) env:\
            {EnvironmentVariables.TIMEZONE.value} \
            This is used to determine the time range so it should be the recipient's \
            timezone.",
        nargs="?",
    )
    parser.add_argument(
        "-sch",
        "--schedule",
        help=f"Whether the email should be tracked or not. env \
            {EnvironmentVariables.ENABLE_STREAK_SCHEDULING.value}. \
            If set, the streak token must be provided via env variable \
            {EnvironmentVariables.STREAK_TOKEN.value}",
        action="store_const",
        const=True,
        default=None,
    )
    parser.add_argument(
        "-scsv",
        "--schedule_csv_path",
        type=str,
        help=f"CSV to use for scheduling the emails \
            env: {EnvironmentVariables.SCHEDULE_CSV_PATH.value}. \
            Note: the argument scheduled needs to be passed for this to be used",
        nargs="?",
    )
    parser.add_argument(
        "-e",
        "--email_address",
        type=str,
        help=f"The email address to use in streak scheduling emails env: \
            {EnvironmentVariables.STREAK_EMAIL_ADDRESS.value} \
            If not provided, the email address of the authenticated user will be used. \
            Note: the argument scheduled needs to be passed for this to be used",
        nargs="?",
    )
    parser.add_argument(
        "-t",
        "--token_path",
        type=str,
        help="The path to the token.json file. Defaults to token.json",
        nargs="?",
        default="token.json",
    )
    parser.add_argument(
        "-fd",
        "--followup_db_path",
        type=str,
        help=f"The path to the follow-up database file env: \
            {EnvironmentVariables.FOLLOWUP_DB_PATH.value}",
        nargs="?",
    )


def add_initial_email_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments specific to initial email sending."""
    parser.add_argument(
        "recruiter_company", type=str, help="The company name of the recruiter"
    )
    parser.add_argument(
        "recruiter_name", type=str, help="The full name of the recruiter"
    )
    parser.add_argument(
        "recruiter_email", type=str, help="The email address of the recruiter"
    )
    parser.add_argument(
        "-ap",
        "--attachment_path",
        type=str,
        help=f"The path to the attachment file, if this is provided, attachment_name \
            must also be provided env: {EnvironmentVariables.ATTACHMENT_PATH.value}",
        nargs="?",
    )
    parser.add_argument(
        "-an",
        "--attachment_name",
        type=str,
        help=f"The name of the attachment file env: \
            {EnvironmentVariables.ATTACHMENT_NAME.value}",
        nargs="?",
    )
    parser.add_argument(
        "-f",
        "--followup",
        help=f"Whether to enable automatic follow-up for this email. env: \
            {EnvironmentVariables.ENABLE_FOLLOWUP.value}",
        action="store_const",
        const=True,
        default=None,
    )
    parser.add_argument(
        "-fw",
        "--followup_wait_days",
        type=int,
        help=f"Number of days to wait before sending follow-up env: \
            {EnvironmentVariables.FOLLOWUP_WAIT_DAYS.value}",
        nargs="?",
    )


def add_followup_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments specific to follow-up email sending."""
    parser.add_argument(
        "-fb",
        "--followup_body_path",
        type=str,
        help=f"The path to the follow-up message body template. env: \
            {EnvironmentVariables.FOLLOWUP_BODY_PATH.value}",
        nargs="?",
    )
    parser.add_argument(
        "-fs",
        "--followup_subject",
        type=str,
        help=f"The subject of the follow-up email message as a string template env: \
            {EnvironmentVariables.FOLLOWUP_SUBJECT.value}",
        nargs="?",
    )
