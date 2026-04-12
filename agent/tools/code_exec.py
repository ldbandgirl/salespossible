"""
Python code execution tool — sandboxed exec for data analysis & automation.

Safety: runs in a restricted namespace with no filesystem/network imports.
For production, use a proper sandbox (Docker, Daytona, Modal — Hermes-style).
"""

from __future__ import annotations

import asyncio
import io
import logging
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

logger = logging.getLogger(__name__)

# Blocked modules for safety
_BLOCKED = frozenset(["os", "subprocess", "sys", "shutil", "socket", "importlib"])

CODE_EXEC_SCHEMA: dict[str, Any] = {
    "name": "execute_python",
    "description": (
        "Execute Python code for data analysis, calculations, or generating reports. "
        "Useful for processing CSV data, computing sales metrics, or transforming data. "
        "Returns stdout output and any errors."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Use print() to output results.",
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds (default 10, max 30)",
                "default": 10,
            },
        },
        "required": ["code"],
    },
}


async def execute_python(inputs: dict[str, Any]) -> str:
    """Execute Python code in a restricted environment."""
    code = inputs["code"]
    timeout = min(int(inputs.get("timeout", 10)), 30)

    # Run in executor to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _run_code, code),
            timeout=float(timeout),
        )
        return result
    except asyncio.TimeoutError:
        return f"Code execution timed out after {timeout}s"


def _run_code(code: str) -> str:
    """Run code in a restricted namespace (sync, runs in thread pool)."""
    # Block dangerous imports
    for blocked in _BLOCKED:
        if f"import {blocked}" in code or f"__import__('{blocked}')" in code:
            return f"Security: import of '{blocked}' is not allowed."

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    namespace: dict[str, Any] = {
        "__builtins__": {
            k: v for k, v in __builtins__.items()  # type: ignore
            if k not in ("open", "exec", "eval", "compile", "__import__")
        }
        if isinstance(__builtins__, dict)
        else {},
        "json": __import__("json"),
        "math": __import__("math"),
        "datetime": __import__("datetime"),
        "re": __import__("re"),
        "collections": __import__("collections"),
        "statistics": __import__("statistics"),
    }

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code, namespace)  # noqa: S102

        output = stdout_buf.getvalue()
        errors = stderr_buf.getvalue()

        result = output if output else "(no output)"
        if errors:
            result += f"\nSTDERR:\n{errors}"
        return result[:4000]

    except Exception:
        tb = traceback.format_exc()
        return f"Error:\n{tb[:2000]}"
