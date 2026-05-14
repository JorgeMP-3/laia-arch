import os, tempfile, pytest

@pytest.fixture(autouse=True)
def _force_dev_env(monkeypatch):
    """Force tests to use a temp dir, not production /srv/laia/."""
    tmp = tempfile.mkdtemp(prefix="agora_test_")
    monkeypatch.setenv("AGORA_ENV", "dev")
    monkeypatch.setenv("AGORA_DATA_DIR", tmp)
    monkeypatch.setenv("AGORA_DEV_DATA_DIR", tmp)
    yield
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
