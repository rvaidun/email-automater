"""Utility to set up automatic cron jobs for follow-up emails."""

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

def get_working_directory():
    """Get the absolute path of the current working directory."""
    return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def setup_cron_job():
    """
    Set up a cron job to run the follow-up script daily.
    
    Returns:
        bool: True if the cron job was set up successfully, False otherwise
    """
    system = platform.system()
    
    if system not in ["Darwin", "Linux"]:
        logger.warning("Automatic cron job setup is only supported on macOS and Linux")
        logger.info("To set up follow-ups on Windows, use Task Scheduler:")
        logger.info("1. Open Task Scheduler")
        logger.info("2. Create Basic Task > Daily > Start a program")
        logger.info(f"3. Add the path to run_followups.sh or create a batch file equivalent")
        return False
    
    # Get the full path to run_followups.sh
    working_dir = get_working_directory()
    script_path = os.path.join(working_dir, "run_followups.sh")
    
    # Make sure the script is executable
    try:
        os.chmod(script_path, 0o755)
    except Exception as e:
        logger.error(f"Could not make follow-up script executable: {e}")
        return False
    
    # Create a cron job that runs at 10 AM daily
    cron_line = f"0 10 * * * cd {working_dir} && {script_path}\n"
    
    # Get existing crontab entries
    try:
        result = subprocess.run(
            ["crontab", "-l"], 
            capture_output=True, 
            text=True
        )
        existing_crontab = result.stdout
    except Exception:
        existing_crontab = ""
    
    # Check if the job already exists
    if cron_line in existing_crontab:
        logger.info("Cron job for follow-ups already exists")
        return True
    
    # Add the new job
    new_crontab = existing_crontab + cron_line
    
    # Write the new crontab
    try:
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(input=new_crontab)
        if process.returncode == 0:
            logger.info("Successfully set up cron job for daily follow-ups at 10 AM")
            return True
        else:
            logger.error(f"Failed to set up cron job: Process returned {process.returncode}")
            return False
    except Exception as e:
        logger.error(f"Failed to set up cron job: {e}")
        return False

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    success = setup_cron_job()
    if success:
        print("Cron job for follow-ups set up successfully")
        sys.exit(0)
    else:
        print("Failed to set up cron job for follow-ups")
        sys.exit(1) 