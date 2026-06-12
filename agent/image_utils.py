"""Screenshot capture and image pruning utilities."""

import base64
import io
import os
from typing import Optional

from PIL import Image


# Keep only the last N screenshots in the conversation context
MAX_SCREENSHOTS = 3


def capture_screenshot(display: Optional[str] = None) -> bytes:
    """
    Capture a screenshot.

    In Docker mode, reads from the Xvfb display via scrot/import.
    In demo mode, captures the real screen using pyautogui.

    Returns raw PNG bytes.
    """
    docker_mode = os.environ.get("DOCKER_MODE", "false").lower() == "true"

    if docker_mode:
        return _capture_xvfb(display or os.environ.get("DISPLAY", ":99"))
    else:
        return _capture_pyautogui()


def _capture_xvfb(display: str) -> bytes:
    """Capture from an Xvfb virtual display using scrot."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    try:
        env = os.environ.copy()
        env["DISPLAY"] = display
        subprocess.run(
            ["scrot", tmp_path],
            env=env,
            check=True,
            capture_output=True,
        )
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _capture_pyautogui() -> bytes:
    """Capture the real screen using pyautogui."""
    import pyautogui

    screenshot = pyautogui.screenshot()
    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    return buf.getvalue()


def png_to_base64(png_bytes: bytes) -> str:
    """Encode PNG bytes as a base64 string."""
    return base64.standard_b64encode(png_bytes).decode("utf-8")


def resize_screenshot(png_bytes: bytes, max_width: int = 1280, max_height: int = 800) -> bytes:
    """Resize a screenshot to fit within the given dimensions while preserving aspect ratio."""
    img = Image.open(io.BytesIO(png_bytes))
    img.thumbnail((max_width, max_height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def prune_screenshots(messages: list[dict], max_screenshots: int = MAX_SCREENSHOTS) -> list[dict]:
    """
    Remove old screenshot image blocks from the messages list, keeping only
    the most recent `max_screenshots` screenshots.

    This operates on the messages in-place conceptually but returns a new list.
    Only image blocks that are screenshots (tool_result content from computer tool)
    are pruned; other images are left untouched.
    """
    # Collect positions of all screenshot image blocks
    screenshot_positions: list[tuple[int, int]] = []  # (msg_index, content_index)

    for msg_idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for content_idx, block in enumerate(content):
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and isinstance(block.get("content"), list)
            ):
                for sub in block["content"]:
                    if isinstance(sub, dict) and sub.get("type") == "image":
                        screenshot_positions.append((msg_idx, content_idx))
                        break

    # If we have more than max_screenshots, blank out the older ones
    if len(screenshot_positions) <= max_screenshots:
        return messages

    to_blank = screenshot_positions[: len(screenshot_positions) - max_screenshots]
    # Deep-copy the messages so we don't mutate caller's list
    import copy

    pruned = copy.deepcopy(messages)
    for msg_idx, content_idx in to_blank:
        content = pruned[msg_idx]["content"]
        block = content[content_idx]
        if isinstance(block.get("content"), list):
            block["content"] = [
                sub
                for sub in block["content"]
                if not (isinstance(sub, dict) and sub.get("type") == "image")
            ]
    return pruned


def screenshot_to_content_block(png_bytes: bytes) -> dict:
    """Return an Anthropic image content block from raw PNG bytes."""
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": png_to_base64(png_bytes),
        },
    }
