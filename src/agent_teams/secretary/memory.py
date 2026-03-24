"""
Secretary 메모리 시스템 — 대화에서 학습하고 맥락을 유지.

Google always-on-memory-agent에서 영감받되,
패시브 기억이 아니라 프로액티브 대화 생성에 사용.

구조:
  - facts: 사용자에 대해 알게 된 사실들
  - conversations: 최근 대화 요약
  - pending: 팔로업이 필요한 항목들
  - patterns: 사용자 행동 패턴
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from agent_teams.config import STATE_DIR

logger = logging.getLogger(__name__)

MEMORY_FILE = STATE_DIR / "secretary_memory.json"


def _load() -> dict:
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "version": "1.0",
        "last_updated": "",
        "facts": [],          # 사용자에 대한 사실 {"content": "...", "category": "...", "created": "..."}
        "conversations": [],   # 최근 대화 요약 {"date": "...", "summary": "...", "topics": [...]}
        "pending": [],         # 팔로업 필요 {"item": "...", "context": "...", "created": "...", "due": "..."}
        "patterns": {},        # 행동 패턴 {"work_hours": "...", "interests": [...], ...}
        "projects": {},        # 진행중 프로젝트 {"name": {"status": "...", "last_update": "..."}}
    }


def _save(data: dict):
    data["last_updated"] = datetime.now().isoformat()
    STATE_DIR.mkdir(exist_ok=True)
    tmp = MEMORY_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(MEMORY_FILE)


def add_fact(content: str, category: str = "general"):
    """사용자에 대한 새 사실 추가."""
    mem = _load()
    # 중복 방지
    if any(f["content"] == content for f in mem["facts"]):
        return
    mem["facts"].append({
        "content": content,
        "category": category,
        "created": datetime.now().isoformat(),
    })
    mem["facts"] = mem["facts"][-50:]  # 최대 50개
    _save(mem)


def add_conversation_summary(summary: str, topics: list[str]):
    """대화 요약 저장."""
    mem = _load()
    mem["conversations"].append({
        "date": datetime.now().isoformat(),
        "summary": summary,
        "topics": topics,
    })
    mem["conversations"] = mem["conversations"][-30:]  # 최근 30개
    _save(mem)


def add_pending(item: str, context: str = "", due: str = ""):
    """팔로업 필요 항목 추가."""
    mem = _load()
    mem["pending"].append({
        "item": item,
        "context": context,
        "created": datetime.now().isoformat(),
        "due": due,
    })
    _save(mem)


def resolve_pending(index: int):
    """팔로업 항목 완료 처리."""
    mem = _load()
    if 0 <= index < len(mem["pending"]):
        mem["pending"].pop(index)
        _save(mem)


def update_project(name: str, status: str):
    """프로젝트 상태 업데이트."""
    mem = _load()
    mem["projects"][name] = {
        "status": status,
        "last_update": datetime.now().isoformat(),
    }
    _save(mem)


def update_pattern(key: str, value):
    """행동 패턴 업데이트."""
    mem = _load()
    mem["patterns"][key] = value
    _save(mem)


def get_full_context() -> str:
    """비서의 대화 생성에 필요한 전체 컨텍스트."""
    mem = _load()
    lines = []

    if mem["facts"]:
        lines.append("[사용자에 대해 아는 것]")
        for f in mem["facts"][-15:]:
            lines.append(f"- {f['content']} ({f['category']})")

    if mem["conversations"]:
        lines.append("\n[최근 대화]")
        for c in mem["conversations"][-5:]:
            lines.append(f"- {c['date'][:10]}: {c['summary']}")

    if mem["pending"]:
        lines.append("\n[팔로업 필요 항목]")
        for i, p in enumerate(mem["pending"]):
            due = f" (기한: {p['due']})" if p.get("due") else ""
            lines.append(f"- [{i}] {p['item']}{due}")

    if mem["projects"]:
        lines.append("\n[진행중 프로젝트]")
        for name, info in mem["projects"].items():
            lines.append(f"- {name}: {info['status']} (last: {info['last_update'][:10]})")

    if mem["patterns"]:
        lines.append("\n[행동 패턴]")
        for k, v in mem["patterns"].items():
            lines.append(f"- {k}: {v}")

    return "\n".join(lines) if lines else "[아직 기억이 없습니다. 대화하면서 학습합니다.]"


def get_pending_items() -> list[dict]:
    """미해결 팔로업 항목."""
    mem = _load()
    return mem.get("pending", [])
