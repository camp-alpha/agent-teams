"""
팀 라우터 — @팀.에이전트 형식의 메시지를 적절한 에이전트로 라우팅.

라우팅 규칙:
  @secretary           → Secretary 팀 기본 에이전트
  @startup             → Startup 팀 CEO (기본)
  @startup.dev         → Startup 팀 Dev 에이전트
  @quant               → Quant 팀 Researcher (기본)
  @infra.sre           → Infra 팀 SRE
  @teams               → 팀 목록 표시
  @1, @2, @system      → 기존 세션 라우팅 (하위 호환)
"""

import logging
from dataclasses import dataclass

from agent_teams.teams.registry import TEAMS, get_agent, get_agent_prompt, list_teams

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """라우팅 결과."""
    route_type: str  # "team" | "session" | "gemini" | "list"
    team_id: str = ""
    agent_id: str = ""
    persona: str = ""
    remaining_args: list[str] = None

    def __post_init__(self):
        if self.remaining_args is None:
            self.remaining_args = []


def resolve_team_route(args: list[str]) -> RouteResult:
    """@지정자를 파싱하여 라우팅 결과 반환.

    Returns:
        RouteResult with route_type:
          - "team": 팀 에이전트로 라우팅 (persona 포함)
          - "session": 기존 Claude 세션 라우팅 (@system, @1 등)
          - "gemini": Gemini 라우팅
          - "list": 팀 목록 요청
    """
    if not args:
        return RouteResult(route_type="session")

    first = args[0]
    if not first.startswith("@"):
        return RouteResult(route_type="session", remaining_args=args)

    target = first[1:].lower()
    remaining = args[1:]

    # @gemini → Gemini 라우팅
    if target == "gemini":
        return RouteResult(route_type="gemini", remaining_args=remaining)

    # @teams → 팀 목록
    if target == "teams":
        return RouteResult(route_type="list")

    # @팀.에이전트 형식 파싱
    if "." in target:
        team_id, agent_id = target.split(".", 1)
    else:
        team_id = target
        agent_id = None

    # 팀 레지스트리에서 찾기
    if team_id in TEAMS:
        agent = get_agent(team_id, agent_id)
        if agent:
            persona = get_agent_prompt(team_id, agent_id)
            return RouteResult(
                route_type="team",
                team_id=team_id,
                agent_id=agent_id or TEAMS[team_id].default_agent,
                persona=persona,
                remaining_args=remaining,
            )
        else:
            # 팀은 있지만 에이전트가 없음
            logger.warning(f"Agent '{agent_id}' not found in team '{team_id}'")
            return RouteResult(route_type="session", remaining_args=args)

    # 팀이 아닌 경우 기존 세션 라우팅으로 폴백 (@system, @1, @uuid...)
    return RouteResult(route_type="session", remaining_args=args)


def build_team_prompt(route: RouteResult, message: str) -> str:
    """팀 에이전트에게 보낼 프롬프트 구성."""
    return (
        f"{route.persona}\n\n"
        f"---\n"
        f"[{route.team_id}.{route.agent_id}에게 온 메시지]\n"
        f"{message}"
    )
