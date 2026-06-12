"""
Computer Use tool definitions and execution.

Implements the computer-use-2024-10-22 beta tool spec:
screenshot, click, double_click, right_click, type, key, scroll, mouse_move.
"""

import os
import time
from typing import Any

from .image_utils import capture_screenshot, resize_screenshot, screenshot_to_content_block
from .trajectory import record_action


# The beta tool definition sent to the Anthropic API
COMPUTER_TOOL_DEFINITION = {
    "type": "computer_20241022",
    "name": "computer",
    "display_width_px": 1280,
    "display_height_px": 800,
    "display_number": 1,
}


def execute_computer_tool(tool_input: dict[str, Any]) -> list[dict]:
    """
    Execute a computer-use tool action and return the tool_result content blocks.

    Returns a list of content blocks suitable for a tool_result message:
      - For screenshot actions: [image_block]
      - For other actions: [text_block]  (followed by an automatic screenshot)
    """
    action = tool_input.get("action", "")
    docker_mode = os.environ.get("DOCKER_MODE", "false").lower() == "true"

    if action == "screenshot":
        png = capture_screenshot()
        png = resize_screenshot(png)
        record_action("screenshot", {})
        return [screenshot_to_content_block(png)]

    elif action == "left_click":
        x, y = int(tool_input["coordinate"][0]), int(tool_input["coordinate"][1])
        _click(x, y, button="left", docker=docker_mode)
        record_action("left_click", {"x": x, "y": y})
        return _take_post_action_screenshot()

    elif action == "double_click":
        x, y = int(tool_input["coordinate"][0]), int(tool_input["coordinate"][1])
        _click(x, y, button="left", double=True, docker=docker_mode)
        record_action("double_click", {"x": x, "y": y})
        return _take_post_action_screenshot()

    elif action == "right_click":
        x, y = int(tool_input["coordinate"][0]), int(tool_input["coordinate"][1])
        _click(x, y, button="right", docker=docker_mode)
        record_action("right_click", {"x": x, "y": y})
        return _take_post_action_screenshot()

    elif action == "type":
        text = tool_input.get("text", "")
        _type_text(text, docker=docker_mode)
        record_action("type", {"text": text})
        return _take_post_action_screenshot()

    elif action == "key":
        key = tool_input.get("key", "")
        _press_key(key, docker=docker_mode)
        record_action("key", {"key": key})
        return _take_post_action_screenshot()

    elif action == "scroll":
        x, y = int(tool_input["coordinate"][0]), int(tool_input["coordinate"][1])
        direction = tool_input.get("direction", "down")
        amount = int(tool_input.get("amount", 3))
        _scroll(x, y, direction, amount, docker=docker_mode)
        record_action("scroll", {"x": x, "y": y, "direction": direction, "amount": amount})
        return _take_post_action_screenshot()

    elif action == "mouse_move":
        x, y = int(tool_input["coordinate"][0]), int(tool_input["coordinate"][1])
        _mouse_move(x, y, docker=docker_mode)
        record_action("mouse_move", {"x": x, "y": y})
        return [{"type": "text", "text": f"Moved mouse to ({x}, {y})"}]

    elif action == "left_click_drag":
        start = tool_input["start_coordinate"]
        end = tool_input["coordinate"]
        sx, sy = int(start[0]), int(start[1])
        ex, ey = int(end[0]), int(end[1])
        _drag(sx, sy, ex, ey, docker=docker_mode)
        record_action("left_click_drag", {"from": [sx, sy], "to": [ex, ey]})
        return _take_post_action_screenshot()

    else:
        record_action("unknown_action", {"action": action, "input": tool_input})
        return [{"type": "text", "text": f"Unknown action: {action}"}]


def _take_post_action_screenshot() -> list[dict]:
    """Take a screenshot after an action and return it as a content block."""
    time.sleep(0.5)  # brief settle time
    png = capture_screenshot()
    png = resize_screenshot(png)
    return [screenshot_to_content_block(png)]


