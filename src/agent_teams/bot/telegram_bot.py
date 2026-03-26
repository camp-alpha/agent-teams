"""
Agent Teams Telegram Bot

팀 에이전트와 대화하기 위한 독립 봇.
research-control 봇과 별도 토큰으로 운영.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from agent_teams.config import TELEGRAM_BOT_TOKEN, STATE_DIR, OWNER_ID
from agent_teams.llm import run_gemini_async, run_claude_sync, run_claude_oneshot_async
from agent_teams.teams.registry import list_teams, get_agent, TEAMS
from agent_teams.teams.router import resolve_team_route, build_team_prompt
from agent_teams.teams.daily_briefing import generate_briefing, get_latest_briefing
from agent_teams.secretary.engine import generate_proactive_message, process_user_response
from agent_teams.secretary.scheduler import setup_scheduler
from agent_teams.notion_logger import log_conversation as notion_log

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

STATE_FILE = STATE_DIR / "bot_state.json"
LOG_FILE = STATE_DIR / "conversations.jsonl"
ALLOWED_USER_IDS: set[int] = set()


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"allowed_users": [], "claude_session": ""}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def log_conversation(user: str, agent: str, message: str, response: str,
                     team: str = "", channel: str = "telegram"):
    # 로컬 jsonl
    entry = {
        "ts": datetime.now().isoformat(),
        "user": user,
        "agent": agent,
        "q": message[:200],
        "a": response[:500],
    }
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # Notion DB 기록 (비동기적으로, 실패해도 무시)
    try:
        # 사용자 → 에이전트
        notion_log(
            from_agent="User", to_agent=agent.split(".")[0].capitalize(),
            message=message, team=team, channel=channel,
        )
        # 에이전트 → 사용자
        notion_log(
            from_agent=agent.split(".")[0].capitalize(), to_agent="User",
            message=response, team=team, channel=channel,
        )
    except Exception:
        pass


async def safe_reply(message, text: str, retries: int = 3):
    """Telegram 전송 with retry (네트워크 타임아웃 대응)."""
    for attempt in range(retries):
        try:
            await message.reply_text(text)
            return
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"Reply failed (attempt {attempt+1}): {e}")
                await asyncio.sleep(2)
            else:
                logger.error(f"Reply failed after {retries} attempts: {e}")


def authorized(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return update.effective_user.id in ALLOWED_USER_IDS


# ── 핸들러 ──

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("등록 권한이 없습니다.")
        return
    state = load_state()
    allowed = state.get("allowed_users", [])
    if user.id not in allowed:
        allowed.append(user.id)
        state["allowed_users"] = allowed
        save_state(state)
        ALLOWED_USER_IDS.add(user.id)
    await update.message.reply_text(
        f"👥 Agent Teams Bot\n등록: {user.first_name}\n/help 로 명령어 확인"
    )


HELP_TEXT = (
    "👥 Agent Teams Bot\n\n"
    "💬 팀 에이전트 (Gemini 기본)\n"
    "/q @startup <메시지> — CEO\n"
    "/q @startup.dev <메시지> — 개발자\n"
    "/q @quant <메시지> — 퀀트 연구원\n"
    "/q @infra <메시지> — SRE (Claude)\n"
    "/q <메시지> — Secretary 기본\n\n"
    "🧠 Claude 강제 (/c)\n"
    "/c <메시지> — Secretary/Claude\n"
    "/c @startup <메시지> — CEO/Claude\n"
    "/c @팀 <메시지> — 해당 팀/Claude\n\n"
    "📋 관리\n"
    "/teams — 팀 목록\n"
    "/briefing — 아침 브리핑\n"
    "/log — 최근 대화\n"
)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def cmd_teams(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(list_teams())


async def cmd_briefing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if ctx.args and ctx.args[0] == "gen":
        await update.message.reply_text("📋 브리핑 생성 중...")
        loop = asyncio.get_event_loop()
        briefing = await loop.run_in_executor(None, generate_briefing)
        await update.message.reply_text(briefing[:4000])
    else:
        await update.message.reply_text(get_latest_briefing()[:4000])


async def cmd_q(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """팀 에이전트에게 질문."""
    if not authorized(update):
        logger.info(f"cmd_q unauthorized: {update.effective_user.id}")
        return
    logger.info(f"cmd_q from {update.effective_user.first_name}: {' '.join(ctx.args or [])[:50]}")
    if not ctx.args:
        await update.message.reply_text("사용법: /q [@팀] <메시지>")
        return

    user = update.effective_user.first_name
    raw_args = list(ctx.args)

    # 팀 라우팅
    route = resolve_team_route(raw_args)

    if route.route_type == "list":
        await update.message.reply_text(list_teams())
        return

    if route.route_type == "gemini":
        if not route.remaining_args:
            await update.message.reply_text("사용법: /q @gemini <질문>")
            return
        raw_msg = " ".join(route.remaining_args)
        await update.message.reply_text(f"⚡ [Gemini] 처리 중...")
        output = await run_gemini_async(raw_msg, timeout=120)
        await safe_reply(update.message, f"⚡ [Gemini] → {user}\n\n{output[:4000]}")
        log_conversation(user, "gemini", raw_msg, output)
        return

    if route.route_type == "team":
        if not route.remaining_args:
            await update.message.reply_text(f"사용법: /q @{route.team_id} <메시지>")
            return
        raw_msg = " ".join(route.remaining_args)
        agent_label = f"{route.team_id}.{route.agent_id}"
        await update.message.reply_text(f"🤖 [{agent_label}] 처리 중...")

        try:
            from agent_teams.config import CLAUDE_SESSIONS
            if route.team_id in CLAUDE_SESSIONS:
                # infra → Claude SRE 세션 (research-control cwd)
                session_id = CLAUDE_SESSIONS[route.team_id]
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(
                    None, lambda: run_claude_sync(session_id, raw_msg, timeout=120, cwd="/home/younjihoon/research-control")[0]
                )
            elif route.team_id == "secretary":
                # secretary → 대화 엔진 (메모리 포함)
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(None, process_user_response, raw_msg)
            else:
                # 그 외 팀 → Gemini
                output = await run_gemini_async(
                    f"{route.persona}\n\n---\n{raw_msg}", timeout=180
                )
        except Exception as e:
            output = f"[에러] {str(e)[:300]}"
            logger.error(f"Team agent error ({agent_label}): {e}", exc_info=True)

        header = f"🤖 [{agent_label}] → {user}\n\n"
        content = header + output
        if len(content) > 4000:
            for i in range(0, len(output), 4000):
                prefix = header if i == 0 else ""
                await update.message.reply_text(prefix + output[i:i+4000])
        else:
            await safe_reply(update.message, content)
        log_conversation(user, agent_label, raw_msg, output, team=route.team_id)
        return

    # 기본: Secretary 대화 엔진 (메모리 포함)
    raw_msg = " ".join(raw_args)
    await update.message.reply_text(f"🤖 [secretary] 처리 중...")
    try:
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, process_user_response, raw_msg)
    except Exception as e:
        output = f"[에러] {str(e)[:300]}"
    await safe_reply(update.message, f"🤖 [secretary] → {user}\n\n{output[:4000]}")
    log_conversation(user, "secretary", raw_msg, output, team="secretary")


async def cmd_c(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Claude 강제 호출. /q와 동일하지만 항상 Claude 사용."""
    if not authorized(update):
        return
    if not ctx.args:
        await update.message.reply_text("사용법: /c [@팀] <메시지>")
        return

    user = update.effective_user.first_name
    raw_args = list(ctx.args)
    logger.info(f"cmd_c (Claude) from {user}: {' '.join(raw_args)[:50]}")

    route = resolve_team_route(raw_args)

    if route.route_type == "team":
        if not route.remaining_args:
            await update.message.reply_text(f"사용법: /c @{route.team_id} <메시지>")
            return
        raw_msg = " ".join(route.remaining_args)
        agent_label = f"{route.team_id}.{route.agent_id}/claude"
        await update.message.reply_text(f"🧠 [{agent_label}] 처리 중...")

        try:
            from agent_teams.config import CLAUDE_SESSIONS
            if route.team_id in CLAUDE_SESSIONS:
                session_id = CLAUDE_SESSIONS[route.team_id]
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(
                    None, lambda: run_claude_sync(session_id, raw_msg, timeout=300, cwd="/home/younjihoon/research-control")[0]
                )
            else:
                prompt = f"{route.persona}\n\n---\n{raw_msg}"
                output = await run_claude_oneshot_async(prompt, timeout=300)
        except Exception as e:
            output = f"[에러] {str(e)[:300]}"
            logger.error(f"cmd_c error ({agent_label}): {e}", exc_info=True)

        await safe_reply(update.message, f"🧠 [{agent_label}] → {user}\n\n{output[:4000]}")
        log_conversation(user, agent_label, raw_msg, output, team=route.team_id)
        return

    # 팀 미지정 → Secretary/Claude
    raw_msg = " ".join(route.remaining_args or raw_args)
    await update.message.reply_text("🧠 [Claude] 처리 중...")
    try:
        from agent_teams.secretary.engine import SECRETARY_SYSTEM
        from agent_teams.secretary.memory import get_full_context
        memory_context = get_full_context()
        now = datetime.now()
        prompt = (
            f"{SECRETARY_SYSTEM}\n\n"
            f"현재 시각: {now.strftime('%Y년 %m월 %d일 %A %H:%M')}\n\n"
            f"[기억]\n{memory_context}\n\n"
            f"[지훈의 메시지]\n{raw_msg}\n\n"
            f"위에 대해 응답하세요."
        )
        output = await run_claude_oneshot_async(prompt, timeout=300)
    except Exception as e:
        output = f"[에러] {str(e)[:300]}"

    await safe_reply(update.message, f"🧠 [secretary/claude] → {user}\n\n{output[:4000]}")
    log_conversation(user, "secretary/claude", raw_msg, output, team="secretary")


