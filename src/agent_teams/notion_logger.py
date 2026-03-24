"""
Notion 대화 로거 — 모든 에이전트 대화를 Notion DB에 기록.

기록 내용:
  - 누가(From) → 누구에게(To)
  - 메시지 내용 (본문 블록으로)
  - 생각 흐름 (Thinking 필드)
  - 팀, 채널, 타임스탬프
"""

import json
import logging
import urllib.request
from datetime import datetime

from agent_teams.config import NOTION_API_TOKEN

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"
CONVERSATIONS_DB = "32d0fa99-3e17-8140-8970-e8a906acf5a2"


def _notion_request(method: str, endpoint: str, data: dict | None = None) -> dict:
    url = f"{NOTION_API}{endpoint}"
    body = json.dumps(data, ensure_ascii=False).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {NOTION_API_TOKEN}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.error(f"Notion request failed: {e}")
        return {}


def log_conversation(
    from_agent: str,
    to_agent: str,
    message: str,
    team: str = "",
    channel: str = "telegram",
    thinking: str = "",
    title_override: str = "",
):
    """대화를 Notion DB에 기록.

    Args:
        from_agent: 발신자 (User, Secretary, CEO, SRE, ...)
        to_agent: 수신자
        message: 메시지 내용
        team: 팀 이름 (secretary, startup, quant, infra)
        channel: 채널 (telegram, autopilot, scheduler, system)
        thinking: 생각 흐름/추론 과정
        title_override: 제목 오버라이드 (없으면 메시지 앞 50자)
    """
    if not NOTION_API_TOKEN:
        return

    now = datetime.now()
    title = title_override or message[:50].replace("\n", " ")

    properties = {
        "Title": {"title": [{"text": {"content": f"[{from_agent}→{to_agent}] {title}"}}]},
        "From": {"select": {"name": from_agent}},
        "To": {"select": {"name": to_agent}},
        "Timestamp": {"date": {"start": now.isoformat()}},
        "Channel": {"select": {"name": channel}},
    }

    if team:
        properties["Team"] = {"select": {"name": team}}

    if thinking:
        properties["Thinking"] = {"rich_text": [{"text": {"content": thinking[:2000]}}]}

    # 메시지 본문을 블록으로 추가 (2000자 단위 분할)
    children = []
    remaining = message
    while remaining:
        chunk = remaining[:2000]
        remaining = remaining[2000:]
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": chunk}}]
            }
        })

    payload = {
        "parent": {"database_id": CONVERSATIONS_DB},
        "properties": properties,
        "children": children[:10],  # Notion 제한: 최대 100 블록
    }

    try:
        _notion_request("POST", "/pages", payload)
    except Exception as e:
        logger.error(f"Notion log failed: {e}")
