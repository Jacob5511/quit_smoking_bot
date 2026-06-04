#!/bin/bash
set -e

echo "Starting Ollama..."
ollama serve &
OLLAMA_PID=$!

echo "Waiting for Ollama to be ready..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 1
done
echo "Ollama is up."

echo "Pulling model: ${OLLAMA_MODEL:-llama3.2}..."
ollama pull "${OLLAMA_MODEL:-llama3.2}"

echo "Starting Telegram bot..."
python bot.py

# If bot exits, kill ollama too
kill $OLLAMA_PID
