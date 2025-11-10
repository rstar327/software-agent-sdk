"""
Minimal example demonstrating ACPAgent usage with the OpenHands SDK.

This example shows how to use ACPAgent to interact with ACP servers
(like Claude-Code or Gemini CLI) through the Agent-Client Protocol.

Prerequisites:
    - An ACP server command available (e.g., npx -y claude-code-acp)
    - API keys for the ACP server if required

Note:
    This is a minimal implementation. Many advanced SDK features
    (microagents, custom tools, security analyzers) are not yet supported.
"""

import os

from openhands.sdk import LLM, Conversation
from openhands.sdk.agent import ACPAgent
from openhands.sdk.event import MessageEvent


# Create an LLM configuration (required by AgentBase but not used by ACP server)
# The actual LLM is managed by the ACP server
llm = LLM(
    model="anthropic/claude-sonnet-4-5-20250929",
    api_key=os.getenv("LLM_API_KEY", "not-used-by-acp"),
)

# Create an ACPAgent that connects to an ACP server
# Example 1: Using Claude-Code ACP server (requires claude-code-acp to be available)
agent = ACPAgent(
    llm=llm,
    acp_command=["npx", "-y", "claude-code-acp"],
    acp_args=[],  # Add any additional arguments for the ACP server
)

# Example 2: Using a local ACP server script
# agent = ACPAgent(
#     llm=llm,
#     acp_command=["python", "/path/to/your/acp_server.py"],
#     acp_args=["--verbose"],
# )

# Example 3: Using Gemini CLI ACP server (hypothetical)
# agent = ACPAgent(
#     llm=llm,
#     acp_command=["gemini-cli-acp"],
#     acp_args=["--api-key", os.getenv("GEMINI_API_KEY")],
# )

# Create a conversation with the agent
cwd = os.getcwd()
conversation = Conversation(agent=agent, workspace=cwd)

# Send a message to the agent
print("Sending message to ACP agent...")
conversation.send_message("Hello! Please tell me about the Agent-Client Protocol.")

# Run the conversation
print("Running conversation...")
conversation.run()

# Access the events from the conversation state
print("\nConversation completed!")
print(f"Total events: {len(conversation.state.events)}")

# Print the last assistant message event
for event in reversed(list(conversation.state.events)):
    if isinstance(event, MessageEvent) and event.source == "agent":
        if event.llm_message and event.llm_message.content:
            for content in event.llm_message.content:
                print(f"\nAgent response: {content}")
        break

print("\nNote: The ACP server subprocess will be automatically cleaned up.")
