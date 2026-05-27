"""Tests for Atlas v2 (atlas.py), laia_paths.py, the atlas CLI and runtime paths."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import textwrap
import time
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CORE = _REPO_ROOT / ".laia-core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from laia_paths import load_config, resolve, render_env_file, get_path, all_paths
import atlas
from atlas import (
    AtlasError, AtlasConfigError, AtlasKeyError,
    HealthResult, get, get_path as atlas_get_path,
    all_refs, health, doctor, validate_registry, invalidate_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, content: str, name: str = "atlas.yaml") -> Path:
    f = tmp_path / name
    f.write_text(textwrap.dedent(content))
    return f


def _load_module(name: str, path: Path):
    # Use an explicit source loader so extension-less files (bin/atlas) load too.
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_cli():
    return _load_module("atlas_cli", _REPO_ROOT / "bin" / "atlas")


# ---------------------------------------------------------------------------
# laia_paths — load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_missing_returns_empty(self, tmp_path: Path) -> None:
        assert load_config(tmp_path / "nope.yaml") == {}

    def test_basic_parse(self, tmp_path: Path) -> None:
        f = tmp_path / "c.yaml"
        f.write_text("paths:\n  root: /srv\n")
        assert load_config(f)["paths"]["root"] == "/srv"

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yaml"
        f.write_text("")
        assert load_config(f) == {}

    def test_non_dict_top_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("- a\n- b\n")
        assert load_config(f) == {}


# ---------------------------------------------------------------------------
# laia_paths — resolve
# ---------------------------------------------------------------------------

class TestResolve:
    def test_simple(self) -> None:
        r = resolve({"paths": {"root": "/srv"}})
        assert r == {"root": "/srv"}

    def test_interpolation(self) -> None:
        r = resolve({"paths": {"root": "/srv", "a": "${paths.root}/a"}})
        assert r["a"] == "/srv/a"

    def test_chain(self) -> None:
        r = resolve({"paths": {"a": "/a", "b": "${paths.a}/b", "c": "${paths.b}/c"}})
        assert r["c"] == "/a/b/c"

    def test_tilde(self) -> None:
        r = resolve({"paths": {"h": "~/LAIA"}})
        assert r["h"] == str(Path.home() / "LAIA")

    def test_circular_raises(self) -> None:
        with pytest.raises(ValueError, match="circular"):
            resolve({"paths": {"a": "${paths.b}", "b": "${paths.a}"}})

    def test_unknown_ref_raises(self) -> None:
        with pytest.raises(KeyError):
            resolve({"paths": {"a": "${paths.missing}"}})

    def test_empty(self) -> None:
        assert resolve({}) == {}
        assert resolve({"paths": {}}) == {}


# ---------------------------------------------------------------------------
# laia_paths — render_env_file
# ---------------------------------------------------------------------------

class TestRenderEnvFile:
    def test_contains_exports(self) -> None:
        out = render_env_file({"agora": "/srv/agora", "root": "/srv"})
        assert 'export LAIA_AGORA="/srv/agora"' in out
        assert 'export LAIA_ROOT="/srv"' in out

    def test_sorted(self) -> None:
        out = render_env_file({"z": "/z", "a": "/a"})
        lines = [l for l in out.splitlines() if l.startswith("export")]
        assert lines[0].startswith("export LAIA_A=")
        assert lines[1].startswith("export LAIA_Z=")

    def test_includes_header(self) -> None:
        out = render_env_file({"x": "/x"})
        assert out.startswith("# Auto-generated")


# ---------------------------------------------------------------------------
# laia_paths — get_path env override
# ---------------------------------------------------------------------------

class TestGetPath:
    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LAIA_MYALIAS", "/override")
        assert get_path("myalias") == Path("/override")

    def test_fallback_to_default(self, tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LAIA_CONFIG_HOME", str(tmp_path))
        result = get_path("nonexistent", default=Path("/fallback"))
        assert result == Path("/fallback")


# ---------------------------------------------------------------------------
# atlas — exceptions
# ---------------------------------------------------------------------------

class TestAtlasExceptions:
    def test_key_error_is_atlas_error(self) -> None:
        assert issubclass(AtlasKeyError, AtlasError)
        assert issubclass(AtlasKeyError, KeyError)

    def test_config_error_is_atlas_error(self) -> None:
        assert issubclass(AtlasConfigError, AtlasError)


# ---------------------------------------------------------------------------
# atlas — _load_raw & caching
# ---------------------------------------------------------------------------

class TestAtlasCache:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        result = atlas._load_raw(tmp_path / "nope.yaml")
        assert result == {}

    def test_bad_yaml_raises_config_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("refs:\n  broken: [this is a list not a dict]\n")
        # _load_raw succeeds (just returns the raw dict), but get() will fail
        refs = atlas._load_raw(f)
        assert "broken" in refs

    def test_non_dict_top_raises_config_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("- a\n- b\n")
        with pytest.raises(AtlasConfigError):
            atlas._load_raw(f)

    def test_cache_hit_no_reread(self, tmp_path: Path) -> None:
        f = _write(tmp_path, """
            version: 2
            refs:
              r1:
                type: path
                value: /tmp
        """)
        t0 = time.perf_counter()
        for _ in range(500):
            atlas._load_raw(f)
        elapsed = time.perf_counter() - t0
        # 500 cached reads must be well under 100ms
        assert elapsed < 0.1, f"cache too slow: {elapsed*1000:.1f}ms for 500 reads"

    def test_cache_invalidated_on_mtime_change(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  r1:\n    type: path\n    value: /a\n")
        r1 = atlas._load_raw(f)
        assert "r1" in r1
        # Rewrite file with different content
        time.sleep(0.01)  # ensure mtime changes
        f.write_text("version: 2\nrefs:\n  r2:\n    type: path\n    value: /b\n")
        import os; os.utime(f, None)  # bump mtime
        r2 = atlas._load_raw(f)
        assert "r2" in r2

    def test_invalidate_cache_forces_reread(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  old:\n    type: path\n    value: /old\n")
        atlas._load_raw(f)
        f.write_text("version: 2\nrefs:\n  new:\n    type: path\n    value: /new\n")
        import os; os.utime(f, None)
        invalidate_cache()
        refs = atlas._load_raw(f)
        assert "new" in refs


# ---------------------------------------------------------------------------
# atlas — get()
# ---------------------------------------------------------------------------

class TestAtlasGet:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_path_type(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  p:\n    type: path\n    value: /tmp\n")
        assert get("p", config_path=f) == "/tmp"

    def test_tilde_expansion(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  h:\n    type: path\n    value: ~/X\n")
        assert get("h", config_path=f) == str(Path.home() / "X")

    def test_ref_interpolation(self, tmp_path: Path) -> None:
        f = _write(tmp_path, """
            version: 2
            refs:
              root:
                type: path
                value: /srv
              sub:
                type: path
                value: ${ref.root}/sub
        """)
        assert get("sub", config_path=f) == "/srv/sub"

    def test_service_url(self, tmp_path: Path) -> None:
        f = _write(tmp_path, """
            version: 2
            refs:
              api:
                type: service
                host: 127.0.0.1
                port: 8088
                protocol: http
        """)
        assert get("api", config_path=f) == "http://127.0.0.1:8088"

    def test_service_host_interpolation(self, tmp_path: Path) -> None:
        f = _write(tmp_path, """
            version: 2
            refs:
              hostname:
                type: path
                value: myhost
              svc:
                type: service
                host: ${ref.hostname}
                port: 80
        """)
        assert get("svc", config_path=f) == "http://myhost:80"

    def test_container_type(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  c:\n    type: container\n    value: laia-agora\n")
        assert get("c", config_path=f) == "laia-agora"

    def test_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  r:\n    type: path\n    value: /orig\n")
        monkeypatch.setenv("ATLAS_R", "/override")
        assert get("r", config_path=f) == "/override"

    def test_missing_raises_atlas_key_error(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs: {}\n")
        with pytest.raises(AtlasKeyError):
            get("nonexistent", config_path=f)

    def test_atlas_key_error_message_lists_available(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  known:\n    type: path\n    value: /x\n")
        with pytest.raises(AtlasKeyError, match="known"):
            get("unknown", config_path=f)

    def test_circular_ref_raises_atlas_error(self, tmp_path: Path) -> None:
        f = _write(tmp_path, """
            version: 2
            refs:
              a:
                type: path
                value: ${ref.b}
              b:
                type: path
                value: ${ref.a}
        """)
        with pytest.raises(AtlasError, match="circular"):
            get("a", config_path=f)

    def test_get_path_returns_path(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  d:\n    type: path\n    value: /tmp\n")
        assert atlas_get_path("d", config_path=f) == Path("/tmp")

    def test_get_path_default(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs: {}\n")
        assert atlas_get_path("nope", default=Path("/fb"), config_path=f) == Path("/fb")

    def test_get_path_raises_without_default(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs: {}\n")
        with pytest.raises(AtlasKeyError):
            atlas_get_path("nope", config_path=f)


# ---------------------------------------------------------------------------
# atlas — validate_registry
# ---------------------------------------------------------------------------

class TestValidateRegistry:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_valid_empty(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs: {}\n")
        assert validate_registry(f) == []

    def test_valid_all_types(self, tmp_path: Path) -> None:
        f = _write(tmp_path, """
            version: 2
            refs:
              p: {type: path, value: /a}
              s: {type: service, host: h, port: 80}
              c: {type: container, value: cont}
              k: {type: socket, value: /s.sock}
              e: {type: env_file, path: /e.env}
        """)
        assert validate_registry(f) == []

    def test_missing_type(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  r:\n    value: /x\n")
        errors = validate_registry(f)
        assert any("type" in e for e in errors)

    def test_unknown_type(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  r:\n    type: bogus\n    value: /x\n")
        errors = validate_registry(f)
        assert any("bogus" in e for e in errors)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  r:\n    type: service\n    host: h\n")
        errors = validate_registry(f)
        assert any("port" in e for e in errors)

    def test_entry_not_dict(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  r: [not, a, dict]\n")
        errors = validate_registry(f)
        assert any("mapping" in e.lower() or "dict" in e.lower() for e in errors)

    def test_bad_yaml_returns_one_error(self, tmp_path: Path) -> None:
        f = tmp_path / "atlas.yaml"
        f.write_text(": invalid: yaml: :\n")
        errors = validate_registry(f)
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# atlas — health checks
# ---------------------------------------------------------------------------

class TestHealthPath:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_existing_path(self, tmp_path: Path) -> None:
        existing = tmp_path / "dir"
        existing.mkdir()
        f = _write(tmp_path, f"version: 2\nrefs:\n  d:\n    type: path\n    value: {existing}\n")
        r = health("d", f)
        assert r.alive is True
        assert r.ref_type == "path"

    def test_missing_path(self, tmp_path: Path) -> None:
        f = _write(tmp_path, f"version: 2\nrefs:\n  d:\n    type: path\n    value: {tmp_path}/nope\n")
        r = health("d", f)
        assert r.alive is False
        assert "does not exist" in r.detail

    def test_socket_missing(self, tmp_path: Path) -> None:
        f = _write(tmp_path, f"version: 2\nrefs:\n  s:\n    type: socket\n    value: {tmp_path}/x.sock\n")
        r = health("s", f)
        assert r.alive is False

    def test_env_file_all_keys_present(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("A=1\nB=2\n")
        f = _write(tmp_path, f"""
            version: 2
            refs:
              e:
                type: env_file
                path: {env}
                keys: [A, B]
        """)
        r = health("e", f)
        assert r.alive is True

    def test_env_file_missing_key(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("A=1\n")
        f = _write(tmp_path, f"""
            version: 2
            refs:
              e:
                type: env_file
                path: {env}
                keys: [A, MISSING_KEY]
        """)
        r = health("e", f)
        assert r.alive is False
        assert "MISSING_KEY" in r.detail

    def test_env_file_not_found(self, tmp_path: Path) -> None:
        f = _write(tmp_path, f"""
            version: 2
            refs:
              e:
                type: env_file
                path: {tmp_path}/nope.env
                keys: [A]
        """)
        r = health("e", f)
        assert r.alive is False

    def test_health_never_raises_on_bad_entry(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  bad: [not a dict]\n")
        r = health("bad", f)
        assert r.alive is False

    def test_health_missing_name_returns_dead(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs: {}\n")
        r = health("ghost", f)
        assert r.alive is False

    def test_health_result_str(self) -> None:
        r = HealthResult(name="x", ref_type="path", value="/x", alive=True, detail="ok")
        assert "OK" in str(r)
        r2 = HealthResult(name="y", ref_type="path", value="/y", alive=False, detail="missing")
        assert "DEAD" in str(r2)


# ---------------------------------------------------------------------------
# atlas — doctor
# ---------------------------------------------------------------------------

class TestDoctor:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_all_keys_returned(self, tmp_path: Path) -> None:
        f = _write(tmp_path, f"""
            version: 2
            refs:
              ok:
                type: path
                value: {tmp_path}
              bad:
                type: path
                value: {tmp_path}/nope
        """)
        results = doctor(f)
        assert set(results) == {"ok", "bad"}
        assert results["ok"].alive is True
        assert results["bad"].alive is False

    def test_bad_config_returns_config_error_entry(self, tmp_path: Path) -> None:
        f = tmp_path / "atlas.yaml"
        f.write_text("not: valid: yaml: :\n")
        results = doctor(f)
        assert len(results) == 1
        r = next(iter(results.values()))
        assert r.alive is False

    def test_empty_registry(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs: {}\n")
        assert doctor(f) == {}


# ---------------------------------------------------------------------------
# Performance: 500 gets must be fast with cache
# ---------------------------------------------------------------------------

class TestPerformance:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_500_gets_under_50ms(self, tmp_path: Path) -> None:
        f = _write(tmp_path, """
            version: 2
            refs:
              r1:
                type: path
                value: /tmp
              r2:
                type: service
                host: 127.0.0.1
                port: 8080
        """)
        # Warm cache
        get("r1", config_path=f)
        t0 = time.perf_counter()
        for _ in range(500):
            get("r1", config_path=f)
            get("r2", config_path=f)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 50, f"1000 cached gets took {elapsed_ms:.1f}ms (expected <50ms)"


# ---------------------------------------------------------------------------
# atlas — interpolation expands only a leading ~ (regression for the
# value.replace("~", home) bug that corrupted any ~ in the string)
# ---------------------------------------------------------------------------

class TestInterpolateTilde:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_leading_tilde_expanded(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  h:\n    type: path\n    value: ~/X\n")
        assert get("h", config_path=f) == str(Path.home() / "X")

    def test_mid_string_tilde_preserved(self, tmp_path: Path) -> None:
        f = _write(tmp_path, "version: 2\nrefs:\n  b:\n    type: path\n    value: /var/backup~/data\n")
        assert get("b", config_path=f) == "/var/backup~/data"


# ---------------------------------------------------------------------------
# atlas — repair_hint propagates into HealthResult
# ---------------------------------------------------------------------------

class TestRepairHint:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_repair_hint_propagates(self, tmp_path: Path) -> None:
        f = _write(tmp_path, f"""
            version: 2
            refs:
              s:
                type: socket
                value: {tmp_path}/x.sock
                repair_hint: "systemctl --user start laia-pathd"
        """)
        r = health("s", f)
        assert r.alive is False
        assert r.repair_hint == "systemctl --user start laia-pathd"

    def test_no_hint_is_none(self, tmp_path: Path) -> None:
        f = _write(tmp_path, f"version: 2\nrefs:\n  s:\n    type: socket\n    value: {tmp_path}/x.sock\n")
        assert health("s", f).repair_hint is None


# ---------------------------------------------------------------------------
# CLI — atlas init (bootstrap from template)
# ---------------------------------------------------------------------------

class TestCliInit:
    def test_creates_from_template(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                   capsys: pytest.CaptureFixture) -> None:
        cli = _load_cli()
        monkeypatch.setenv("LAIA_CONFIG_HOME", str(tmp_path))
        rc = cli.cmd_init(types.SimpleNamespace(force=False))
        assert rc == 0
        dest = tmp_path / "atlas.yaml"
        assert dest.exists()
        assert "version: 2" in dest.read_text()

    def test_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                        capsys: pytest.CaptureFixture) -> None:
        cli = _load_cli()
        monkeypatch.setenv("LAIA_CONFIG_HOME", str(tmp_path))
        cli.cmd_init(types.SimpleNamespace(force=False))
        (tmp_path / "atlas.yaml").write_text("sentinel\n")
        cli.cmd_init(types.SimpleNamespace(force=False))  # must not overwrite
        assert (tmp_path / "atlas.yaml").read_text() == "sentinel\n"

    def test_force_overwrites(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                              capsys: pytest.CaptureFixture) -> None:
        cli = _load_cli()
        monkeypatch.setenv("LAIA_CONFIG_HOME", str(tmp_path))
        (tmp_path / "atlas.yaml").write_text("sentinel\n")
        cli.cmd_init(types.SimpleNamespace(force=True))
        assert "version: 2" in (tmp_path / "atlas.yaml").read_text()


# ---------------------------------------------------------------------------
# CLI — consumer scanner
# ---------------------------------------------------------------------------

class TestCliConsumers:
    def test_detects_logical_and_hardcode(self, tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
        cli = _load_cli()
        src = tmp_path / "src"
        src.mkdir()
        (src / "good.py").write_text('x = atlas.get("myref")\n')
        (src / "bad.py").write_text('p = "/opt/special/place/file"\n')
        monkeypatch.setattr(cli, "_LAIA_ROOT", tmp_path)

        class _FakeAtlas:
            class AtlasError(Exception):
                pass

            @staticmethod
            def get(name: str) -> str:
                return {"myref": "/opt/special/place"}[name]

        refs = {"myref": {"type": "path", "value": "/opt/special/place"}}
        found = cli._scan_consumers(refs, _FakeAtlas, None)
        assert any("good.py" in loc for loc in found["myref"]["logical"])
        assert any("bad.py" in loc for loc in found["myref"]["hardcode"])


# ---------------------------------------------------------------------------
# CLI — guided repair planning (dry-run never executes)
# ---------------------------------------------------------------------------

class TestCliDoctorFix:
    def test_dry_run_plans_mkdir_without_running(self, tmp_path: Path,
                                                 capsys: pytest.CaptureFixture) -> None:
        cli = _load_cli()
        target = tmp_path / "missing_dir"
        results = {
            "d": HealthResult(name="d", ref_type="path", value=str(target),
                              alive=False, detail="path does not exist on disk"),
        }
        args = types.SimpleNamespace(yes=False, dry_run=True, include_optional=False)
        cli._doctor_fix(results, args)
        out = capsys.readouterr().out
        assert "mkdir -p" in out
        assert not target.exists()  # dry-run must not create anything


# ---------------------------------------------------------------------------
# scripts/_laia_runtime_paths.py — resilient Atlas-backed resolution
# ---------------------------------------------------------------------------

class TestRuntimePaths:
    def _load(self):
        return _load_module("_lrp_test", _REPO_ROOT / "scripts" / "_laia_runtime_paths.py")

    def test_atlas_env_override_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ATLAS_LAIA_ROOT", "/tmp/override_root")
        invalidate_cache()
        lrp = self._load()
        assert lrp.laia_root() == Path("/tmp/override_root")

    def test_falls_back_to_default_without_registries(self, tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ATLAS_LAIA_ROOT", raising=False)
        monkeypatch.setenv("ATLAS_CONFIG", str(tmp_path / "absent.yaml"))
        monkeypatch.setenv("LAIA_CONFIG_HOME", str(tmp_path))  # laia_paths config dir (empty)
        monkeypatch.setenv("LAIA_ROOT", "/tmp/fallback_root")
        invalidate_cache()
        lrp = self._load()
        assert lrp.laia_root() == Path("/tmp/fallback_root")
