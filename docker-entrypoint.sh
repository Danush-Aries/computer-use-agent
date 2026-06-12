#!/bin/bash
set -e

# Start virtual display
Xvfb :99 -screen 0 1280x800x24 &
export DISPLAY=:99

# Give Xvfb time to start
sleep 1

# Start openbox window manager (needed for Firefox to render correctly)
openbox &

# Start x11vnc so you can connect and watch (port 5900, no password)
x11vnc -display :99 -nopw -listen localhost -xkb -forever -shared &

# Start Firefox in the background (optional - useful for testing)
# firefox --no-remote &

# Launch Streamlit
exec streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true
