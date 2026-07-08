"""
Core unit tests for computer-use-agent.

Tests the pure utility functions that don't require a display or API key.
"""

import io
import os
import pathlib

import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png(width: int = 100, height: int = 80) -> bytes:
    """Return a minimal PNG of the given dimensions."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(128, 64, 32)).save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# image_utils tests
# ---------------------------------------------------------------------------

class TestImageUtils:
    def test_png_to_base64_returns_string(self):
        from agent.image_utils import png_to_base64

        b64 = png_to_base64(_make_png())
        assert isinstance(b64, str)
        assert len(b64) > 0

    def test_png_to_base64_is_valid_base64(self):
        import base64
        from agent.image_utils import png_to_base64

        b64 = png_to_base64(_make_png())
        # Should not raise
        decoded = base64.standard_b64decode(b64)
        assert decoded[:4] == b"\x89PNG"

    def test_resize_screenshot_reduces_large_image(self):
        from agent.image_utils import resize_screenshot

        large_png = _make_png(2560, 1600)
        resized = resize_screenshot(large_png, max_width=1280, max_height=800)
        img = Image.open(io.BytesIO(resized))
        assert img.width <= 1280
        assert img.height <= 800

    def test_resize_screenshot_preserves_small_image(self):
        from agent.image_utils import resize_screenshot

        small_png = _make_png(640, 480)
        resized = resize_screenshot(small_png, max_width=1280, max_height=800)
        img = Image.open(io.BytesIO(resized))
        # Small image should not be upscaled
        assert img.width <= 640
        assert img.height <= 480

    def test_screenshot_to_content_block_structure(self):
        from agent.image_utils import screenshot_to_content_block

        block = screenshot_to_content_block(_make_png())
        assert block["type"] == "image"
        assert block["source"]["type"] == "base64"
        assert block["source"]["media_type"] == "image/png"
        assert isinstance(block["source"]["data"], str)

    def test_prune_screenshots_no_pruning_when_under_limit(self):
        from agent.image_utils import prune_screenshots

        messages = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]}
        ]
        result = prune_screenshots(messages, max_screenshots=3)
        assert result == messages

    def test_prune_screenshots_removes_old_screenshots(self):
        from agent.image_utils import prune_screenshots, screenshot_to_content_block

        block = screenshot_to_content_block(_make_png())
        # Build 4 screenshot tool_result messages
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"id_{i}",
                        "content": [block.copy()],
                    }
                ],
            }
            for i in range(4)
        ]
        pruned = prune_screenshots(messages, max_screenshots=3)
        # First message's tool_result should have its image removed
        first_content = pruned[0]["content"][0]
        assert first_content["content"] == []

    def test_prune_screenshots_keeps_recent_screenshots(self):
        from agent.image_utils import prune_screenshots, screenshot_to_content_block

        block = screenshot_to_content_block(_make_png())
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"id_{i}",
                        "content": [block.copy()],
                    }
                ],
            }
            for i in range(4)
        ]
        pruned = prune_screenshots(messages, max_screenshots=3)
        # Last 3 messages should still have their images
        for msg in pruned[1:]:
            content_block = msg["content"][0]
            assert len(content_block["content"]) == 1
            assert content_block["content"][0]["type"] == "image"

    def test_prune_screenshots_does_not_mutate_original(self):
        from agent.image_utils import prune_screenshots, screenshot_to_content_block

        block = screenshot_to_content_block(_make_png())
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"id_{i}",
                        "content": [block.copy()],
                    }
                ],
            }
            for i in range(4)
        ]
        # Keep a reference to original first content list
        original_first_content = messages[0]["content"][0]["content"]
        prune_screenshots(messages, max_screenshots=3)
        # Original should be untouched
        assert len(original_first_content) == 1


# ---------------------------------------------------------------------------
# trajectory tests
# ---------------------------------------------------------------------------

class TestTrajectory:
    def setup_method(self):
        """Redirect trajectory to a temp file."""
        import agent.trajectory as t

        self._module = t
        self._orig = t.TRAJECTORY_FILE
        t.TRAJECTORY_FILE = pathlib.Path("/tmp/test_trajectory_pytest.json")
        t.clear_trajectory()

    def teardown_method(self):
        """Restore trajectory file path."""
        self._module.TRAJECTORY_FILE = self._orig
        tmp = pathlib.Path("/tmp/test_trajectory_pytest.json")
        if tmp.exists():
            tmp.unlink()

    def test_clear_trajectory_creates_empty_file(self):
        from agent.trajectory import clear_trajectory, load_trajectory

        clear_trajectory()
        assert load_trajectory() == []

    def test_record_action_appends_entry(self):
        from agent.trajectory import record_action, load_trajectory

        record_action("click", {"x": 10, "y": 20})
        traj = load_trajectory()
        assert len(traj) == 1
        assert traj[0]["action"] == "click"
        assert traj[0]["params"] == {"x": 10, "y": 20}

    def test_record_action_accumulates(self):
        from agent.trajectory import record_action, load_trajectory

        record_action("screenshot", {})
        record_action("type", {"text": "hello"})
        traj = load_trajectory()
        assert len(traj) == 2
        assert traj[1]["action"] == "type"

    def test_record_action_returns_entry(self):
        from agent.trajectory import record_action

        entry = record_action("key", {"key": "Return"})
        assert entry["action"] == "key"
        assert "timestamp" in entry

    def test_record_action_stores_result(self):
        from agent.trajectory import record_action, load_trajectory

        record_action("screenshot", {}, result="ok")
        traj = load_trajectory()
        assert traj[0]["result"] == "ok"

    def test_load_trajectory_handles_missing_file(self):
        import agent.trajectory as t

        t.TRAJECTORY_FILE = pathlib.Path("/tmp/nonexistent_trajectory_xyz.json")
        result = t.load_trajectory()
        assert result == []
        # Restore
        t.TRAJECTORY_FILE = pathlib.Path("/tmp/test_trajectory_pytest.json")

    def test_load_trajectory_handles_corrupt_file(self):
        import agent.trajectory as t

        t.TRAJECTORY_FILE.write_text("not valid json {{{")
        result = t.load_trajectory()
        assert result == []


# ---------------------------------------------------------------------------
# tools tests (non-display parts)
# ---------------------------------------------------------------------------

class TestTools:
    def test_computer_tool_definition_has_required_keys(self):
        from agent.tools import COMPUTER_TOOL_DEFINITION

        assert COMPUTER_TOOL_DEFINITION["type"] == "computer_20241022"
        assert COMPUTER_TOOL_DEFINITION["name"] == "computer"
        assert "display_width_px" in COMPUTER_TOOL_DEFINITION
        assert "display_height_px" in COMPUTER_TOOL_DEFINITION

    def test_execute_computer_tool_unknown_action(self):
        from agent.tools import execute_computer_tool
        import agent.trajectory as t

        orig = t.TRAJECTORY_FILE
        t.TRAJECTORY_FILE = pathlib.Path("/tmp/test_traj_tools.json")
        t.clear_trajectory()
        try:
            result = execute_computer_tool({"action": "unknown_action_xyz"})
            assert isinstance(result, list)
            assert result[0]["type"] == "text"
            assert "unknown" in result[0]["text"].lower()
        finally:
            t.TRAJECTORY_FILE = orig
            pathlib.Path("/tmp/test_traj_tools.json").unlink(missing_ok=True)
