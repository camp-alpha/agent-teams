"""LLM 호출 — Gemini/Claude 통합 인터페이스."""

import asyncio
import logging
import os
import subprocess

from agent_teams.config import GEMINI_BIN, CLAUDE_BIN

logger = logging.getLogger(__name__)


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
