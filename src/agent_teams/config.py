"""공통 설정."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
STATE_DIR = PROJECT_ROOT / "state"
STATE_DIR.mkdir(exist_ok=True)

# ── 환경변수 ──
def _load_env():
    for env_path in [PROJECT_ROOT / ".env"]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k, v)

_load_env()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BIN = os.environ.get("GEMINI_BIN", "gemini")
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

# Notion
NOTION_API_TOKEN = os.environ.get("NOTION_API_TOKEN", "")
NOTION_IDS = {
    "ideas": os.environ.get("NOTION_IDEAS_DB", ""),
}

METRICS_FILE = STATE_DIR / "metrics.jsonl"

# 봇 소유자 (등록 가능한 유일한 사용자)
OWNER_ID = int(os.environ.get("OWNER_ID", "8157972337"))
