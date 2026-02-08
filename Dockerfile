FROM python:3.13-slim

# System deps for PyAudio (voice features) and Qt
RUN apt-get update && apt-get install -y --no-install-recommends \
        portaudio19-dev \
        libgl1 \
        libglib2.0-0 \
        libxkbcommon0 \
        libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: headless / API-only.  Override for GUI usage.
CMD ["python", "run.py", "--no-voice"]
