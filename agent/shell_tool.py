"""Strands Shell as a single agent tool. Only runbooks/public is mounted."""

from pathlib import Path

import strands_shell
from strands import tool

RUNBOOKS_PUBLIC = Path(__file__).resolve().parent.parent / "runbooks" / "public"

_shell: strands_shell.Shell | None = None


def make_shell() -> strands_shell.Shell:
    return strands_shell.Shell(
        binds=[strands_shell.Bind(str(RUNBOOKS_PUBLIC), "/runbooks", mode="copy")],
        allowed_urls=[],
        timeout=10.0,
    )


@tool
def run_shell(cmd: str) -> dict:
    """Ejecuta un comando en el shell sandbox de runbooks (cat, grep, ls, jq).

    Solo el directorio /runbooks está montado. No hay acceso a red.
    Devuelve exit_code, stdout y stderr.
    """
    global _shell
    if _shell is None:
        _shell = make_shell()
    result = _shell.run(cmd)
    # VERIFY (2026-09-01, strands_shell 0.3.3): strands_shell.Output has no
    # `exit_code` attribute — the installed native Output exposes `status`
    # (int), `stdout`, `stderr`. We keep our own dict's key as `exit_code`
    # per this tool's public interface.
    # ponytail: 4000 chars is enough for any runbook; raise if a runbook ever grows past it
    return {
        "exit_code": result.status,
        "stdout": result.stdout[:4000],
        "stderr": result.stderr[:1000],
    }
