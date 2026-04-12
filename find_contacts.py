"""Find recruiter contacts for companies using Apollo."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from dotenv import load_dotenv

from utils.apollo import ApolloClient, ApolloError
from utils.outreach_state import OutreachStateStore

load_dotenv()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Find recruiter contacts")
    parser.add_argument("companies", nargs="+", help="Company names to search")
    parser.add_argument("--limit", type=int, default=3, help="Contacts per company")
    parser.add_argument(
        "--apollo-api-key",
        type=str,
        help="Apollo API key. Falls back to APOLLO_API_KEY.",
    )
    parser.add_argument(
        "--state-path",
        type=str,
        default="state/outreach_state.json",
        help="Outreach state file",
    )
    parser.add_argument(
        "--allow-paid-apollo",
        action="store_true",
        help=(
            "Spend live Apollo credits from this command. Disabled by default "
            "to avoid accidental paid test runs."
        ),
    )
    return parser.parse_args()


def find_contacts_for_company(
    company_name: str,
    *,
    apollo_client: ApolloClient,
    state: OutreachStateStore | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Return enriched recruiter contacts for a single company."""
    organization, contacts = apollo_client.find_recruiter_contacts(
        company_name,
        limit=limit,
    )
    duplicate_count = 0
    filtered_contacts: list[dict[str, Any]] = []
    for contact in contacts:
        email = str(contact.get("email", "")).strip().lower()
        if state and email and state.has_contact(email):
            duplicate_count += 1
            continue
        filtered_contacts.append(contact)

    return {
        "company": company_name,
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "domain": organization.domain,
            "website_url": organization.website_url,
        }
        if organization
        else None,
        "contacts": filtered_contacts,
        "duplicates_skipped": duplicate_count,
    }


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    if not args.allow_paid_apollo:
        sys.stderr.write(
            "Refusing to spend Apollo credits from find_contacts.py without "
            "--allow-paid-apollo.\n"
        )
        return 2
    state = OutreachStateStore(args.state_path)
    client = ApolloClient(api_key=args.apollo_api_key)

    results: list[dict[str, Any]] = []
    for company in args.companies:
        try:
            results.append(
                find_contacts_for_company(
                    company,
                    apollo_client=client,
                    state=state,
                    limit=args.limit,
                )
            )
        except ApolloError as exc:
            results.append(
                {
                    "company": company,
                    "organization": None,
                    "contacts": [],
                    "duplicates_skipped": 0,
                    "error": str(exc),
                }
            )

    sys.stdout.write(f"{json.dumps(results, indent=2)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
