"""Each registered validator: happy + sad cases."""

from __future__ import annotations

import pytest

from laia_cli.install_wizard import validators


@pytest.mark.parametrize("name,value,expected_ok", [
    # non_empty
    ("non_empty", "abc", True),
    ("non_empty", "", False),
    ("non_empty", None, False),
    ("non_empty", [], False),
    ("non_empty", ["x"], True),
    # password_strength
    ("password_strength", "longenough123", True),
    ("password_strength", "short", False),
    ("password_strength", "password", False),
    ("password_strength", None, False),
    # ssh_target
    ("ssh_target", "laia@10.0.0.5", True),
    ("ssh_target", "laia-hermes@192.168.1.10", True),
    ("ssh_target", "user@host.example.com", True),
    ("ssh_target", "user@laia-old", True),
    ("ssh_target", "noatsign", False),
    ("ssh_target", "@nohost", False),
    ("ssh_target", "user@", False),
    ("ssh_target", "user@999.0.0.1", False),
    # valid_hostname
    ("valid_hostname", "example.com", True),
    ("valid_hostname", "laia-old", True),
    ("valid_hostname", "-bad", False),
    ("valid_hostname", "", False),
    # ipv4
    ("ipv4", "192.168.1.1", True),
    ("ipv4", "255.255.255.255", True),
    ("ipv4", "1.2.3", False),
    ("ipv4", "256.0.0.0", False),
    # rsync_bwlimit (empty allowed)
    ("rsync_bwlimit", "", True),
    ("rsync_bwlimit", None, True),
    ("rsync_bwlimit", "50M", True),
    ("rsync_bwlimit", "1G", True),
    ("rsync_bwlimit", "200K", True),
    ("rsync_bwlimit", "abc", False),
    ("rsync_bwlimit", "50MB", False),
    # port_number
    ("port_number", "8088", True),
    ("port_number", "0", False),
    ("port_number", "70000", False),
    ("port_number", "abc", False),
    # posix_username
    ("posix_username", "admin", True),
    ("posix_username", "laia-hermes", True),
    ("posix_username", "_underscore", True),
    ("posix_username", "Admin", False),  # uppercase
    ("posix_username", "1leading", False),
    ("posix_username", "with space", False),
    # llm_provider_name
    ("llm_provider_name", "deepseek", True),
    ("llm_provider_name", "openai", True),
    ("llm_provider_name", "my-custom", True),
    ("llm_provider_name", "Bad Name!", False),
    ("llm_provider_name", "", False),
])
def test_validator(name, value, expected_ok):
    ok, msg = validators.run(name, value)
    assert ok == expected_ok, f"{name}({value!r}) → ({ok}, {msg!r})"
    if not ok:
        assert msg, "Failed validators must include an error message."


def test_unknown_validator_returns_clean_error():
    ok, msg = validators.run("not_a_real_validator", "x")
    assert ok is False
    assert "desconocido" in (msg or "")


def test_no_validator_means_pass():
    ok, msg = validators.run(None, "anything")
    assert ok is True and msg is None


def test_existing_path(tmp_path):
    ok, _ = validators.run("existing_path", str(tmp_path))
    assert ok is True
    ok, msg = validators.run("existing_path", str(tmp_path / "does-not-exist"))
    assert ok is False and msg


def test_writable_dir(tmp_path):
    ok, _ = validators.run("writable_dir", str(tmp_path))
    assert ok is True
