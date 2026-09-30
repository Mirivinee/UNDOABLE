# Sandbox for running Claude Code autonomously on UNDOABLE.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g @anthropic-ai/claude-code && pip install --no-cache-dir ruff pytest
RUN useradd -m dev
USER dev
WORKDIR /work
