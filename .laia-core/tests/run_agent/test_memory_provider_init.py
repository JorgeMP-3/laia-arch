"""Regression tests for memory provider selection during AIAgent init."""

from types import SimpleNamespace
from unittest.mock import patch


def test_blank_memory_provider_defaults_to_workspace_context():
    """Blank memory.provider must default to workspace-context (bundled core memory).

    Honcho (or any other provider with stale credentials) must still NOT auto-enable —
    only the bundled workspace-context is the canonical default.
    """
    cfg = {"memory": {"provider": ""}, "agent": {}}
    honcho_cfg = SimpleNamespace(enabled=True, api_key="stale-key", base_url=None)

    with (
        patch("laia_cli.config.load_config", return_value=cfg),
        patch("laia_cli.config.save_config") as save_config,
        patch(
            "plugins.memory.honcho.client.HonchoClientConfig.from_global_config",
            return_value=honcho_cfg,
        ) as from_global_config,
        patch("plugins.memory.load_memory_provider") as load_memory_provider,
        patch("agent.model_metadata.get_model_context_length", return_value=204_800),
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent

        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=False,
        )

    # workspace-context (bundled) must be selected and loaded.
    load_memory_provider.assert_called_with("workspace-context")
    assert agent._memory_manager is not None

    # Honcho must not have been auto-enabled by virtue of stale config.
    from_global_config.assert_not_called()
    save_config.assert_not_called()

