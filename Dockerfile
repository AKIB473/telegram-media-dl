FROM python:3.12-slim

# Install ffmpeg for media processing
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install the tmdl CLI
RUN pip install --no-cache-dir -e .

CMD ["tmdl", "run"]
