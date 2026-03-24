"""
일일 브리핑 — Secretary가 전 팀 보고를 수집하여 브리핑 생성.

Gemini로 각 팀 상태를 수집하고, 종합 브리핑을 생성하여 Telegram 전송.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from agent_teams.config import STATE_DIR, METRICS_FILE
from agent_teams.llm import run_gemini_sync

logger = logging.getLogger(__name__)

BRIEFING_FILE = STATE_DIR / "daily_briefing.json"


def _collect_system_status() -> str:
    """시스템 상태 수집."""
    lines = []
    try:
        df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        lines.append(f"[디스크] {df.stdout.strip().split(chr(10))[-1]}")
    except Exception:
        lines.append("[디스크] 확인 실패")

    try:
        uptime = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
        lines.append(f"[업타임] {uptime.stdout.strip()}")
    except Exception:
        pass

    # 서비스 상태
    for svc in ["research-bot", "mock-interview"]:
        try:
            r = subprocess.run(
                ["systemctl", "--user", "is-active", svc],
                capture_output=True, text=True,
            )
            status = r.stdout.strip()
            lines.append(f"[서비스:{svc}] {status}")
        except Exception:
            pass

    return "\n".join(lines)


def _collect_quant_status() -> str:
    """퀀트 팀 최근 활동."""
    if not METRICS_FILE.exists():
        return "최근 autopilot 실행 없음."
    try:
        with open(METRICS_FILE) as f:
            entries = [json.loads(l) for l in f if l.strip()]
        if not entries:
            return "메트릭 데이터 없음."
        recent = entries[-5:]
        lines = []
        for e in recent:
            lines.append(f"  {e.get('run_id','?')} T{e.get('turn',0)} {e.get('role','')} {e.get('decision','-')}")
        return "최근 실행:\n" + "\n".join(lines)
    except Exception:
        return "메트릭 읽기 실패."


def _collect_startup_status() -> str:
    """스타트업 팀 상태 (배포된 서비스 체크)."""
    lines = []
    # interview-maestro 체크
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "3", "http://localhost:8000/health"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and "ok" in r.stdout:
            lines.append("interview-maestro: 운영 중")
        else:
            lines.append("interview-maestro: 다운")
    except Exception:
        lines.append("interview-maestro: 확인 실패")

    return "\n".join(lines) if lines else "배포된 서비스 없음."


def generate_briefing() -> str:
    """전 팀 보고를 수집하고 Gemini로 브리핑 생성."""
    system_status = _collect_system_status()
    quant_status = _collect_quant_status()
    startup_status = _collect_startup_status()

    now = datetime.now()
    prompt = (
        f"당신은 개인 비서입니다. 아래 정보를 바탕으로 오늘의 아침 브리핑을 작성하세요.\n"
        f"날짜: {now.strftime('%Y년 %m월 %d일 %A')}\n\n"
        f"[시스템 상태]\n{system_status}\n\n"
        f"[퀀트 연구팀]\n{quant_status}\n\n"
        f"[스타트업 팀]\n{startup_status}\n\n"
        f"형식:\n"
        f"1. 한줄 요약\n"
        f"2. 각 팀 상태 (2줄 이내)\n"
        f"3. 오늘 주의할 점 또는 의사결정 필요 사항\n\n"
        f"간결하게 작성. 이모지 사용 OK. 한국어."
    )

    try:
        briefing = run_gemini_sync(prompt, timeout=60)
    except Exception as e:
        briefing = f"브리핑 생성 실패: {e}\n\n원본 데이터:\n{system_status}\n{quant_status}\n{startup_status}"

    # 저장
    data = {
        "date": now.isoformat(),
        "briefing": briefing,
        "raw": {
            "system": system_status,
            "quant": quant_status,
            "startup": startup_status,
        },
    }
    try:
        with open(BRIEFING_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return briefing


def get_latest_briefing() -> str:
    """최근 브리핑 조회."""
    if not BRIEFING_FILE.exists():
        return "아직 브리핑이 없습니다. /briefing gen 으로 생성하세요."
    try:
        with open(BRIEFING_FILE) as f:
            data = json.load(f)
        return f"[{data['date'][:10]}]\n\n{data['briefing']}"
    except Exception:
        return "브리핑 읽기 실패."
