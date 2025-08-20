"""Unit tests for email argument parsing utilities."""

import os
from unittest.mock import patch

import pytest

from utils.email_args import (
    EnvironmentVariables,
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
        EnvironmentVariables.STREAK_TOKEN.value: "env_token",
        EnvironmentVariables.STREAK_EMAIL_ADDRESS.value: "env_email@example.com",
        EnvironmentVariables.SCHEDULE_CSV_PATH.value: "env_schedule.csv",
        EnvironmentVariables.ENABLE_STREAK_SCHEDULING.value: "true",
        EnvironmentVariables.ATTACHMENT_PATH.value: "env_attachment.pdf",
        EnvironmentVariables.ATTACHMENT_NAME.value: "env_attachment_name.pdf",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


def test_get_arg_or_env_with_arg():
    """Test getting value from argument."""
    value = get_arg_or_env("test_value", EnvironmentVariables.EMAIL_SUBJECT)
    assert value == "test_value"


def test_get_arg_or_env_with_env():
    """Test getting value from environment variable."""
    with patch.dict(
        os.environ, {EnvironmentVariables.EMAIL_SUBJECT.value: "test_value"}
    ):
        value = get_arg_or_env(None, EnvironmentVariables.EMAIL_SUBJECT)
        assert value == "test_value"


def test_get_arg_or_env_with_default():
    """Test default value when neither argument nor environment variable is set."""
    with patch.dict(os.environ, {}, clear=True):
        value = get_arg_or_env(
            None, EnvironmentVariables.EMAIL_SUBJECT, default="default_value"
        )
        assert value == "default_value"


def test_get_arg_or_env_required_missing():
    """Test value when required but neither argument nor environment variable is set."""
    with patch.dict(os.environ, {}, clear=True):  # noqa: SIM117
        with pytest.raises(
            ValueError,
            match=f"Missing required argument or environment variable: {EnvironmentVariables.EMAIL_SUBJECT.value}",  # noqa: E501
        ):
            get_arg_or_env(None, EnvironmentVariables.EMAIL_SUBJECT, required=True)


def test_get_bool_arg_or_env_true():
    """Test getting boolean value when true."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = True
        value = get_bool_arg_or_env(
            mock_args.test_arg, EnvironmentVariables.ENABLE_STREAK_SCHEDULING
        )
        assert value is True


def test_get_bool_arg_or_env_false():
    """Test getting boolean value when false."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = False
        value = get_bool_arg_or_env(
            mock_args.test_arg, EnvironmentVariables.ENABLE_STREAK_SCHEDULING
        )
        assert value is False


def test_get_bool_arg_or_env_env_true():
    """Test getting boolean value from environment variable when true."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(
            os.environ, {EnvironmentVariables.ENABLE_STREAK_SCHEDULING.value: "true"}
        ):
            value = get_bool_arg_or_env(
                mock_args.test_arg, EnvironmentVariables.ENABLE_STREAK_SCHEDULING
            )
            assert value is True


def test_get_bool_arg_or_env_env_false():
    """Test getting boolean value from environment variable when false."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(
            os.environ, {EnvironmentVariables.ENABLE_STREAK_SCHEDULING.value: "false"}
        ):
            value = get_bool_arg_or_env(
                mock_args.test_arg, EnvironmentVariables.ENABLE_STREAK_SCHEDULING
            )
            assert value is False


def test_get_bool_arg_or_env_invalid():
    """Test getting boolean value with invalid value."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(
            os.environ, {EnvironmentVariables.ENABLE_STREAK_SCHEDULING.value: "invalid"}
        ):
            value = get_bool_arg_or_env(
                mock_args.test_arg, EnvironmentVariables.ENABLE_STREAK_SCHEDULING
            )
            assert value is False


def test_get_bool_arg_or_env_missing():
    """Test get boolean value when neither argument nor environment variable is set."""
    with patch("argparse.Namespace") as mock_args:
        mock_args.test_arg = None
        with patch.dict(os.environ, {}, clear=True):
            value = get_bool_arg_or_env(
                mock_args.test_arg, EnvironmentVariables.ENABLE_STREAK_SCHEDULING
            )
            assert value is False
