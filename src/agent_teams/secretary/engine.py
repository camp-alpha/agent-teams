"""
Secretary 대화 엔진 — 프로액티브 대화 생성 + 기억 업데이트.

핵심 원칙:
  - 비서가 먼저 말을 건다 (브리핑이 아니라 질문)
  - 대화 후 기억을 업데이트한다
  - 기억을 기반으로 다음 대화를 더 잘한다
"""

import json
import logging
from datetime import datetime

from agent_teams.llm import run_gemini_sync
from agent_teams.secretary.memory import (
    get_full_context,
    add_conversation_summary,
    add_fact,
    add_pending,
    resolve_pending,
    update_project,
)

logger = logging.getLogger(__name__)


SECRETARY_SYSTEM = """당신은 지훈의 개인 비서입니다. 이름은 '비서'입니다.

역할:
- 지훈을 챙기는 것이 당신의 존재 이유입니다
- 지훈이 당신을 챙기는 게 아니라, 당신이 지훈을 챙깁니다
- 대화를 통해 지훈에 대해 계속 학습합니다
- 필요한 것을 미리 파악하고 먼저 제안합니다

대화 스타일:
- 간결하고 핵심적. 불필요한 인사말 없이 바로 본론
- 질문으로 대화를 유도. 일방적 보고 금지
- 유용한 정보가 있을 때만 말함. 할 말 없으면 억지로 만들지 않음
- 지훈이 말한 것을 기억하고 나중에 팔로업

금지사항:
- "무엇을 도와드릴까요?" 같은 수동적 표현
- 감정 과잉 표현
- 이미 알고 있는 정보 반복 설명
"""


def generate_proactive_message(external_context: str = "") -> str:
    """비서가 먼저 보낼 메시지 생성.

    Args:
        external_context: 캘린더, 시스템 상태 등 외부 컨텍스트

    Returns:
        비서가 보낼 메시지
    """
    memory_context = get_full_context()
    now = datetime.now()

    prompt = (
        f"{SECRETARY_SYSTEM}\n\n"
        f"현재 시각: {now.strftime('%Y년 %m월 %d일 %A %H:%M')}\n\n"
        f"[기억]\n{memory_context}\n\n"
        f"[외부 정보]\n{external_context if external_context else '없음'}\n\n"
        f"위 정보를 바탕으로, 지금 지훈에게 보낼 메시지를 작성하세요.\n\n"
        f"규칙:\n"
        f"- 가장 중요하거나 시급한 것 1-2개만 언급\n"
        f"- 반드시 질문을 포함해서 대화를 유도\n"
        f"- 팔로업 항목이 있으면 확인 질문\n"
        f"- 새로운 정보가 있으면 공유하고 의견 물어보기\n"
        f"- 할 말이 정말 없으면 '특이사항 없음'이라고만 하기\n"
        f"- 3-5문장 이내\n"
    )

    return run_gemini_sync(prompt, timeout=60)


def process_user_response(user_message: str) -> str:
    """사용자 메시지를 처리하고 응답 + 기억 업데이트.

    1. 기억 컨텍스트 + 메시지를 보고 응답 생성
    2. 대화에서 학습할 것을 추출하여 기억 업데이트
    3. 팔로업 필요한 것이 있으면 pending에 추가

    Returns:
        비서의 응답
    """
    memory_context = get_full_context()
    now = datetime.now()

    # 1단계: 응답 생성
    response_prompt = (
        f"{SECRETARY_SYSTEM}\n\n"
        f"현재 시각: {now.strftime('%Y년 %m월 %d일 %A %H:%M')}\n\n"
        f"[기억]\n{memory_context}\n\n"
        f"[지훈의 메시지]\n{user_message}\n\n"
        f"위에 대해 응답하세요. 필요하면 추가 질문을 하세요."
    )

    response = run_gemini_sync(response_prompt, timeout=60)

    # 2단계: 기억 업데이트 (비동기적으로 처리)
    _update_memory_from_conversation(user_message, response)

    return response


def _update_memory_from_conversation(user_message: str, assistant_response: str):
    """대화에서 기억할 것을 추출하여 저장."""
    extract_prompt = (
        f"아래 대화에서 기억할 만한 정보를 추출해줘.\n\n"
        f"[사용자]: {user_message}\n"
        f"[비서]: {assistant_response}\n\n"
        f"다음 JSON으로 출력:\n"
        f'{{"facts": ["기억할 사실1", ...],\n'
        f' "pending": ["팔로업 필요 항목1", ...],\n'
        f' "projects": {{"프로젝트명": "상태"}},\n'
        f' "summary": "대화 한줄 요약",\n'
        f' "topics": ["토픽1", "토픽2"]}}\n\n'
        f"기억할 것이 없으면 빈 리스트/객체. JSON만 출력."
    )

    try:
        raw = run_gemini_sync(extract_prompt, timeout=30)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
    except (json.JSONDecodeError, Exception):
        # 추출 실패해도 대화는 계속
        add_conversation_summary(user_message[:100], [])
        return

    # 사실 저장
    for fact in data.get("facts", []):
        if fact:
            add_fact(fact)

    # 팔로업 항목
    for item in data.get("pending", []):
        if item:
            add_pending(item, context=user_message[:100])

    # 프로젝트 상태
    for name, status in data.get("projects", {}).items():
        update_project(name, status)

    # 대화 요약
    add_conversation_summary(
        data.get("summary", user_message[:100]),
        data.get("topics", []),
    )
