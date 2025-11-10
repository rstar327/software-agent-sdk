"""Test ACPAgent functionality."""

from unittest.mock import Mock, patch

import pytest

from openhands.sdk.agent.acp_agent import ACPAgent
from openhands.sdk.tool.spec import Tool


def test_acp_agent_initialization():
    """Test that ACPAgent can be initialized without LLM."""
    agent = ACPAgent(
        acp_command=["echo", "test"],
    )
    assert agent.acp_command == ["echo", "test"]
    assert agent.acp_args == []
    assert agent.acp_cwd is None
    assert agent.llm is None


def test_acp_agent_with_args():
    """Test ACPAgent initialization with additional arguments."""
    agent = ACPAgent(
        acp_command=["python", "-m", "acp_server"],
        acp_args=["--verbose"],
        acp_cwd="/tmp/test",
    )
    assert agent.acp_command == ["python", "-m", "acp_server"]
    assert agent.acp_args == ["--verbose"]
    assert agent.acp_cwd == "/tmp/test"
    assert agent.llm is None


def test_acp_agent_rejects_tools():
    """Test that ACPAgent raises error when tools are provided."""
    from openhands.sdk.conversation.state import ConversationState

    agent = ACPAgent(
        acp_command=["test"],
        tools=[Tool(name="test_tool")],
    )
    state = Mock(spec=ConversationState)

    with pytest.raises(
        NotImplementedError, match="ACPAgent does not yet support custom tools"
    ):
        agent.init_state(state, on_event=Mock())


def test_acp_agent_rejects_mcp_config():
    """Test that ACPAgent raises error when MCP config is provided."""
    from openhands.sdk.conversation.state import ConversationState

    agent = ACPAgent(
        acp_command=["test"],
        mcp_config={"test": "config"},
    )
    state = Mock(spec=ConversationState)

    with pytest.raises(NotImplementedError, match="ACPAgent does not yet support MCP"):
        agent.init_state(state, on_event=Mock())


@patch("subprocess.Popen")
def test_acp_agent_start_server(mock_popen):
    """Test that ACP server can be started."""
    agent = ACPAgent(
        acp_command=["python", "-m", "acp_server"],
    )

    mock_process = Mock()
    mock_process.stdin = Mock()
    mock_process.stdout = Mock()
    mock_process.poll.return_value = None
    mock_popen.return_value = mock_process

    agent._start_acp_server("/tmp/workspace")

    mock_popen.assert_called_once()
    assert agent._process == mock_process
