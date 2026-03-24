"""
Secretary 스케줄러 — 매일 지정 시각에 프로액티브 메시지 전송.

봇의 Application에 job_queue를 사용하여 스케줄링.
"""

import logging
from datetime import time as dt_time

from telegram.ext import Application, ContextTypes

from agent_teams.config import STATE_DIR, OWNER_ID
from agent_teams.secretary.engine import generate_proactive_message
from agent_teams.teams.daily_briefing import generate_briefing

logger = logging.getLogger(__name__)


async def morning_routine(context: ContextTypes.DEFAULT_TYPE):
    """매일 아침 실행되는 루틴."""
    logger.info("Morning routine triggered")

    # 외부 컨텍스트 수집 (브리핑)
    try:
        briefing = generate_briefing()
        external = f"[아침 브리핑]\n{briefing}"
    except Exception as e:
        external = f"[브리핑 생성 실패: {e}]"

    # 비서의 프로액티브 메시지 생성
    try:
        message = generate_proactive_message(external_context=external)
    except Exception as e:
        message = f"좋은 아침. 비서 시스템에 이슈가 있어서 간단히만 — {external[:200]}"

    # Telegram 전송
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=message[:4000],
        )
        logger.info("Morning message sent")
    except Exception as e:
        logger.error(f"Morning message failed: {e}")


def setup_scheduler(app: Application):
    """봇에 스케줄 등록."""
    job_queue = app.job_queue
    if job_queue is None:
        logger.error("job_queue not available. Install python-telegram-bot[job-queue]")
        return

    # 매일 09:00 KST
    job_queue.run_daily(
        morning_routine,
        time=dt_time(hour=9, minute=0, second=0),
        name="morning_routine",
    )
    logger.info("Scheduled: morning_routine at 09:00 daily")
