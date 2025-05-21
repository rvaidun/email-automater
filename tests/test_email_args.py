"""Unit tests for email argument parsing utilities."""

import os
from unittest.mock import patch

import pytest

from utils.email_args import (
    EnvironmentVariables,
    add_common_email_args,
    add_followup_args,
    add_initial_email_args,
    get_arg_or_env,
    get_bool_arg_or_env,
)


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    env_vars = {
        EnvironmentVariables.EMAIL_SUBJECT.value: "env_subject",
        EnvironmentVariables.MESSAGE_BODY_PATH.value: "env_body.txt",
        EnvironmentVariables.TIMEZONE.value: "env_tz",
        EnvironmentVariables.STREAK_TOKEN.value: "env_token",  # noqa: S105
        EnvironmentVariables.STREAK_EMAIL_ADDRESS.value: "env_email@example.com",
        EnvironmentVariables.SCHEDULE_CSV_PATH.value: "env_schedule.csv",
        EnvironmentVariables.ENABLE_STREAK_SCHEDULING.value: "true",
        EnvironmentVariables.FOLLOWUP_BODY_PATH.value: "env_followup.txt",
        EnvironmentVariables.FOLLOWUP_SUBJECT.value: "env_followup_subject",
        EnvironmentVariables.FOLLOWUP_DB_PATH.value: "env_followup_db.json",
        EnvironmentVariables.FOLLOWUP_WAIT_DAYS.value: "5",
        EnvironmentVariables.ENABLE_FOLLOWUP.value: "true",
        EnvironmentVariables.ATTACHMENT_PATH.value: "env_attachment.pdf",
        EnvironmentVariables.ATTACHMENT_NAME.value: "env_attachment_name.pdf",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


def test_get_arg_or_env_with_arg():
    """Test getting value from argument."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = "test_value"
        value = get_arg_or_env(mock_args, "test_arg", "TEST_ENV")
        assert value == "test_value"


def test_get_arg_or_env_with_env():
    """Test getting value from environment variable."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(os.environ, {"TEST_ENV": "test_value"}):
            value = get_arg_or_env(mock_args, "test_arg", "TEST_ENV")
            assert value == "test_value"


def test_get_arg_or_env_with_default():
    """Test getting default value when neither argument nor environment variable is set."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(os.environ, {}, clear=True):
            value = get_arg_or_env(mock_args, "test_arg", "TEST_ENV", default="default_value")
            assert value == "default_value"


def test_get_arg_or_env_required_missing():
    """Test getting value when required but neither argument nor environment variable is set."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Required argument test_arg not provided"):
                get_arg_or_env(mock_args, "test_arg", "TEST_ENV", required=True)


def test_get_bool_arg_or_env_true():
    """Test getting boolean value when true."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = True
        value = get_bool_arg_or_env(mock_args, "test_arg", "TEST_ENV")
        assert value is True


def test_get_bool_arg_or_env_false():
    """Test getting boolean value when false."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = False
        value = get_bool_arg_or_env(mock_args, "test_arg", "TEST_ENV")
        assert value is False


def test_get_bool_arg_or_env_env_true():
    """Test getting boolean value from environment variable when true."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(os.environ, {"TEST_ENV": "true"}):
            value = get_bool_arg_or_env(mock_args, "test_arg", "TEST_ENV")
            assert value is True


def test_get_bool_arg_or_env_env_false():
    """Test getting boolean value from environment variable when false."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(os.environ, {"TEST_ENV": "false"}):
            value = get_bool_arg_or_env(mock_args, "test_arg", "TEST_ENV")
            assert value is False


def test_get_bool_arg_or_env_invalid():
    """Test getting boolean value with invalid value."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(os.environ, {"TEST_ENV": "invalid"}):
            value = get_bool_arg_or_env(mock_args, "test_arg", "TEST_ENV")
            assert value is False


def test_get_bool_arg_or_env_missing():
    """Test getting boolean value when neither argument nor environment variable is set."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(os.environ, {}, clear=True):
            value = get_bool_arg_or_env(mock_args, "test_arg", "TEST_ENV")
            assert value is False


def test_add_common_email_args():
    """Test adding common email arguments."""
    with patch("argparse.ArgumentParser") as mock_parser:
        add_common_email_args(mock_parser)
        mock_parser.add_argument.assert_any_call(
            "--email_address",
            help="Email address to send from",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--token_path",
            help="Path to the token file",
            default="token.json",
        )
        mock_parser.add_argument.assert_any_call(
            "--streak_token",
            help="Streak API token",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--streak_email_address",
            help="Email address associated with Streak",
            required=True,
        )


def test_add_initial_email_args():
    """Test adding initial email arguments."""
    with patch("argparse.ArgumentParser") as mock_parser:
        add_initial_email_args(mock_parser)
        mock_parser.add_argument.assert_any_call(
            "--recruiter_company",
            help="Recruiter's company name",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--recruiter_name",
            help="Recruiter's name",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--recruiter_email",
            help="Recruiter's email address",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--subject",
            help="Email subject",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--message_body_path",
            help="Path to the message body template file",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--attachment_path",
            help="Path to the attachment file",
        )
        mock_parser.add_argument.assert_any_call(
            "--attachment_name",
            help="Name to use for the attachment",
        )
        mock_parser.add_argument.assert_any_call(
            "--enable_followup",
            help="Enable automatic follow-up",
            action="store_true",
        )


def test_add_followup_args():
    """Test adding follow-up arguments."""
    with patch("argparse.ArgumentParser") as mock_parser:
        add_followup_args(mock_parser)
        mock_parser.add_argument.assert_any_call(
            "--followup_body_path",
            help="Path to the follow-up message body template file",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--followup_subject",
            help="Follow-up email subject",
            required=True,
        )
        mock_parser.add_argument.assert_any_call(
            "--timezone",
            help="Timezone for scheduling follow-ups",
            default="UTC",
        )
        mock_parser.add_argument.assert_any_call(
            "--followup_db_path",
            help="Path to the follow-up database file",
            default="followup_db.json",
        )
        mock_parser.add_argument.assert_any_call(
            "--followup_wait_days",
            help="Number of days to wait between follow-ups",
            type=int,
            default=7,
        ) 