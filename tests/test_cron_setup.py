"""Unit tests for the cron_setup module."""

import subprocess
from pathlib import Path, PosixPath
from unittest.mock import MagicMock, patch

import pytest

from utils.cron_setup import get_working_directory, setup_cron_job


@pytest.fixture
def mock_script_path(tmp_path):
    """Create a temporary script path for testing."""
    script_path = tmp_path / "run_followups.sh"
    script_path.touch()
    return script_path


@pytest.fixture
def mock_working_dir(tmp_path):
    """Create a temporary working directory for testing."""
    return tmp_path


def test_get_working_directory():
    """Test that get_working_directory returns the correct path."""
    with patch("utils.cron_setup.Path") as mock_path:
        mock_path.return_value.resolve.return_value.parent.parent = Path("/test/path")
        result = get_working_directory()
        assert result == PosixPath("/test/path")


@pytest.mark.parametrize("system", ["Windows", "FreeBSD"])
def test_unsupported_platform(system):
    """Test that setup_cron_job returns False for unsupported platforms."""
    with patch("platform.system", return_value=system):
        result = setup_cron_job()
        assert result is False


@pytest.mark.parametrize("system", ["Darwin", "Linux"])
def test_supported_platform(system, mock_script_path, mock_working_dir):
    """Test cron job setup on supported platforms."""
    with (
        patch("platform.system", return_value=system),
        patch(
            "utils.cron_setup.get_working_directory",
            return_value=PosixPath(mock_working_dir),
        ),
        patch("utils.cron_setup.Path") as mock_path,
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen") as mock_popen,
    ):
        # Mock the script path
        mock_path.return_value = mock_script_path
        # Mock crontab listing (empty)
        mock_run.return_value = subprocess.CompletedProcess(
            args=["crontab", "-l"], returncode=0, stdout="", stderr=""
        )

        # Mock crontab writing process
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("", "")
        mock_popen.return_value = mock_process

        # Run the function
        result = setup_cron_job()

        # Verify results
        assert result is True
        assert mock_script_path.stat().st_mode & 0o755 == 0o755  # noqa: PLR2004 check executable

        # Verify crontab listing was called
        mock_run.assert_called_once_with(
            ["/usr/bin/crontab", "-l"], capture_output=True, text=True, check=False
        )

        # Verify crontab writing was called with correct arguments
        mock_popen.assert_called_once_with(
            ["/usr/bin/crontab", "-"], stdin=subprocess.PIPE, text=True
        )

        # Verify the input data was passed correctly
        mock_process.communicate.assert_called_once()
        input_data = mock_process.communicate.call_args[1]["input"]
        expected_cron = f"0 10 * * * cd {mock_working_dir} && {mock_script_path}\n"
        assert input_data == expected_cron


def test_existing_cron_job(mock_script_path, mock_working_dir):
    """Test that setup_cron_job handles existing cron jobs correctly."""
    with (
        patch("platform.system", return_value="Darwin"),
        patch(
            "utils.cron_setup.get_working_directory",
            return_value=PosixPath(mock_working_dir),
        ),
        patch("utils.cron_setup.Path") as mock_path,
        patch("subprocess.run") as mock_run,
    ):
        # Mock the script path
        mock_path.return_value = mock_script_path

        # Mock crontab listing with existing job
        existing_cron = f"0 10 * * * cd {mock_working_dir} && {mock_script_path}\n"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["crontab", "-l"], returncode=0, stdout=existing_cron, stderr=""
        )

        result = setup_cron_job()
        assert result is True
        mock_run.assert_called_once()


def test_crontab_write_error(mock_script_path, mock_working_dir):
    """Test handling of crontab write errors."""
    with (
        patch("platform.system", return_value="Darwin"),
        patch(
            "utils.cron_setup.get_working_directory",
            return_value=PosixPath(mock_working_dir),
        ),
        patch("utils.cron_setup.Path") as mock_path,
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen") as mock_popen,
    ):
        # Mock the script path
        mock_path.return_value = mock_script_path

        # Mock successful crontab listing
        mock_run.return_value = subprocess.CompletedProcess(
            args=["crontab", "-l"], returncode=0, stdout="", stderr=""
        )

        # Mock crontab write error
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_stdin = MagicMock()
        mock_stdin.communicate.return_value = (b"", b"Error")
        mock_process.stdin = mock_stdin
        mock_popen.return_value = mock_process

        result = setup_cron_job()
        assert result is False
