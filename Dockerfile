FROM python:3.12-slim

WORKDIR /app

# Install Ollama
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://ollama.com/install.sh | sh && \
    apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
