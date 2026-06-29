<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=200&color=0:0d47a1,50:ff006e,100:00ffff&text=Computer%20Use%20Agent&fontSize=44&fontColor=ffffff&animation=fadeIn&desc=Claude%20%C2%B7%20Streamlit%20%C2%B7%20Docker%20%C2%B7%20VNC&descAlignY=80&descSize=16" width="100%" alt="banner"/>
</div>

<div align="center">

![Python](https://img.shields.io/badge/Python_3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Anthropic](https://img.shields.io/badge/Claude_Sonnet_4.6-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Docker](https://img.shields.io/badge/Docker_sandbox-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![VNC](https://img.shields.io/badge/VNC_viewer-007ACC?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-00ff41?style=for-the-badge)

</div>

A desktop-control agent powered by **Claude Sonnet 4.6** and Anthropic's `computer-use-2024-10-22` beta. The agent **sees** your screen via screenshots, **plans** actions, and **drives** mouse and keyboard — through a clean Streamlit UI, with a Docker + VNC sandbox so it can't break your real desktop.

## 🏗️ How it works

```mermaid
flowchart LR
    U[User task] --> UI[Streamlit UI]
    UI --> L[🔁 Agentic loop]
    L -->|capture| SS[📸 Screenshot]
    SS -->|w/ cached system prompt| C[Claude Sonnet 4.6<br/>computer-use beta]
    C -->|tool_use:<br/>click / type / key / scroll| T[Tools]
    T -->|xdotool / pyautogui| DESK{{Desktop<br/>real or Docker}}
    DESK -->|new state| SS
    T -->|action log| TJ[(trajectory.json)]
    DESK -.->|VNC port 5900| VIEW[👁️ VNC viewer]
```

## ✨ Features

- 🤖 **Agentic loop** — screenshot → Claude → tool execution → repeat until done
- 💸 **Prompt caching** — system prompt flagged `cache_control: ephemeral` for low-cost long tasks
- 🖼️ **Image pruning** — keeps only the last 3 screenshots in context (stays under the window)
- 📼 **Trajectory recording** — every action appended to `trajectory.json` for replay / debugging
- 🛡️ **Docker sandbox** — Ubuntu + Xvfb + x11vnc + Firefox ESR; watch via VNC

---

## 🚀 Quick start (demo mode, real desktop)

```bash
git clone https://github.com/Dhanush-Aries/computer-use-agent.git
cd computer-use-agent

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                # add ANTHROPIC_API_KEY
streamlit run app.py                # http://localhost:8501
```

> ⚠️ **Demo mode** (`DOCKER_MODE=false`) drives your **real desktop** via pyautogui. Use the Docker sandbox below for safety.

---

## 🐳 Docker sandbox

```bash
cp .env.example .env                # add ANTHROPIC_API_KEY
docker compose up --build

# Streamlit UI  → http://localhost:8501
# VNC viewer    → localhost:5900     (no password)
```

The container runs an Xvfb virtual display (1280×800) with Firefox ESR. Point a VNC client at `localhost:5900` to watch the agent in real time.

---

## 📂 Project structure

```
computer-use-agent/
├── app.py                        # Streamlit UI
├── agent/
│   ├── computer_use_agent.py     # Main agentic loop + prompt caching
│   ├── tools.py                  # Computer-use tool defs & execution
│   ├── image_utils.py            # Screenshot capture + image pruning
│   └── trajectory.py             # Action recorder → trajectory.json
├── Dockerfile                    # Ubuntu + Xvfb + x11vnc + Firefox
├── docker-compose.yml
├── docker-entrypoint.sh
├── requirements.txt
└── .env.example
```

---

## ⚙️ Environment

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** |
| `DOCKER_MODE` | `false` | `true` → xdotool/scrot in Docker; `false` → pyautogui on real desktop |
| `DISPLAY` | `:99` | X display used in Docker mode |
| `SCREEN_WIDTH` | `1280` | Virtual display width (Docker) |
| `SCREEN_HEIGHT` | `800` | Virtual display height (Docker) |
| `VNC_PORT` | `5900` | VNC server port (Docker) |
| `STREAMLIT_PORT` | `8501` | Streamlit server port |

---

## 📼 Trajectory format

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

## ⚙️ Requirements

Python 3.11+ · `anthropic>=0.40.0` · `streamlit>=1.32.0` · `Pillow>=10.0.0` · `pyautogui>=0.9.54` (demo) · `python-dotenv>=1.0.0` · Docker + Compose (sandbox)

## 📜 License

MIT — see [LICENSE](./LICENSE)

---

<sub>Part of the <a href="https://github.com/Dhanush-Aries">Dhanush Shankar</a> AI engineering portfolio.</sub>
