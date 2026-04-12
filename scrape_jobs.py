"""Scrape recent new-grad software companies from newgrad-jobs.com."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from utils.company_normalize import clean_company_display_name, company_key

load_dotenv()

HOMEPAGE_URL = "https://www.newgrad-jobs.com/"
LEGACY_SOURCE_URL = "https://www.newgrad-jobs.com/list-software-engineer-jobs"
DIRECT_AIRTABLE_EMBED_URL = (
    "https://airtable.com/embed/appjDG7vmPOm1pO7S/shr763VHjlzPBDCgN/tblLP4AtskrLA8Aw1"
)
CANONICAL_AIRTABLE_EMBED_URL = (
    "https://airtable.com/embed/appjDG7vmPOm1pO7S/shr763VHjlzPBDCgN?viewControls=on"
)
PRIMARY_SOURCE_NAME = "newgrad-jobs"
TIMEZONE = ZoneInfo("America/New_York")
MIN_OCR_LINE_LENGTH = 2
MAX_OCR_LINE_LENGTH = 50
MAX_OCR_WORDS = 5
OCR_MIN_CONFIDENCE = 40.0
OCR_LINE_GAP = 12
DATE_RE = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$")
CARD_RE = re.compile(
    r'<div role="listitem" class="collection-item-8 w-dyn-item">.*?'
    r'<a href="(?P<href>/list-software-engineer-jobs/[^"]+)".*?'
    r'<p class="time">(?P<date>[^<]+)</p>.*?'
    r'<p class="jobtitle">(?P<title>[^<]+)</p>.*?'
    r'<p class="companyname_list">(?P<company>[^<]+)</p>',
    re.DOTALL,
)
AIRTABLE_LINK_RE = re.compile(
    r'<h2[^>]*data-job-path="(?P<job_path>[^"]+)"[^>]*'
    r'airtable-link="(?P<airtable_link>https://airtable\.com/embed/[^"]+)"[^>]*'
    r'short-link="(?P<short_link>[^"]*)"[^>]*>(?P<label>[^<]+)</h2>',
    re.DOTALL,
)
PREFETCH_URL_RE = re.compile(r'urlWithParams:\s*"(?P<url>[^"]+)"')
PREFETCH_HEADERS_RE = re.compile(r"var headers = (?P<headers>\{.*?\});")
OCR_STOP_WORDS = {
    "software",
    "engineer",
    "developer",
    "jobs",
    "job",
    "remote",
    "hybrid",
    "onsite",
    "entry",
    "level",
    "new",
    "grad",
    "apply",
    "opening",
    "openings",
    "today",
    "subscribe",
    "full time",
    "part time",
}


@dataclass(slots=True)
class ScrapedCompany:
    """A single company discovered from the job source."""

    display_name: str
    company_key: str
    job_title: str
    listing_url: str
    posted_at: str
    source: str = PRIMARY_SOURCE_NAME


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Scrape new-grad companies")
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="Fallback screenshot path used only if scraping fails",
    )
    return parser.parse_args()


def _http_get(
    url: str,
    *,
    session: requests.Session | None = None,
) -> requests.Response:
    client = session or requests
    return client.get(  # type: ignore[return-value]
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
        },
    )


def fetch_listing_html(url: str = LEGACY_SOURCE_URL) -> str:
    """Fetch the raw HTML for the legacy job listing page."""
    response = _http_get(url)
    response.raise_for_status()
    return response.text


def fetch_homepage_html(url: str = HOMEPAGE_URL) -> str:
    """Fetch the newgrad-jobs homepage HTML."""
    response = _http_get(url)
    response.raise_for_status()
    return response.text


def _parse_date(value: str) -> datetime | None:
    cleaned = value.strip()
    if not DATE_RE.match(cleaned):
        return None
    return datetime.strptime(cleaned, "%B %d, %Y").replace(tzinfo=TIMEZONE)


def parse_listing_html(
    html_text: str,
    *,
    now: datetime | None = None,
) -> list[ScrapedCompany]:
    """Extract recent companies from the legacy listing page."""
    timestamp = now or datetime.now(TIMEZONE)
    recent_cutoff = timestamp - timedelta(hours=24)
    companies: dict[str, ScrapedCompany] = {}

    for match in CARD_RE.finditer(html_text):
        company_name = clean_company_display_name(match.group("company"))
        posted_at = _parse_date(match.group("date"))
        if posted_at is None:
            continue
        if posted_at.date() < recent_cutoff.date():
            continue

        key = company_key(company_name)
        companies.setdefault(
            key,
            ScrapedCompany(
                display_name=company_name,
                company_key=key,
                job_title=match.group("title").strip(),
                listing_url=f"https://www.newgrad-jobs.com{match.group('href')}",
                posted_at=posted_at.isoformat(),
            ),
        )

    return list(companies.values())


def extract_airtable_embed_url(
    homepage_html: str,
    *,
    job_path: str = "/us/swe",
    short_link: str = "swe",
) -> str | None:
    """Return the Software Engineering Airtable embed URL from the homepage."""
    fallback: str | None = None
    for match in AIRTABLE_LINK_RE.finditer(homepage_html):
        matched_job_path = match.group("job_path").strip()
        matched_short_link = match.group("short_link").strip().lower()
        matched_label = html.unescape(match.group("label")).strip().lower()
        airtable_link = match.group("airtable_link").strip()
        if matched_job_path == job_path:
            return airtable_link
        if matched_short_link == short_link and matched_job_path.startswith("/us/"):
            fallback = airtable_link
        elif "software engineering" in matched_label and matched_job_path.startswith(
            "/us/"
        ):
            fallback = fallback or airtable_link
    return fallback or DIRECT_AIRTABLE_EMBED_URL


def _decode_js_string(value: str) -> str:
    return html.unescape(value).encode("utf-8").decode("unicode_escape")


def _extract_airtable_prefetch(embed_html: str) -> tuple[str, dict[str, str]]:
    url_match = PREFETCH_URL_RE.search(embed_html)
    headers_match = PREFETCH_HEADERS_RE.search(embed_html)
    if not url_match or not headers_match:
        msg = "Could not parse Airtable prefetch metadata"
        raise ValueError(msg)
    prefetch_url = _decode_js_string(url_match.group("url"))
    headers = json.loads(headers_match.group("headers"))
    return prefetch_url, {str(key): str(value) for key, value in headers.items()}


def fetch_airtable_view_data(embed_url: str) -> dict[str, Any]:
    """Fetch the shared Airtable view data backing the newgrad-jobs table."""
    session = requests.Session()
    embed_response = _http_get(embed_url, session=session)
    embed_response.raise_for_status()
    prefetch_url, headers = _extract_airtable_prefetch(embed_response.text)
    headers["x-time-zone"] = str(TIMEZONE)
    headers["referer"] = embed_url

    shared_view_response = session.get(
        f"https://airtable.com{prefetch_url}",
        headers=headers,
        timeout=20,
    )
    shared_view_response.raise_for_status()
    payload = shared_view_response.json()
    if payload.get("msg") != "SUCCESS":
        msg = f"Unexpected Airtable response: {payload.get('msg', 'unknown')}"
        raise ValueError(msg)
    return payload


def _parse_airtable_timestamp(
    created_time: str | None,
    date_value: str | None,
) -> datetime | None:
    if created_time:
        return datetime.fromisoformat(created_time).astimezone(TIMEZONE)
    if date_value:
        return datetime.strptime(date_value, "%Y-%m-%d").replace(tzinfo=TIMEZONE)
    return None


def _build_choice_maps(
    columns: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    columns_by_name: dict[str, str] = {}
    choice_maps: dict[str, dict[str, str]] = {}
    for column in columns:
        column_id = str(column.get("id", "")).strip()
        column_name = str(column.get("name", "")).strip()
        if not column_id or not column_name:
            continue
        columns_by_name[column_name] = column_id
        raw_choices = (column.get("typeOptions") or {}).get("choices") or {}
        if not isinstance(raw_choices, dict):
            continue
        choice_maps[column_id] = {
            str(choice_id): str(choice.get("name", "")).strip()
            for choice_id, choice in raw_choices.items()
            if isinstance(choice, dict)
        }
    return columns_by_name, choice_maps


def _decode_airtable_value(
    value: object,
    *,
    choice_map: dict[str, str] | None = None,
) -> str:
    resolved_choices = choice_map or {}
    if isinstance(value, dict):
        if "url" in value:
            return str(value.get("url", "")).strip()
        if "label" in value:
            return str(value.get("label", "")).strip()
        return ""
    if isinstance(value, list):
        labels = [resolved_choices.get(str(item), str(item)) for item in value]
        return ", ".join(label for label in labels if label)
    if value is None:
        return ""
    return resolved_choices.get(str(value), str(value)).strip()


def parse_airtable_view_data(
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
) -> list[ScrapedCompany]:
    """Extract recent companies from the Airtable shared view payload."""
    timestamp = now or datetime.now(TIMEZONE)
    recent_cutoff = timestamp - timedelta(hours=24)

    table = payload.get("data", {}).get("table", {})
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if not isinstance(columns, list) or not isinstance(rows, list):
        return []

    columns_by_name, choice_maps = _build_choice_maps(columns)
    title_column = columns_by_name.get("Position Title")
    company_column = columns_by_name.get("Company")
    apply_column = columns_by_name.get("Apply")
    date_column = columns_by_name.get("Date")
    if not title_column or not company_column:
        return []

    companies: dict[str, ScrapedCompany] = {}
    latest_seen_at: dict[str, datetime] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        cell_values = row.get("cellValuesByColumnId", {})
        if not isinstance(cell_values, dict):
            continue

        posted_at = _parse_airtable_timestamp(
            str(row.get("createdTime", "")).strip() or None,
            _decode_airtable_value(
                cell_values.get(date_column, ""),
                choice_map=choice_maps.get(date_column or "", {}),
            )
            if date_column
            else None,
        )
        if posted_at is None or posted_at < recent_cutoff or posted_at > timestamp:
            continue

        company_name = clean_company_display_name(
            _decode_airtable_value(
                cell_values.get(company_column, ""),
                choice_map=choice_maps.get(company_column, {}),
            )
        )
        if not company_name:
            continue

        key = company_key(company_name)
        if not key:
            continue

        if key in latest_seen_at and latest_seen_at[key] >= posted_at:
            continue

        companies[key] = ScrapedCompany(
            display_name=company_name,
            company_key=key,
            job_title=_decode_airtable_value(
                cell_values.get(title_column, ""),
                choice_map=choice_maps.get(title_column, {}),
            )
            or "Software Engineering",
            listing_url=_decode_airtable_value(
                cell_values.get(apply_column, ""),
                choice_map=choice_maps.get(apply_column or "", {}),
            )
            or embed_url_from_payload(payload),
            posted_at=posted_at.isoformat(),
        )
        latest_seen_at[key] = posted_at

    return list(companies.values())


def embed_url_from_payload(payload: dict[str, Any]) -> str:
    """Best-effort shared-view URL for traceability."""
    share_id = str(payload.get("data", {}).get("shareId", "")).strip()
    shared_view_id = str(payload.get("data", {}).get("sharedViewId", "")).strip()
    if share_id and shared_view_id:
        return f"https://airtable.com/{share_id}/{shared_view_id}"
    return HOMEPAGE_URL


def scrape_companies_from_airtable(
    *,
    now: datetime | None = None,
) -> list[ScrapedCompany]:
    """Scrape recent companies from the live Airtable-backed software table."""
    homepage_html = fetch_homepage_html()
    embed_candidates = [
        extract_airtable_embed_url(homepage_html),
        DIRECT_AIRTABLE_EMBED_URL,
        CANONICAL_AIRTABLE_EMBED_URL,
    ]
    seen: set[str] = set()
    for embed_url in embed_candidates:
        if not embed_url or embed_url in seen:
            continue
        seen.add(embed_url)
        try:
            return parse_airtable_view_data(
                fetch_airtable_view_data(embed_url),
                now=now,
            )
        except (json.JSONDecodeError, requests.RequestException, ValueError):
            continue
    return []


def _clean_ocr_line(line: str) -> str:
    cleaned = re.sub(r"^[\W_]+", "", line.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,.-")


def _looks_like_company_ocr_line(line: str) -> bool:
    lowered = line.lower()
    tokens = set(re.findall(r"[a-z]+", lowered))
    if len(line) < MIN_OCR_LINE_LENGTH or len(line) > MAX_OCR_LINE_LENGTH:
        return False
    if any(
        stop_word in lowered if " " in stop_word else stop_word in tokens
        for stop_word in OCR_STOP_WORDS
    ):
        return False
    if any(character.isdigit() for character in line):
        return False
    return len(line.split()) <= MAX_OCR_WORDS


def _parse_tesseract_tsv(tsv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(tsv_text), delimiter="\t"))


def _company_column_bounds(
    rows: list[dict[str, str]],
) -> tuple[int, int, int] | None:
    header_candidates: list[dict[str, str]] = []
    salary_candidates: list[dict[str, str]] = []

    for row in rows:
        text = row.get("text", "").strip()
        if text == "Company":
            header_candidates.append(row)
        elif text == "Salary":
            salary_candidates.append(row)

    if not header_candidates or not salary_candidates:
        return None

    header = max(
        header_candidates,
        key=lambda row: (int(row["top"]), int(row["left"])),
    )
    salary = min(
        (
            row
            for row in salary_candidates
            if abs(int(row["top"]) - int(header["top"])) <= OCR_LINE_GAP
        ),
        key=lambda row: int(row["left"]),
        default=min(salary_candidates, key=lambda row: int(row["left"])),
    )
    return int(header["left"]) - 8, int(salary["left"]) - 10, int(header["top"])


def _company_column_line_words(
    rows: list[dict[str, str]],
    *,
    company_left: int,
    company_right: int,
    header_top: int,
) -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
    line_words: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        text = row.get("text", "").strip()
        if not text:
            continue
        left = int(row["left"])
        top = int(row["top"])
        conf = float(row["conf"])
        if conf < OCR_MIN_CONFIDENCE or top <= header_top + OCR_LINE_GAP:
            continue
        if not (company_left <= left < company_right):
            continue
        if text in {"Company", "Salary"}:
            continue
        line_key = (
            row["page_num"],
            row["block_num"],
            row["par_num"],
            row["line_num"],
        )
        line_words.setdefault(line_key, []).append(row)
    return line_words


def _scraped_company_from_ocr_line(
    line: str,
    *,
    screenshot_path: str | Path,
) -> ScrapedCompany | None:
    if not _looks_like_company_ocr_line(line):
        return None
    key = company_key(line)
    if not key:
        return None
    return ScrapedCompany(
        display_name=line,
        company_key=key,
        job_title="OCR fallback",
        listing_url=str(screenshot_path),
        posted_at=datetime.now(TIMEZONE).isoformat(),
        source="screenshot-ocr",
    )


def extract_companies_from_tesseract_tsv(
    tsv_text: str,
    *,
    screenshot_path: str | Path,
) -> list[ScrapedCompany]:
    """Extract company names from the screenshot's Company column."""
    rows = _parse_tesseract_tsv(tsv_text)
    bounds = _company_column_bounds(rows)
    if bounds is None:
        return []

    company_left, company_right, header_top = bounds
    line_words = _company_column_line_words(
        rows,
        company_left=company_left,
        company_right=company_right,
        header_top=header_top,
    )
    companies: dict[str, ScrapedCompany] = {}
    for words in line_words.values():
        ordered = sorted(words, key=lambda row: int(row["left"]))
        line = _clean_ocr_line(" ".join(word["text"] for word in ordered))
        company = _scraped_company_from_ocr_line(
            line,
            screenshot_path=screenshot_path,
        )
        if company:
            companies.setdefault(company.company_key, company)
    return list(companies.values())


