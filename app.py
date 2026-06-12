"""
Streamlit UI for the Computer Use Agent.

Features:
- Live screenshot display (updates as the agent runs)
- Action log with timestamps
- Task input and run controls
- Mode selector (demo / Docker)
- Trajectory viewer
"""

import base64
import io
import os
import queue
import threading
import time
from typing import Optional

import streamlit as st
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Computer Use Agent",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
def _init_state():
    defaults = {
        "running": False,
        "action_log": [],          # list of dicts: {time, action, params}
        "latest_screenshot": None, # base64 PNG string
        "agent_output": "",
        "task": "",
        "docker_mode": False,
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()

# ---------------------------------------------------------------------------
# CSS tweaks
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .action-entry {
        font-family: monospace;
        font-size: 0.82rem;
        background: #1e1e2e;
        color: #cdd6f4;
        padding: 4px 8px;
        border-radius: 4px;
        margin-bottom: 2px;
    }
    .action-entry .ts { color: #6c7086; }
    .action-entry .act { color: #89b4fa; font-weight: bold; }
    .agent-output {
        background: #1e1e2e;
        color: #a6e3a1;
        padding: 10px;
        border-radius: 6px;
        font-family: monospace;
        font-size: 0.9rem;
        white-space: pre-wrap;
        min-height: 80px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Settings")

    api_key_input = st.text_input(
        "Anthropic API Key",
        value=st.session_state.api_key,
        type="password",
        help="Set ANTHROPIC_API_KEY in .env to avoid re-entering.",
    )
    if api_key_input:
        st.session_state.api_key = api_key_input

    docker_mode = st.toggle(
        "Docker mode (virtual display)",
        value=st.session_state.docker_mode,
        help="ON = control Xvfb display inside Docker. OFF = demo mode (real screen via pyautogui).",
    )
    st.session_state.docker_mode = docker_mode
    os.environ["DOCKER_MODE"] = "true" if docker_mode else "false"

    st.divider()
    st.caption("Model: claude-sonnet-4-6")
    st.caption("Beta: computer-use-2024-10-22")
    st.caption("Caching: system prompt cached")
    st.caption("Image pruning: last 3 screenshots kept")

    st.divider()

    if st.button("Clear trajectory.json"):
        from agent.trajectory import clear_trajectory
        clear_trajectory()
        st.success("Trajectory cleared.")

    if st.button("View trajectory"):
        from agent.trajectory import load_trajectory
        traj = load_trajectory()
        st.json(traj)

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.title("Computer Use Agent")
st.caption("Powered by claude-sonnet-4-6 · computer-use-2024-10-22 beta")

col_left, col_right = st.columns([3, 2])

# ── LEFT: screenshot + task input ──────────────────────────────────────────
with col_left:
    st.subheader("Desktop View")
    screenshot_placeholder = st.empty()

    # Show latest screenshot or a placeholder
    if st.session_state.latest_screenshot:
        screenshot_placeholder.image(
            base64.b64decode(st.session_state.latest_screenshot),
            use_container_width=True,
            caption="Latest screenshot",
        )
    else:
        screenshot_placeholder.info("No screenshot yet — start a task to see the desktop.")

    st.subheader("Task")
    task_input = st.text_area(
        "Describe what you want the agent to do:",
        value=st.session_state.task,
        height=100,
        placeholder="e.g. Open Firefox and navigate to https://example.com",
    )
    st.session_state.task = task_input

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        run_btn = st.button(
            "Run Agent",
            type="primary",
            disabled=st.session_state.running,
            use_container_width=True,
        )
    with btn_col2:
        stop_btn = st.button(
            "Stop",
            disabled=not st.session_state.running,
            use_container_width=True,
        )

    st.subheader("Agent Output")
    output_placeholder = st.empty()
    output_placeholder.markdown(
        f'<div class="agent-output">{st.session_state.agent_output or "Agent output will appear here…"}</div>',
        unsafe_allow_html=True,
    )

# ── RIGHT: action log ───────────────────────────────────────────────────────
with col_right:
    st.subheader("Action Log")
    log_placeholder = st.empty()

    def _render_log():
        if not st.session_state.action_log:
            log_placeholder.info("No actions yet.")
            return
        html_parts = []
        for entry in reversed(st.session_state.action_log[-50:]):
            ts = entry.get("time", "")
            act = entry.get("action", "?")
            params = entry.get("params", {})
            # Build a brief param summary
            if act == "left_click":
                detail = f"({params.get('x')}, {params.get('y')})"
            elif act == "type":
                text_preview = str(params.get("text", ""))[:30]
                detail = f'"{text_preview}{"…" if len(str(params.get("text", ""))) > 30 else ""}"'
            elif act == "screenshot":
                detail = ""
            elif act == "key":
                detail = params.get("key", "")
            elif act == "scroll":
                detail = f"({params.get('x')}, {params.get('y')}) {params.get('direction')}"
            else:
                detail = str(params)[:40]
            html_parts.append(
                f'<div class="action-entry">'
                f'<span class="ts">{ts}</span> '
                f'<span class="act">{act}</span> '
                f'{detail}'
                f"</div>"
            )
        log_placeholder.markdown("\n".join(html_parts), unsafe_allow_html=True)

    _render_log()

# ---------------------------------------------------------------------------
# Agent thread machinery
# ---------------------------------------------------------------------------

# We use an event queue to pass updates from the agent thread back to
# the main thread on the next Streamlit rerun.
_update_queue: queue.Queue = queue.Queue()
_stop_event = threading.Event()


def _run_agent_thread(task: str, api_key: str):
    """Run the agent in a background thread, pushing updates to the queue."""
    try:
        from agent.computer_use_agent import ComputerUseAgent

        def on_action(action_type: str, params: dict, screenshot_b64: Optional[str]):
            ts = time.strftime("%H:%M:%S")
            _update_queue.put({
                "type": "action",
                "action": action_type,
                "params": params,
                "time": ts,
                "screenshot": screenshot_b64,
            })

        def on_message(text: str):
            _update_queue.put({"type": "message", "text": text})

        agent = ComputerUseAgent(
            api_key=api_key,
            on_action=on_action,
            on_message=on_message,
        )
        result = agent.run(task)
        _update_queue.put({"type": "done", "result": result})

    except Exception as exc:
        _update_queue.put({"type": "error", "error": str(exc)})


# ---------------------------------------------------------------------------
# Button handling
# ---------------------------------------------------------------------------
if run_btn and not st.session_state.running:
    if not st.session_state.task.strip():
        st.warning("Please enter a task first.")
    elif not st.session_state.api_key:
        st.error("No Anthropic API key. Set ANTHROPIC_API_KEY in .env or enter it in the sidebar.")
    else:
        st.session_state.running = True
        st.session_state.action_log = []
        st.session_state.agent_output = ""
        _stop_event.clear()

        t = threading.Thread(
            target=_run_agent_thread,
            args=(st.session_state.task, st.session_state.api_key),
            daemon=True,
        )
        t.start()
        st.rerun()

if stop_btn and st.session_state.running:
    _stop_event.set()
    st.session_state.running = False
    st.rerun()

# ---------------------------------------------------------------------------
# Drain the update queue and refresh UI
# ---------------------------------------------------------------------------
if st.session_state.running:
    # Drain up to 20 updates per rerun to avoid blocking
    updated = False
    for _ in range(20):
        try:
            event = _update_queue.get_nowait()
        except queue.Empty:
            break

        updated = True
        etype = event.get("type")

        if etype == "action":
            st.session_state.action_log.append({
                "time": event["time"],
                "action": event["action"],
                "params": event["params"],
            })
            if event.get("screenshot"):
                st.session_state.latest_screenshot = event["screenshot"]

        elif etype == "message":
            st.session_state.agent_output += event["text"]

        elif etype in ("done", "error"):
            st.session_state.running = False
            if etype == "done":
                st.session_state.agent_output += "\n\n" + event.get("result", "")
            else:
                st.session_state.agent_output += f"\n\nERROR: {event.get('error', 'Unknown error')}"

    # Always rerun while running so we poll the queue
    time.sleep(0.3)
    st.rerun()