# ---------------------------------------------------------------------------
# Low-level input dispatch — Docker vs. demo (pyautogui)
# ---------------------------------------------------------------------------

def _xdo_cmd(cmd: list[str], display: str = ":99") -> None:
    """Run an xdotool command against the virtual display."""
    import subprocess

    env = os.environ.copy()
    env["DISPLAY"] = display
    subprocess.run(["xdotool"] + cmd, env=env, check=True, capture_output=True)


def _click(x: int, y: int, button: str = "left", double: bool = False,
           docker: bool = False) -> None:
    if docker:
        display = os.environ.get("DISPLAY", ":99")
        btn_map = {"left": "1", "middle": "2", "right": "3"}
        btn = btn_map.get(button, "1")
        if double:
            _xdo_cmd(["mousemove", "--sync", str(x), str(y)], display)
            _xdo_cmd(["click", "--repeat", "2", btn], display)
        else:
            _xdo_cmd(["mousemove", "--sync", str(x), str(y)], display)
            _xdo_cmd(["click", btn], display)
    else:
        import pyautogui

        pyautogui.moveTo(x, y, duration=0.1)
        if double:
            pyautogui.doubleClick()
        elif button == "right":
            pyautogui.rightClick()
        else:
            pyautogui.click()


def _type_text(text: str, docker: bool = False) -> None:
    if docker:
        display = os.environ.get("DISPLAY", ":99")
        _xdo_cmd(["type", "--clearmodifiers", text], display)
    else:
        import pyautogui

        pyautogui.typewrite(text, interval=0.02)


def _press_key(key: str, docker: bool = False) -> None:
    """Press a key. Supports xdotool key names (e.g. 'Return', 'ctrl+c')."""
    if docker:
        display = os.environ.get("DISPLAY", ":99")
        _xdo_cmd(["key", key], display)
    else:
        import pyautogui

        # Convert common xdotool names to pyautogui names
        key_map = {
            "Return": "enter",
            "BackSpace": "backspace",
            "Tab": "tab",
            "Escape": "escape",
            "Delete": "delete",
            "ctrl+c": "ctrl+c",
            "ctrl+v": "ctrl+v",
            "ctrl+a": "ctrl+a",
            "ctrl+z": "ctrl+z",
        }
        mapped = key_map.get(key, key)
        if "+" in mapped:
            parts = mapped.split("+")
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(mapped)


def _scroll(x: int, y: int, direction: str, amount: int, docker: bool = False) -> None:
    if docker:
        display = os.environ.get("DISPLAY", ":99")
        _xdo_cmd(["mousemove", "--sync", str(x), str(y)], display)
        btn = "4" if direction == "up" else "5"
        for _ in range(amount):
            _xdo_cmd(["click", btn], display)
    else:
        import pyautogui

        pyautogui.moveTo(x, y, duration=0.1)
        clicks = amount if direction == "down" else -amount
        pyautogui.scroll(clicks)


def _mouse_move(x: int, y: int, docker: bool = False) -> None:
    if docker:
        display = os.environ.get("DISPLAY", ":99")
        _xdo_cmd(["mousemove", "--sync", str(x), str(y)], display)
    else:
        import pyautogui

        pyautogui.moveTo(x, y, duration=0.1)


def _drag(sx: int, sy: int, ex: int, ey: int, docker: bool = False) -> None:
    if docker:
        display = os.environ.get("DISPLAY", ":99")
        _xdo_cmd(["mousemove", "--sync", str(sx), str(sy)], display)
        _xdo_cmd(["mousedown", "1"], display)
        _xdo_cmd(["mousemove", "--sync", str(ex), str(ey)], display)
        _xdo_cmd(["mouseup", "1"], display)
    else:
        import pyautogui

        pyautogui.mouseDown(sx, sy)
        pyautogui.moveTo(ex, ey, duration=0.3)
        pyautogui.mouseUp()
