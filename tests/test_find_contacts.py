"""Tests for the standalone Apollo contact finder CLI."""

from types import SimpleNamespace

import find_contacts

EXIT_LIVE_APOLLO_OPT_IN_REQUIRED = 2


def test_find_contacts_main_refuses_paid_apollo_without_opt_in(
    monkeypatch,
    tmp_path,
    capsys,
):
    """Standalone Apollo lookups should require an explicit live-credit opt-in."""
    monkeypatch.setattr(
        find_contacts,
        "parse_args",
        lambda: SimpleNamespace(
            companies=["Stripe"],
            limit=3,
            apollo_api_key="test-key",
            state_path=str(tmp_path / "outreach_state.json"),
            allow_paid_apollo=False,
        ),
    )
    monkeypatch.setattr(
        find_contacts,
        "ApolloClient",
        lambda **_: (_ for _ in ()).throw(AssertionError("Apollo should not run")),
    )

    result = find_contacts.main()

    captured = capsys.readouterr()
    assert result == EXIT_LIVE_APOLLO_OPT_IN_REQUIRED
    assert "--allow-paid-apollo" in captured.err
