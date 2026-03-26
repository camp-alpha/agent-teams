"""LLM 호출 — Gemini/Claude 하이브리드 라우팅.

단순 작업 → Gemini (무료/빠름)
복잡한 추론/코딩 → Claude (고품질)
"""

import asyncio
import logging
import os
import re
import subprocess

from agent_teams.config import GEMINI_BIN, CLAUDE_BIN

logger = logging.getLogger(__name__)

# ── 작업 분류 ──

CLAUDE_PATTERNS = [
    r"(작성|생성|만들|구현|코딩|코드|빌드|build)",
    r"(분석|연구|탐구|가설|검증|전략|설계|아키텍처)",
    r"(수정|변경|리팩토링|fix|edit|update|debug)",
    r"(계획|plan|design|시나리오|로드맵)",
    r"(비교|평가|판단|추론|논리|수학)",
    r"(git|commit|push|deploy|배포)",
    r"(왜|어떻게|원인|근본|분석해)",
    r"(장단점|트레이드오프|trade.?off)",
]

GEMINI_PATTERNS = [
    r"(읽어|보여|확인|체크|check|상태)",
    r"(요약|summarize|정리|리스트|목록)",
    r"(몇|얼마|뭐|무엇|어떤|언제|어디)",
    r"(번역|translate|설명해$)",
    r"(찾아|검색|search|grep|find)",
    r"(일정|캘린더|calendar|스케줄)",
    r"(알림|리마인드|remind)",
]


def classify_task(message: str) -> str:
    """메시지를 분석하여 'claude' 또는 'gemini' 반환."""
    msg = message.lower().strip()

    claude_score = sum(1 for p in CLAUDE_PATTERNS if re.search(p, msg))
    gemini_score = sum(1 for p in GEMINI_PATTERNS if re.search(p, msg))

    if claude_score > gemini_score:
        return "claude"
    if gemini_score > claude_score:
        return "gemini"
    # 동점이면 길이 기반: 짧으면 gemini, 길면 claude
    if len(msg) < 80:
        return "gemini"
    return "claude"


# ── Gemini ──

def _gemini_env() -> dict:
    env = os.environ.copy()
    return env


def run_gemini_sync(message: str, timeout: int = 120, cwd: str = ".") -> str:
    cmd = [GEMINI_BIN, "--yolo", "-p", message, "-o", "text"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=cwd, env=_gemini_env(),
        )
        output = result.stdout.strip()
        if result.returncode != 0 and not output:
            return f"[Gemini Error] {result.stderr.strip()[:500]}"
        return output if output else "[No output]"
    except subprocess.TimeoutExpired:
        return f"[Gemini Timeout] {timeout}s"
    except Exception as e:
        return f"[Gemini Error] {str(e)}"


async def run_gemini_async(message: str, timeout: int = 120, cwd: str = ".") -> str:
    cmd = [GEMINI_BIN, "--yolo", "-p", message, "-o", "text"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=cwd, env=_gemini_env(),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode().strip()
        if proc.returncode != 0 and not output:
            return f"[Gemini Error] {stderr.decode().strip()[:500]}"
        return output if output else "[No output]"
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return f"[Gemini Timeout] {timeout}s"
    except Exception as e:
        return f"[Gemini Error] {str(e)}"


# ── Claude (세션 기반) ──

def run_claude_sync(session_id: str, message: str, timeout: int = 600,
                    cwd: str = ".", fork: bool = False) -> tuple[str, str]:
    out_fmt = "json" if fork else "text"
    cmd = [
        CLAUDE_BIN, "--resume", session_id, "--print",
        "--dangerously-skip-permissions", "--output-format", out_fmt, message,
    ]
    if fork:
        cmd.insert(cmd.index("--print"), "--fork-session")
    try:
        import json
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        raw = result.stdout.strip()
        if result.returncode != 0 and not raw:
            return f"[Error] {result.stderr.strip()[:500]}", session_id
        if fork:
            try:
                data = json.loads(raw)
                return data.get("result", raw[:4000]), data.get("session_id", session_id)
            except json.JSONDecodeError:
                return raw, session_id
        return raw if raw else "[No output]", session_id
    except subprocess.TimeoutExpired:
        return f"[Timeout] {timeout}s", session_id
    except Exception as e:
        return f"[Error] {str(e)}", session_id


# ── Claude (세션 없이, 단발 호출) ──

def run_claude_oneshot(message: str, timeout: int = 300, cwd: str = ".") -> str:
    """세션 없이 Claude 단발 호출."""
    cmd = [
        CLAUDE_BIN, "--print",
        "--dangerously-skip-permissions", "--output-format", "text",
        "-p", message,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        output = result.stdout.strip()
        if result.returncode != 0 and not output:
            return f"[Claude Error] {result.stderr.strip()[:500]}"
        return output if output else "[No output]"
    except subprocess.TimeoutExpired:
        return f"[Claude Timeout] {timeout}s"
    except Exception as e:
        return f"[Claude Error] {str(e)}"


async def run_claude_oneshot_async(message: str, timeout: int = 300, cwd: str = ".") -> str:
    """세션 없이 Claude 비동기 단발 호출."""
    cmd = [
        CLAUDE_BIN, "--print",
        "--dangerously-skip-permissions", "--output-format", "text",
        "-p", message,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode().strip()
        if proc.returncode != 0 and not output:
            return f"[Claude Error] {stderr.decode().strip()[:500]}"
        return output if output else "[No output]"
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return f"[Claude Timeout] {timeout}s"
    except Exception as e:
        return f"[Claude Error] {str(e)}"


# ── 하이브리드 라우터 ──

async def run_hybrid_async(message: str, system_prompt: str = "",
                           timeout: int = 180, cwd: str = ".") -> tuple[str, str]:
    """메시지를 자동 분류하여 Gemini 또는 Claude로 라우팅.

    Returns: (output, engine_used)
    """
    engine = classify_task(message)
    full_prompt = f"{system_prompt}\n\n{message}" if system_prompt else message

    if engine == "claude":
        output = await run_claude_oneshot_async(full_prompt, timeout=timeout, cwd=cwd)
        return output, "claude"
    else:
        output = await run_gemini_async(full_prompt, timeout=min(timeout, 120), cwd=cwd)
        return output, "gemini"