async def cmd_log(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not LOG_FILE.exists():
        await update.message.reply_text("로그 없음.")
        return
    with open(LOG_FILE) as f:
        lines = f.readlines()
    recent = lines[-10:]
    output = "📜 최근 대화\n\n"
    for line in recent:
        try:
            e = json.loads(line)
            ts = e["ts"][11:16]
            output += f"{ts} [{e.get('agent','?')}] {e.get('q','')[:50]}\n"
            output += f"  → {e.get('a','')[:80]}\n\n"
        except Exception:
            continue
    await update.message.reply_text(output[:4000])


# 일반 메시지 → Secretary 대화 엔진 (기억 기반)
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        logger.info(f"Unauthorized: {update.effective_user.id}")
        return
    text = update.message.text
    if not text:
        return
    user = update.effective_user.first_name
    logger.info(f"Message from {user}: {text[:50]}")
    try:
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, process_user_response, text)
        await safe_reply(update.message, output[:4000])
        log_conversation(user, "secretary", text, output, team="secretary")
    except Exception as e:
        logger.error(f"handle_message error: {e}", exc_info=True)
        await update.message.reply_text(f"[오류] {str(e)[:200]}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Unhandled error: {context.error}", exc_info=context.error)
    if update and hasattr(update, "effective_message") and update.effective_message:
        try:
            await update.effective_message.reply_text(f"[시스템 오류] {str(context.error)[:200]}")
        except Exception:
            pass


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN 환경변수를 설정하세요.")
        return

    state = load_state()
    for uid in state.get("allowed_users", []):
        ALLOWED_USER_IDS.add(uid)
    logger.info(f"Allowed users: {ALLOWED_USER_IDS}")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("teams", cmd_teams))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("q", cmd_q))
    app.add_handler(CommandHandler("c", cmd_c))
    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    # 스케줄러 등록 (매일 09:00 아침 루틴)
    setup_scheduler(app)

    logger.info("Agent Teams Bot started (scheduler active)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
