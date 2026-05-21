"""Tests for __main__.py — argparse + Ctrl-C / EOF / exception handling."""

from __future__ import annotations

import pytest


def test_main_version_returns_zero(capsys):
    from laia_cli.install_wizard.__main__ import main
    rc = main(["--version"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "contract" in out
    assert "0.1.0" in out


def test_main_keyboard_interrupt_returns_130(monkeypatch, capsys):
    """Ctrl-C during the loop must surface as exit 130 with a clean line."""
    from laia_cli.install_wizard import __main__ as main_mod

    def raise_kbd(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(main_mod, "_run", raise_kbd)
    rc = main_mod.main(["--text-ui"])
    assert rc == 130
    err = capsys.readouterr().err
    assert "Cancelado por el usuario" in err
    assert "Traceback" not in err
    assert "--resume" in err


def test_main_eof_returns_130(monkeypatch, capsys):
    from laia_cli.install_wizard import __main__ as main_mod
    monkeypatch.setattr(main_mod, "_run",
                        lambda *a, **kw: (_ for _ in ()).throw(EOFError()))
    rc = main_mod.main(["--text-ui"])
    assert rc == 130
    assert "Fin de entrada" in capsys.readouterr().err


def test_main_unexpected_exception_returns_1(monkeypatch, capsys):
    from laia_cli.install_wizard import __main__ as main_mod
    monkeypatch.setattr(main_mod, "_run",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    rc = main_mod.main(["--text-ui"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "boom" in err
    assert "--debug" in err
    assert "Traceback" not in err


def test_main_debug_flag_reraises(monkeypatch):
    """With --debug, exceptions propagate so a developer sees the traceback."""
    from laia_cli.install_wizard import __main__ as main_mod
    monkeypatch.setattr(main_mod, "_run",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        main_mod.main(["--text-ui", "--debug"])
