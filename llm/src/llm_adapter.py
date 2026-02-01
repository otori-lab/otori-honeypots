import os
import logging
from pathlib import Path
import requests
from fs_engine import fs_snapshot
from utils import log_event

logger = logging.getLogger(__name__)

# Load system prompt from config file
CONFIG_DIR = Path(__file__).parent.parent / "config"
SYSTEM_PROMPT_FILE = CONFIG_DIR / "system_prompt.txt"

def _load_system_prompt() -> str:
    """Load system prompt from config file, fallback to embedded default."""
    if SYSTEM_PROMPT_FILE.exists():
        return SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
    # Fallback if config file doesn't exist
    return """You are a Linux Shell. Behave exactly like a terminal.

RULES:
1. Do NOT explain. Do NOT chat.
2. Output ONLY the standard stdout/stderr.
3. If the command is silent (like 'cd', 'mkdir', 'export'), output nothing.
4. If the command is not found, output 'bash: {cmd}: command not found'.

CONTEXT:
User: {user}
Dir: {cwd}
Files: {files}

EXAMPLES:
Cmd: whoami
Out: {user}

Cmd: cd /tmp
Out:

Cmd: pwd
Out: /tmp

Cmd: notarealcommand
Out: bash: notarealcommand: command not found

CURRENT COMMAND:
Cmd: {cmd}
Out:"""

_SYSTEM_PROMPT_TEMPLATE = _load_system_prompt()

def build_shell_prompt(st, cmd: str) -> str:
    """Build the full prompt for the LLM with context and optional extra context."""
    snap = fs_snapshot(st)

    # Get extra context from environment variable
    extra_context = os.environ.get("EXTRA_CONTEXT", "").strip()

    # Format the base prompt
    prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        user=st.user,
        cwd=st.cwd,
        files=snap,
        cmd=cmd
    )

    # Inject extra context if provided
    if extra_context:
        # Insert extra context after the CONTEXT section
        context_marker = "EXAMPLES:"
        if context_marker in prompt:
            parts = prompt.split(context_marker, 1)
            prompt = f"{parts[0]}EXTRA CONTEXT:\n{extra_context}\n\n{context_marker}{parts[1]}"

    return prompt


def post_validate_output(st, cmd: str, output: str) -> str:
    """Post-process LLM output to ensure consistency with session state."""
    c = cmd.strip()
    if c == "whoami":
        return st.user + "\n"
    if c == "pwd":
        return st.cwd + "\n"
    if c == "hostname":
        return st.hostname + "\n"
    if c == "id":
        return f"uid={st.uid}({st.user}) gid={st.gid}({st.user}) groups={st.gid}({st.user})\n"
    if c == "date":
        return st.now_local_str() + "\n"
    cleaned = output.replace("```", "").strip("\n")
    return cleaned + ("\n" if not cleaned.endswith("\n") else "")


def ollama_shell_reply(st, cmd: str, session: requests.Session, session_id: str, addr, ollama_url: str, ollama_model: str) -> tuple[str, int]:
    """Send command to Ollama LLM and return shell-like response."""
    prompt = build_shell_prompt(st, cmd)
    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 200,
            "top_k": 20,
            "top_p": 0.85,
            "repeat_penalty": 1.05,
        }
    }
    try:
        r = session.post(ollama_url, json=payload, timeout=35)
        r.raise_for_status()
        data = r.json()
        response = (data.get("response") or "").strip()
        if response:
            out = post_validate_output(st, cmd, response)
            log_event(session_id, addr, "llm_success", {"cmd": cmd, "response_preview": out[:200]})
            return out, 0
        log_event(session_id, addr, "llm_empty", {"cmd": cmd})
        return (f"bash: {cmd}: command not found\n", 127)
    except requests.exceptions.Timeout:
        log_event(session_id, addr, "llm_timeout", {"cmd": cmd})
        return (f"bash: {cmd}: LLM unavailable (timeout)\n", 127)
    except requests.exceptions.ConnectionError as e:
        log_event(session_id, addr, "llm_connection_error", {"cmd": cmd, "error": str(e)})
        return (f"bash: {cmd}: LLM unavailable (connection)\n", 127)
    except Exception as e:
        log_event(session_id, addr, "llm_error", {"cmd": cmd, "error": type(e).__name__, "details": str(e)})
        return (f"bash: {cmd}: LLM error ({type(e).__name__})\n", 127)
