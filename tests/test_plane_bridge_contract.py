"""Contract pin: the PlaneClient surface the agora-plane-forwarder relies on.

The REST contract for Plane lives in ONE place — the satellite package
``laia_plane_bridge`` (S6 §3.1, reuse-not-duplicate). This test pins the
exact client surface the Core plugin calls, so a satellite-side refactor
breaks HERE (CI) and not inside laia-agora.

Live-dependency rule: the package is installed at deploy time; without it
this skips cleanly (run with PYTHONPATH to the satellite's plane/bridge for
the full check, e.g. in laia-dev).
"""

import inspect

import pytest

client_mod = pytest.importorskip(
    "laia_plane_bridge.client",
    reason="laia_plane_bridge not installed (satellite package; see S6 design note)",
)


EXPECTED = {
    "create_work_item": ["project_id", "name", "description_html", "extra"],
    "add_comment": ["project_id", "work_item_id", "comment_html"],
    "update_work_item": ["project_id", "work_item_id", "patch"],
    "add_link": ["project_id", "work_item_id", "url", "title"],
}


def test_client_constructor_contract():
    sig = inspect.signature(client_mod.PlaneClient.__init__)
    params = list(sig.parameters)
    assert params[1:4] == ["base_url", "api_key", "workspace_slug"]


@pytest.mark.parametrize("method,expected_params", sorted(EXPECTED.items()))
def test_client_method_contract(method, expected_params):
    fn = getattr(client_mod.PlaneClient, method)
    assert inspect.iscoroutinefunction(fn), f"{method} must stay async"
    params = [p for p in inspect.signature(fn).parameters if p != "self"]
    assert params == expected_params, (
        f"PlaneClient.{method} signature drifted — update the forwarder "
        f"plugin AND this pin together")


def test_typed_errors_exported():
    assert issubclass(client_mod.PlaneClientError, Exception)
