# Email Automater

Local Python recruiter-outreach tooling.

This repo currently ships:

- a one-off Gmail sender for manual outreach
- a daily pipeline that scrapes recent companies from `newgrad-jobs.com`
- Apollo-based recruiter discovery with hard spend guards
- conservative business-hour pacing for new outreach and follow-ups
- Gmail thread checks for replies, bounces, opt-outs, and follow-up stops
- local state tracking in `state/outreach_state.json`
- helper installers for cron and macOS `launchd`

This repo does **not** currently ship a web UI, multi-tenant auth, or a SaaS backend. It is still a single-user local workflow.

## Current Behavior

The default daily flow is:

1. scrape recent software-ish jobs from `newgrad-jobs.com`
2. normalize and dedupe company names
3. skip companies already contacted today, on cooldown, or over the 60-day cap
4. discover recruiter-like contacts in Apollo
5. render sample outreach using the committed email templates
6. send new outreach only inside the configured business window
7. check existing Gmail threads for replies, bounces, auto-replies, and opt-outs
8. send follow-ups as real thread replies when due

Key safety rules already enforced in code:

- dry runs skip paid Apollo discovery unless `--allow-paid-apollo-in-dry-run` is set
- outside the active send window, the pipeline does not spend Apollo credits on new outreach
- sends are paced locally instead of blasting all contacts at once
- one new recruiter contact per company per day
- two recruiter contacts max per company inside a rolling 60-day window
- follow-ups stop when the thread shows a reply, bounce, auto-reply, or opt-out

## Repository Layout

- `pipeline.py`: daily orchestration entrypoint
- `automate_emails.py`: one-off recruiter email sender
- `send_followups.py`: due follow-up runner
- `run_daily_once.py`: once-per-day wrapper for cron/launchd
- `scrape_jobs.py`: job scraping + screenshot OCR fallback
- `find_contacts.py`: Apollo recruiter lookup helper
- `utils/outreach_state.py`: JSON state model
- `email1.md`, `email2.md`, `email3.md`: sample email templates

## Setup

1. Clone the repo.
2. Install dependencies.

Using `uv`:

```bash
uv sync
```

Using `venv` + `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Create a `.env` from `env.example`.
4. Follow the Gmail quickstart to create `credentials.json`:
   [Google Gmail API Python quickstart](https://developers.google.com/gmail/api/quickstart/python)
5. Run any Gmail command once to generate `token.json`.

`token.json`, `credentials.json`, local state, and logs are ignored by Git.

## Configuration

See `env.example` for the current supported settings.

Most important variables:

- `APOLLO_API_KEY`: required for recruiter discovery
- `MESSAGE_BODY_PATH`: template used for initial outreach
- `EMAIL_SUBJECT`: optional fallback subject when the template does not provide an inline `Subject:`
- `TOKEN_PATH` / `CREDS_PATH`: Gmail auth paths
- `TIMEZONE`: primary local timezone for state + scheduling decisions
- `SEND_WINDOW_TIMEZONE`: timezone used for new-outreach pacing
- `SCHEDULE_CSV_PATH`: optional editable CSV for new-outreach send windows
- `OUTREACH_WEEKDAYS`: allowed weekdays for new outreach
- `NEW_OUTREACH_DAILY_LIMIT`: max new outreach actions per run/day
- `MAX_COMPANIES_PER_RUN`: max scraped companies considered in one run
- `PIPELINE_CONTACT_DISCOVERY_LIMIT_PER_COMPANY`: recruiter candidates explored per company
- `APOLLO_REQUEST_BUDGET_PER_RUN`: hard per-run Apollo request budget
- `FOLLOWUP_DAILY_LIMIT`: optional follow-up cap; unset or `0` means no extra cap

The committed templates are safe sample defaults. Customize them before using this for real outreach.

## Commands

Daily pipeline:

```bash
.venv/bin/python pipeline.py --mode daily --dry-run
.venv/bin/python pipeline.py --mode daily --dry-run --allow-paid-apollo-in-dry-run
.venv/bin/python pipeline.py --mode daily
```

Once-per-day wrapper for schedulers:

```bash
.venv/bin/python run_daily_once.py
```

Direct helpers:

```bash
.venv/bin/python scrape_jobs.py
.venv/bin/python scrape_jobs.py --screenshot /absolute/path/to/screenshot.png
.venv/bin/python find_contacts.py Stripe --allow-paid-apollo
.venv/bin/python send_followups.py
```

One-off send:

```bash
.venv/bin/python automate_emails.py "ExampleCo" "Taylor Recruiter" "taylor@example.com"
```

## Scheduler Helpers

Two schedules matter here:

- daily runner schedule: cron/launchd launches `run_daily_once.py` at `3:00 PM` in `America/New_York`
- send-window schedule: an optional `scheduler.csv` can override the default business-hour send window used by new outreach

Without a custom `scheduler.csv`, the default window is:

- Monday-Friday: `09:00-16:30`
- Sunday: `09:00-16:30`
- Saturday: no new-outreach window

CSV day mapping uses Python weekday numbers:

- `0=Monday`
- `1=Tuesday`
- `2=Wednesday`
- `3=Thursday`
- `4=Friday`
- `5=Saturday`
- `6=Sunday`

Cron installer:

```bash
.venv/bin/python -m utils.cron_setup --repo-path "$(pwd)"
```

The installed cron line looks like:

```bash
0 15 * * * cd /absolute/path/to/repo && .venv/bin/python run_daily_once.py >> daily_run.log 2>&1
```

macOS LaunchAgent installer:

```bash
.venv/bin/python -m utils.launchd_setup --repo-path "$(pwd)"
```

## Testing

Run the current gate locally:

```bash
pytest tests/ -q
uvx ruff check .
uvx ruff format --check .
```

## Notes

- The old Streak-based scheduling path has been removed from the active workflow.
- State lives in `state/outreach_state.json`; deleting it resets local history.
- This repo is intentionally conservative about spend and deliverability. If a run cannot send safely, it should send less rather than more.
