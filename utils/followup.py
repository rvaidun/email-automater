"""Utility functions for managing email follow-ups."""

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

DB_PATH = "followup_db.json"
FOLLOWUP_WAIT_DAYS = 3  # Default wait time between follow-ups


def load_followup_db() -> Dict[str, List]:
    """Load the follow-up database from disk."""
    logger.debug("Loading follow-up database from %s", DB_PATH)
    if not os.path.exists(DB_PATH):
        logger.debug("Database file does not exist, creating empty database")
        return {"emails": []}
    
    with open(DB_PATH, "r") as f:
        data = json.load(f)
        logger.debug("Loaded database with %d email entries", len(data.get("emails", [])))
        return data


def save_followup_db(db: Dict) -> None:
    """Save the follow-up database to disk."""
    logger.debug("Saving follow-up database with %d email entries", len(db.get("emails", [])))
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=4)
    logger.debug("Database saved successfully")


def track_email(
    recruiter_email: str,
    recruiter_name: str,
    recruiter_company: str,
    thread_id: str,
    subject: str,
    followup_count: int = 0,
) -> None:
    """
    Add a sent email to the tracking database.
    
    Args:
        recruiter_email: Email address of the recipient
        recruiter_name: Name of the recipient
        recruiter_company: Company of the recipient
        thread_id: Gmail thread ID
        subject: Email subject
        followup_count: Number of follow-ups already sent
    """
    db = load_followup_db()
    
    # Check if this email already exists
    for email in db["emails"]:
        if email["recruiter_email"] == recruiter_email:
            # Update the existing entry
            email["thread_id"] = thread_id
            email["last_contact"] = datetime.datetime.now().isoformat()
            email["followup_count"] = followup_count
            save_followup_db(db)
            return
    
    # Add new email entry
    db["emails"].append({
        "recruiter_email": recruiter_email,
        "recruiter_name": recruiter_name,
        "recruiter_company": recruiter_company,
        "thread_id": thread_id,
        "subject": subject,
        "initial_contact": datetime.datetime.now().isoformat(),
        "last_contact": datetime.datetime.now().isoformat(),
        "followup_count": followup_count,
        "next_followup": (datetime.datetime.now() + 
                          datetime.timedelta(days=FOLLOWUP_WAIT_DAYS)).isoformat()
    })
    
    save_followup_db(db)
    logger.info(f"Tracked email to {recruiter_email} for follow-up")


def get_pending_followups() -> List[Dict[str, Any]]:
    """
    Get all emails that are due for a follow-up.
    
    Returns:
        List of email entries that need follow-up
    """
    db = load_followup_db()
    now = datetime.datetime.now().isoformat()
    
    return [
        email for email in db["emails"] 
        if email.get("next_followup") and email["next_followup"] <= now
        and email["followup_count"] < 2  # Limit to 2 follow-ups
    ]


def update_followup_status(
    recruiter_email: str, 
    increment_count: bool = True
) -> None:
    """
    Update the follow-up status for an email.
    
    Args:
        recruiter_email: Email address to update
        increment_count: Whether to increment the follow-up count
    """
    db = load_followup_db()
    
    for email in db["emails"]:
        if email["recruiter_email"] == recruiter_email:
            if increment_count:
                email["followup_count"] += 1
            
            email["last_contact"] = datetime.datetime.now().isoformat()
            email["next_followup"] = (
                datetime.datetime.now() + 
                datetime.timedelta(days=FOLLOWUP_WAIT_DAYS)
            ).isoformat()
            
            save_followup_db(db)
            return
    
    logger.warning(f"Email to {recruiter_email} not found in tracking database") 