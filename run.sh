#!/bin/bash
cd "$(dirname "$0")"
[ -f .env ] && export $(grep -v '^#' .env | xargs)
PYTHONPATH=src python3 -m agent_teams.bot.telegram_bot
