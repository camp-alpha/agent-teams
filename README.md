# Agent Teams

멀티 에이전트 팀 오케스트레이션. Telegram 봇으로 팀 에이전트와 대화.

## 팀 구성

| 팀 | 명령어 | 에이전트 | 역할 |
|----|--------|----------|------|
| Secretary | `@secretary` | 비서 | 일일 브리핑, 일정, 제2의 지능 |
| Startup | `@startup` | CEO, Market, Dev | 수익 창출 서비스 기획/개발 |
| Quant | `@quant` | Researcher, Data | 암호화폐 퀀트 전략 연구 |
| Infra | `@infra` | SRE, Architect | 시스템 관리, 구조 개선 |

## 사용법

```
/q @secretary 오늘 할 일 정리해줘
/q @startup 새 아이디어 평가해줘
/q @startup.dev 이 기능 구현해줘
/q @quant BTC 변동성 전략 검토
/q @infra 서비스 상태 체크
/briefing gen               # 아침 브리핑 생성
일반 메시지                  # Secretary가 응답
```

## 실행

```bash
cp .env.example .env
# .env에 TELEGRAM_BOT_TOKEN, GEMINI_API_KEY 설정

# 로컬
./run.sh

# Docker
docker build -t agent-teams .
docker run -d --env-file .env agent-teams
```

## research-control과의 관계

이 프로젝트는 [research-control](https://github.com/camp-alpha/research-control)에서 분리.

| | research-control | agent-teams |
|---|---|---|
| 목적 | 퀀트 연구 오케스트레이션 | 개인 비서 + 스타트업 + 인프라 |
| 실행 환경 | 로컬 (데이터 접근 필요) | 클라우드 OK |
| 통신 | Telegram (같은 그룹 채팅 가능) | Telegram (별도 봇) |
