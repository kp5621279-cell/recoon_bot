FROM python:3.12-slim

# ffmpeg (music + yt-dlp) and libopus0 (voice encoding)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libopus0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -U yt-dlp

COPY . .

CMD ["python", "bot.py"]
