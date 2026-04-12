"""Tests for job scraping helpers."""

from datetime import datetime
from zoneinfo import ZoneInfo

from scrape_jobs import (
    DIRECT_AIRTABLE_EMBED_URL,
    extract_airtable_embed_url,
    extract_companies_from_tesseract_tsv,
    parse_airtable_view_data,
    parse_listing_html,
)


def test_extract_airtable_embed_url_prefers_us_software_engineering():
    """The homepage parser should pick the US SWE Airtable embed."""
    homepage_html = """
    <h2 data-job-path="/ca/swe"
        airtable-link="https://airtable.com/embed/canada"
        short-link="swe">💻 Software Engineering</h2>
    <h2 data-job-path="/us/swe"
        airtable-link="https://airtable.com/embed/united-states"
        short-link="swe">💻 Software Engineering</h2>
    """

    assert (
        extract_airtable_embed_url(homepage_html)
        == "https://airtable.com/embed/united-states"
    )


def test_extract_airtable_embed_url_falls_back_to_direct_airtable_link():
    """The scraper should keep a working Airtable URL if homepage parsing fails."""
    assert extract_airtable_embed_url("<html></html>") == DIRECT_AIRTABLE_EMBED_URL


def test_parse_airtable_view_data_extracts_recent_unique_companies():
    """The Airtable parser should dedupe companies and keep only recent rows."""
    payload = {
        "data": {
            "table": {
                "columns": [
                    {"id": "title", "name": "Position Title"},
                    {"id": "date", "name": "Date"},
                    {"id": "apply", "name": "Apply"},
                    {"id": "company", "name": "Company"},
                ],
                "rows": [
                    {
                        "id": "row-1",
                        "createdTime": "2026-04-11T20:00:00.000Z",
                        "cellValuesByColumnId": {
                            "title": "Software Engineer",
                            "date": "2026-04-11",
                            "apply": {
                                "label": "Apply",
                                "url": "https://jobs.example/stripe",
                            },
                            "company": "Stripe",
                        },
                    },
                    {
                        "id": "row-2",
                        "createdTime": "2026-04-11T17:00:00.000Z",
                        "cellValuesByColumnId": {
                            "title": "Backend Engineer",
                            "date": "2026-04-11",
                            "apply": {
                                "label": "Apply",
                                "url": "https://jobs.example/stripe-older",
                            },
                            "company": "Stripe",
                        },
                    },
                    {
                        "id": "row-future",
                        "createdTime": "2026-04-12T01:00:00.000Z",
                        "cellValuesByColumnId": {
                            "title": "Future Role",
                            "date": "2026-04-11",
                            "apply": {
                                "label": "Apply",
                                "url": "https://jobs.example/futureco",
                            },
                            "company": "FutureCo",
                        },
                    },
                    {
                        "id": "row-3",
                        "createdTime": "2026-04-09T17:00:00.000Z",
                        "cellValuesByColumnId": {
                            "title": "Old Role",
                            "date": "2026-04-09",
                            "apply": {
                                "label": "Apply",
                                "url": "https://jobs.example/oldco",
                            },
                            "company": "OldCo",
                        },
                    },
                ],
            }
        }
    }

    companies = parse_airtable_view_data(
        payload,
        now=datetime(2026, 4, 11, 20, 15, tzinfo=ZoneInfo("America/New_York")),
    )

    assert len(companies) == 1
    assert companies[0].display_name == "Stripe"
    assert companies[0].job_title == "Software Engineer"
    assert companies[0].listing_url == "https://jobs.example/stripe"


def test_extract_companies_from_tesseract_tsv_reads_company_column():
    """The OCR fallback should read company names from the Company column."""
    tsv_text = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\t"
        "width\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t1565\t978\t72\t15\t96.5\tCompany\n"
        "5\t1\t1\t1\t1\t2\t1805\t978\t47\t15\t96.9\tSalary\n"
        "5\t1\t1\t1\t2\t1\t1564\t1017\t61\t12\t96.9\tTrusted\n"
        "5\t1\t1\t1\t2\t2\t1628\t1017\t77\t12\t96.9\tConcepts,\n"
        "5\t1\t1\t1\t2\t3\t1710\t1017\t39\t12\t96.9\tInc.\n"
        "5\t1\t1\t1\t3\t1\t1565\t1046\t111\t12\t96.9\tRemoteHunter\n"
    )

    companies = extract_companies_from_tesseract_tsv(
        tsv_text,
        screenshot_path="/tmp/email-automater-2/tests/screenshot.png",
    )

    assert [company.display_name for company in companies] == [
        "Trusted Concepts, Inc",
        "RemoteHunter",
    ]


def test_parse_listing_html_extracts_recent_unique_companies():
    """The legacy scraper should still dedupe companies and keep recent listings."""
    html = """
    <div role="listitem" class="collection-item-8 w-dyn-item">
      <a href="/list-software-engineer-jobs/jr_web_developer_at_leidos_1"></a>
      <p class="time">April 11, 2026</p>
      <p class="jobtitle">Jr Web developer</p>
      <p class="companyname_list">Leidos</p>
    </div>
    <div role="listitem" class="collection-item-8 w-dyn-item">
      <a href="/list-software-engineer-jobs/junior_software_engineer_at_leidos_2"></a>
      <p class="time">April 11, 2026</p>
      <p class="jobtitle">Junior Software Engineer</p>
      <p class="companyname_list">Leidos</p>
    </div>
    <div role="listitem" class="collection-item-8 w-dyn-item">
      <a href="/list-software-engineer-jobs/software_engineer_at_oldco_3"></a>
      <p class="time">April 08, 2026</p>
      <p class="jobtitle">Software Engineer</p>
      <p class="companyname_list">OldCo</p>
    </div>
    """

    companies = parse_listing_html(
        html,
        now=datetime(2026, 4, 11, 10, 15, tzinfo=ZoneInfo("America/New_York")),
    )

    assert len(companies) == 1
    assert companies[0].display_name == "Leidos"
