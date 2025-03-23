"""Utilities for interacting with the Streak API."""

import datetime
import logging
from typing import NamedTuple

import requests

logger = logging.getLogger(__name__)
headers = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "authorization": "Bearer ",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://mail.google.com",
    "priority": "u=1, i",
    "referer": "https://mail.google.com/",
    "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    "sec-ch-ua-arch": '"arm"',
    "sec-ch-ua-bitness": '"64"',
    "sec-ch-ua-form-factors": '"Desktop"',
    "sec-ch-ua-full-version": '"134.0.6998.118"',
    "sec-ch-ua-full-version-list": '"Chromium";v="134.0.6998.118", "Not:A-Brand";v="24.0.0.0", "Google Chrome";v="134.0.6998.118"',  # noqa: E501
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": '""',
    "sec-ch-ua-platform": '"macOS"',
    "sec-ch-ua-platform-version": '"13.6.3"',
    "sec-ch-ua-wow64": "?0",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",  # noqa: E501
    "x-streak-web-client": "true",
    "x-streak-web-extension-id": "pnnfemgpilpdaojpnkjdgfgbnnjojfik",
    "x-streak-web-extension-version": "6.98",
    "x-streak-web-retry-count": "0",
}

params = {
    "email": "rahul.vaidun@gmail.com",
}


class StreakSendLaterConfig(NamedTuple):
    """Data fields for the Streak send later configuration."""

    token: str
    to_address: str
    subject: str
    thread_id: str
    draft_id: str
    send_date: datetime.datetime
    is_tracked: bool


def schedule_send_later(
    config: StreakSendLaterConfig,
) -> requests.Response:
    """Schedule an email to be sent later using Streak."""
    headers["authorization"] = f"Bearer {config.token}"
    # convert config.send_date to UTC
    send_date = config.send_date.astimezone(datetime.UTC)
    data = {
        "threadId": config.thread_id,
        "draftId": config.draft_id,
        "sendDate": str(int(send_date.timestamp()) * 1000),
        "subject": config.subject,
        "sendLaterType": "NEW_MESSAGE",
        "isTracked": str(config.is_tracked).lower(),
        "shouldBox": "false",
        "snippetKeyList": "[]",
        "toAddresses": f'["{config.to_address}"]',
    }
    response = requests.post(
        "https://api.streak.com/api/v2/sendlaters",
        params=params,
        headers=headers,
        data=data,
        timeout=10,
    )
    if not response.ok:
        logger.error("Failed to schedule email to be sent later")
        logger.error(response.text)
        return False
    logger.info("Email scheduled to be sent at %s", config.send_date)
    return True
