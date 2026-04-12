"""Tests for recruiter name formatting helpers."""

from pathlib import Path

from automate_emails import process_string
from utils.email_content import split_inline_subject
from utils.recruiter_names import recruiter_first_name, recruiter_template_context


def test_recruiter_first_name_returns_first_token():
    """Normal recruiter names should render with the first name only."""
    assert recruiter_first_name("Erika Gonzalez") == "Erika"


def test_recruiter_first_name_skips_salutations():
    """Greetings should not include common honorific prefixes."""
    assert recruiter_first_name("Dr. Karishma Borah") == "Karishma"


def test_recruiter_template_context_supports_subject_aliases():
    """Template context should expose both company and recruiter firstname aliases."""
    context = recruiter_template_context(
        recruiter_company="Stripe",
        recruiter_name="Karishma Borah",
    )

    assert context["company"] == "Stripe"
    assert context["recruiter_company"] == "Stripe"
    assert context["recruiter_name"] == "Karishma"
    assert context["recruiterfirstname"] == "Karishma"


def test_email1_template_greets_with_first_name_only():
    """The live initial email template should greet with first name only."""
    context = recruiter_template_context(
        recruiter_company="Stripe",
        recruiter_name="Erica Gonzalez",
    )
    rendered = process_string(Path("email1.md").read_text(), **context)
    _, body = split_inline_subject(rendered)

    assert "Hi Erica," in body
    assert "Hi Erica Gonzalez," not in body
