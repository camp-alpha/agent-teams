FROM python:3.12-slim

# Install Node.js for Gemini CLI
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    rm -rf /var/lib/apt/lists/*

# Install Gemini CLI
RUN npm install -g @anthropic-ai/claude-code @anthropic-ai/claude-code || true
RUN npm install -g @anthropic-ai/gemini-cli || npm install -g gemini-cli || true

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .

CMD ["python", "-m", "agent_teams.bot.telegram_bot"]
