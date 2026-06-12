"""
Main agent loop for the Computer Use Agent.

Uses claude-sonnet-4-6 with the computer-use-2024-10-22 beta.
Implements:
  - Manual agentic loop (screenshot → Claude → tool execution → loop)
  - Prompt caching on the system prompt (cache_control)
  - Image pruning (keeps last 3 screenshots in context)
  - Trajectory recording
  - Callback hooks so the Streamlit UI can observe progress in real time
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Optional

import anthropic
from dotenv import load_dotenv

from .image_utils import capture_screenshot, resize_screenshot, screenshot_to_content_block, prune_screenshots
from .tools import COMPUTER_TOOL_DEFINITION, execute_computer_tool
from .trajectory import record_action, clear_trajectory

load_dotenv()

MODEL = "claude-sonnet-4-6"
BETA_HEADER = "computer-use-2024-10-22"
MAX_ITERATIONS = 50

# Stable system prompt — placed under cache_control so it is cached after
# the first request and served cheaply on every subsequent turn.
SYSTEM_PROMPT = """You are a computer use agent that can see and control a desktop.
You have access to a computer tool that lets you take screenshots, click, type, scroll, and press keys.

Instructions:
- Always start by taking a screenshot to understand the current state of the screen.
- Think step by step about how to accomplish the task.
- After every action (click, type, key, scroll), take another screenshot to see the result.
- If something doesn't work as expected, try an alternative approach.
- When the task is complete, say "TASK COMPLETE" followed by a brief summary of what you accomplished.
- If you cannot complete the task, say "TASK FAILED" followed by the reason.

Display resolution: 1280x800.
Coordinates are (x, y) where (0, 0) is the top-left corner.
"""

# ---------------------------------------------------------------------------
# ActionCallback type: called after each tool execution step
# Signature: callback(action_type, params, screenshot_b64_or_none)
# ---------------------------------------------------------------------------
ActionCallback = Callable[[str, dict, Optional[str]], None]


class ComputerUseAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        on_action: Optional[ActionCallback] = None,
        on_message: Optional[Callable[[str], None]] = None,
    ):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.on_action = on_action  # called each time a tool is executed
        self.on_message = on_message  # called each time Claude produces text

    def run(self, task: str, clear_history: bool = True) -> str:
        """
        Run the agent on the given task.

        Returns the final text response from the agent.
        """
        if clear_history:
            clear_trajectory()

        # Seed with an initial screenshot so Claude has context immediately
        initial_png = capture_screenshot()
        initial_png = resize_screenshot(initial_png)
        record_action("initial_screenshot", {})

        messages: list[dict] = [
            {
                "role": "user",
                "content": [
                    screenshot_to_content_block(initial_png),
                    {"type": "text", "text": task},
                ],
            }
        ]

        # Cached system prompt — stable content placed under cache_control.
        # The system prompt never changes so it will be served from cache on
        # all requests after the first one (significant cost reduction on long
        # multi-step tasks).
        system = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        for iteration in range(MAX_ITERATIONS):
            # Prune old screenshots to keep context lean
            pruned_messages = prune_screenshots(messages)

            response = self.client.beta.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system,
                tools=[COMPUTER_TOOL_DEFINITION],
                messages=pruned_messages,
                betas=[BETA_HEADER],
            )

            # Collect assistant text for display / return
            assistant_text = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    assistant_text += block.text
                    if self.on_message:
                        self.on_message(block.text)

            # Append the full assistant response (including tool_use blocks)
            messages.append({"role": "assistant", "content": response.content})

            # If Claude is done, return
            if response.stop_reason == "end_turn":
                record_action("agent_done", {"final_text": assistant_text})
                return assistant_text

            # Process tool calls
            if response.stop_reason == "tool_use":
                tool_results: list[dict] = []

                for block in response.content:
                    if not (hasattr(block, "type") and block.type == "tool_use"):
                        continue

                    tool_name: str = block.name
                    tool_input: dict[str, Any] = block.input
                    tool_use_id: str = block.id

                    # Execute the tool
                    result_content = execute_computer_tool(tool_input)

                    # Fire UI callback
                    if self.on_action:
                        screenshot_b64 = None
                        for rc in result_content:
                            if isinstance(rc, dict) and rc.get("type") == "image":
                                screenshot_b64 = rc.get("source", {}).get("data")
                                break
                        self.on_action(
                            tool_input.get("action", tool_name),
                            tool_input,
                            screenshot_b64,
                        )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_content,
                        }
                    )

                # Append all tool results in a single user message
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason — bail out
            break

        return f"Agent stopped after {MAX_ITERATIONS} iterations without completing the task."
