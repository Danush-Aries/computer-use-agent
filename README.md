# Claude Computer Use Agent

A desktop-control agent powered by **claude-sonnet-4-6** and Anthropic's
`computer-use-2024-10-22` beta.  The agent sees your screen via screenshots,
plans actions, and drives mouse/keyboard through a clean Streamlit UI.

Key features:

- **Agentic loop** — screenshot → Claude → tool execution → repeat until task complete
- **Prompt caching** — system prompt placed under `cache_control` for lower cost on long tasks
- **Image pruning** — keeps only the last 3 screenshots in context to stay within the context window
- **Trajectory recording** — every action is appended to `trajectory.json` for replay / debugging
- **Docker sandbox** — Ubuntu + Xvfb + x11vnc + Firefox ESR; watch the virtual desktop over VNC

---

## Quick start (local desktop, demo mode)

```bash
# 1. Clone and enter the repo
git clone https://github.com/Dhanush-Aries/computer-use-agent.git
cd computer-use-agent

# 2. Create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# 5. Launch the UI
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501), type a task, and watch
the agent control your desktop.

> **Note:** In demo mode (`DOCKER_MODE=false`) the agent controls your *real*
> desktop via pyautogui.  Run inside the Docker container (below) for a safe
> sandboxed environment.

---

## Docker sandbox

```bash
# Build and start
cp .env.example .env   # add your ANTHROPIC_API_KEY
docker compose up --build

# Streamlit UI  → http://localhost:8501
# VNC viewer    → localhost:5900  (no password)
```

The container runs an Xvfb virtual display (1280×800) with Firefox ESR.
Connect a VNC client to `localhost:5900` to watch the agent work in real time.

---

## Project structure

```
computer-use-agent/
├── app.py                        # Streamlit UI
├── agent/
│   ├── __init__.py
│   ├── computer_use_agent.py     # Main agentic loop + prompt caching
│   ├── tools.py                  # Computer-use tool definitions & execution
│   ├── image_utils.py            # Screenshot capture + image pruning
│   └── trajectory.py             # Action recorder → trajectory.json
├── Dockerfile                    # Ubuntu + Xvfb + x11vnc + Firefox
├── docker-compose.yml
├── docker-entrypoint.sh
├── requirements.txt
├── .env.example
└── README.md
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key. |
| `DOCKER_MODE` | `false` | `true` → use xdotool/scrot inside Docker; `false` → use pyautogui on real desktop. |
| `DISPLAY` | `:99` | X display used in Docker mode. |
| `SCREEN_WIDTH` | `1280` | Virtual display width (Docker). |
| `SCREEN_HEIGHT` | `800` | Virtual display height (Docker). |
| `VNC_PORT` | `5900` | VNC server port (Docker). |
| `STREAMLIT_PORT` | `8501` | Streamlit server port. |

---

## How prompt caching works

The system prompt is passed as a list with a single block containing
`"cache_control": {"type": "ephemeral"}`.  On the first request Anthropic
caches the prompt; every subsequent request in the same task reuses the cache,
cutting input-token costs significantly on long multi-step tasks.

---

## Trajectory format

`trajectory.json` is a JSON array of action objects:

```json
[
  {
    "timestamp": 1718234567.123,
    "action": "left_click",
    "params": {"x": 640, "y": 400},
    "result": null
  }
]
```

---

## Requirements

- Python 3.11+
- `anthropic>=0.40.0`
- `streamlit>=1.32.0`
- `Pillow>=10.0.0`
- `pyautogui>=0.9.54` (demo mode only)
- `python-dotenv>=1.0.0`
- Docker + Docker Compose (sandbox mode)
