"""
ACPAgent: An Agent-Client Protocol client implementation for OpenHands SDK.

This agent acts as an ACP client that communicates with ACP servers
(like Claude-Code, Gemini CLI) to provide AI agent capabilities through
the Agent-Client Protocol (https://agentclientprotocol.com/).
"""

import json
import subprocess
from typing import TYPE_CHECKING, Any

from pydantic import Field

from openhands.sdk.agent.base import AgentBase
from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands.sdk.event import MessageEvent
from openhands.sdk.llm import Message, TextContent
from openhands.sdk.logger import get_logger


if TYPE_CHECKING:
    from openhands.sdk.conversation import (
        ConversationCallbackType,
        ConversationState,
        LocalConversation,
    )

logger = get_logger(__name__)


class ACPAgent(AgentBase):
    """
    ACPAgent is an Agent-Client Protocol client implementation.

    This agent communicates with ACP servers (like Claude-Code or Gemini CLI)
    to provide AI agent capabilities. It translates OpenHands SDK conversation
    states into ACP protocol messages and vice versa.

    Note:
        ACP servers manage their own LLM configuration internally, so the `llm`
        parameter is optional and not used by the ACP protocol. It's only kept
        for compatibility with AgentBase.

    Example:
        >>> from openhands.sdk.agent import ACPAgent
        >>> agent = ACPAgent(
        ...     acp_command=["npx", "-y", "claude-code-acp"],
        ...     acp_args=[]
        ... )
        >>> conversation = Conversation(agent=agent, workspace="/tmp/workspace")
        >>> conversation.send_message("Hello!")
        >>> conversation.run()

    Note:
        This is a minimal implementation focusing on basic ACP protocol support.
        Many advanced SDK features (like microagents, custom tools, security
        analyzers) are not yet supported and will raise NotImplementedError.
    """

    llm: Any = Field(  # type: ignore[assignment]
        default=None,
        description=(
            "LLM configuration (not used by ACP - ACP servers manage their "
            "own LLM). Kept for AgentBase compatibility."
        ),
    )

    acp_command: list[str] = Field(
        ...,
        description=(
            "Command to start the ACP server subprocess. "
            "Example: ['npx', '-y', 'claude-code-acp']"
        ),
    )
    acp_args: list[str] = Field(
        default_factory=list,
        description="Additional arguments to pass to the ACP server command.",
    )
    acp_cwd: str | None = Field(
        default=None,
        description=(
            "Working directory for the ACP server process. "
            "If None, uses the conversation workspace."
        ),
    )

    _process: subprocess.Popen[bytes] | None = None
    _session_id: str | None = None
    _message_id: int = 0

    def _check_unsupported_features(self) -> None:
        """Check for unsupported features and raise errors."""
        if self.tools and len(self.tools) > 0:
            raise NotImplementedError(
                "ACPAgent does not yet support custom tools. "
                "The ACP server manages its own tools."
            )

        if self.mcp_config:
            raise NotImplementedError(
                "ACPAgent does not yet support MCP configuration. "
                "MCP integration should be configured at the ACP server level."
            )

        if self.agent_context:
            raise NotImplementedError(
                "ACPAgent does not yet support AgentContext (microagents). "
                "This is a known limitation and will be addressed in future versions."
            )

        if self.security_analyzer:
            raise NotImplementedError(
                "ACPAgent does not yet support security analyzers. "
                "Security policies should be managed at the ACP server level."
            )

        if self.condenser:
            raise NotImplementedError(
                "ACPAgent does not yet support context condensers. "
                "Context management is handled by the ACP server."
            )

    def init_state(
        self,
        state: "ConversationState",  # noqa: F821
        on_event: "ConversationCallbackType",
    ) -> None:
        """Initialize the agent state and check for unsupported features."""
        self._check_unsupported_features()
        super().init_state(state, on_event=on_event)

    def _get_next_message_id(self) -> int:
        """Generate the next JSON-RPC message ID."""
        self._message_id += 1
        return self._message_id

    def _start_acp_server(self, workspace_dir: str) -> None:
        """Start the ACP server subprocess."""
        if self._process is not None:
            logger.warning("ACP server already running")
            return

        cwd = self.acp_cwd or workspace_dir
        full_command = self.acp_command + self.acp_args

        logger.info(f"Starting ACP server: {' '.join(full_command)} in {cwd}")

        self._process = subprocess.Popen(
            full_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )

    def _stop_acp_server(self) -> None:
        """Stop the ACP server subprocess."""
        if self._process is None:
            return

        logger.info("Stopping ACP server")
        if self._process.stdin:
            self._process.stdin.close()
        if self._process.stdout:
            self._process.stdout.close()
        if self._process.stderr:
            self._process.stderr.close()

        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("ACP server did not terminate, killing")
            self._process.kill()
            self._process.wait()

        self._process = None
        self._session_id = None

    def _send_jsonrpc_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a JSON-RPC request to the ACP server and return the response."""
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("ACP server not started")

        message_id = self._get_next_message_id()
        request = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params or {},
        }

        request_json = json.dumps(request) + "\n"
        logger.debug(f"Sending to ACP server: {request_json.strip()}")

        self._process.stdin.write(request_json.encode("utf-8"))
        self._process.stdin.flush()

        # Read response
        if self._process.stdout is None:
            raise RuntimeError("ACP server stdout not available")

        response_line = self._process.stdout.readline().decode("utf-8")
        logger.debug(f"Received from ACP server: {response_line.strip()}")

        response = json.loads(response_line)

        if "error" in response:
            error = response["error"]
            raise RuntimeError(
                f"ACP server error: {error.get('message', 'Unknown error')}"
            )

        return response.get("result", {})

    def _initialize_acp_session(self) -> None:
        """Initialize the ACP session (initialize + session/new)."""
        # Step 1: Initialize
        init_result = self._send_jsonrpc_request(
            "initialize",
            {
                "protocolVersion": "1.0",
                "clientInfo": {
                    "name": "openhands-sdk",
                    "version": "1.0.0",
                },
            },
        )
        logger.info(
            f"ACP server initialized: {init_result.get('serverInfo', {}).get('name')}"
        )

        # Step 2: Create new session
        session_result = self._send_jsonrpc_request("session/new", {})
        self._session_id = session_result.get("sessionId")
        logger.info(f"Created ACP session: {self._session_id}")

    def step(
        self,
        conversation: "LocalConversation",
        on_event: "ConversationCallbackType",
    ) -> None:
        """
        Execute one step of the agent.

        This method:
        1. Starts the ACP server if not already running
        2. Initializes the ACP session if needed
        3. Sends the latest user message to the ACP server via session/prompt
        4. Processes the response and adds it to the conversation
        """
        state = conversation.state

        # Start ACP server if needed
        if self._process is None:
            self._start_acp_server(conversation.workspace.working_dir)
            self._initialize_acp_session()

        # Get the latest user message from the conversation
        user_messages = [
            event
            for event in state.events
            if isinstance(event, MessageEvent) and event.source == "user"
        ]

        if not user_messages:
            logger.warning("No user messages found in conversation")
            state.execution_status = ConversationExecutionStatus.FINISHED
            return

        latest_message = user_messages[-1]

        # Extract text from the message
        message_text = ""
        if latest_message.llm_message and latest_message.llm_message.content:
            for content in latest_message.llm_message.content:
                if isinstance(content, TextContent):
                    message_text += content.text

        if not message_text:
            logger.warning("Latest user message has no text content")
            state.execution_status = ConversationExecutionStatus.FINISHED
            return

        logger.info(f"Sending prompt to ACP server: {message_text[:100]}...")

        # Send prompt to ACP server
        try:
            prompt_result = self._send_jsonrpc_request(
                "session/prompt",
                {
                    "sessionId": self._session_id,
                    "prompt": message_text,
                },
            )

            # Extract response from ACP server
            response_text = prompt_result.get("response", "")

            if not response_text:
                response_text = (
                    "The ACP server completed the task but returned no response."
                )

            logger.info(f"Received response from ACP server: {response_text[:100]}...")

            # Create a message event with the response
            response_message = MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant",
                    content=[TextContent(text=response_text)],
                ),
            )
            on_event(response_message)

            # Mark conversation as finished
            state.execution_status = ConversationExecutionStatus.FINISHED

        except Exception as e:
            logger.error(f"Error communicating with ACP server: {e}")
            error_message = MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant",
                    content=[
                        TextContent(
                            text=f"Error communicating with ACP server: {str(e)}"
                        )
                    ],
                ),
            )
            on_event(error_message)
            state.execution_status = ConversationExecutionStatus.FINISHED
            raise

    def __del__(self):
        """Cleanup: stop the ACP server on deletion."""
        self._stop_acp_server()