def _fallback_companies_from_ocr_text(
    ocr_text: str,
    *,
    screenshot_path: Path,
) -> list[ScrapedCompany]:
    companies: dict[str, ScrapedCompany] = {}
    for raw_line in ocr_text.splitlines():
        line = _clean_ocr_line(raw_line)
        company = _scraped_company_from_ocr_line(
            line,
            screenshot_path=screenshot_path,
        )
        if company:
            companies.setdefault(company.company_key, company)
    return list(companies.values())


def extract_companies_from_screenshot(path: str | Path) -> list[ScrapedCompany]:
    """Use Tesseract OCR to extract company-like names from a screenshot."""
    screenshot_path = Path(path)
    tesseract_path = shutil.which("tesseract")
    if not tesseract_path:
        msg = "tesseract is not installed"
        raise RuntimeError(msg)

    tsv_result = subprocess.run(  # noqa: S603
        [tesseract_path, str(screenshot_path), "stdout", "--psm", "6", "tsv"],
        capture_output=True,
        text=True,
        check=False,
    )
    if tsv_result.returncode == 0:
        extracted = extract_companies_from_tesseract_tsv(
            tsv_result.stdout,
            screenshot_path=screenshot_path,
        )
        if extracted:
            return extracted

    text_result = subprocess.run(  # noqa: S603
        [tesseract_path, str(screenshot_path), "stdout", "--psm", "6"],
        capture_output=True,
        text=True,
        check=False,
    )
    if text_result.returncode != 0:
        msg = text_result.stderr.strip() or "tesseract failed"
        raise RuntimeError(msg)
    return _fallback_companies_from_ocr_text(
        text_result.stdout,
        screenshot_path=screenshot_path,
    )


def scrape_companies(
    *,
    screenshot: str | Path | None = None,
    now: datetime | None = None,
) -> list[ScrapedCompany]:
    """Scrape the primary source and optionally fall back to legacy/OCR paths."""
    for scrape_step in (
        lambda: scrape_companies_from_airtable(now=now),
        lambda: parse_listing_html(fetch_listing_html(), now=now),
    ):
        try:
            companies = scrape_step()
        except (json.JSONDecodeError, requests.RequestException, ValueError):
            companies = []
        if companies:
            return companies

    if screenshot is None:
        return []
    return extract_companies_from_screenshot(screenshot)


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    companies = scrape_companies(screenshot=args.screenshot)
    output = [company.display_name for company in companies]
    output.append(f"\ncompanies={len(companies)}")
    sys.stdout.write("\n".join(output) + "\n")
    return 0 if companies else 1


if __name__ == "__main__":
    raise SystemExit(main())
