# Ubuntu 22.04 with Xvfb virtual display, x11vnc, Firefox, and Python
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV DOCKER_MODE=true

# Core system packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    xvfb \
    x11vnc \
    scrot \
    xdotool \
    firefox \
    openbox \
    x11-utils \
    x11-xserver-utils \
    dbus-x11 \
    libx11-dev \
    libxtst-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Start Xvfb, openbox window manager, and then Streamlit
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8501 5900

ENTRYPOINT ["/entrypoint.sh"]
