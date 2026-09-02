"""Strands Shell as a single agent tool. Only runbooks/public is mounted."""

from pathlib import Path

import strands_shell
from strands import tool

RUNBOOKS_PUBLIC = Path(__file__).resolve().parent.parent / "runbooks" / "public"


def make_shell() -> strands_shell.Shell:
    return strands_shell.Shell(
        binds=[strands_shell.Bind(str(RUNBOOKS_PUBLIC), "/runbooks", mode="copy")],
        allowed_urls=[],
        timeout=10.0,
    )


@tool
def run_shell(cmd: str) -> dict:
    """Ejecuta un comando en el shell sandbox de runbooks (cat, grep, ls).

    Solo el directorio /runbooks está montado. No hay acceso a red. Cada comando corre en
    un sandbox nuevo: nada persiste entre llamadas. stdout se trunca a 4000 caracteres y
    stderr a 1000. Devuelve exit_code, stdout y stderr.
    """
    # ponytail: a fresh Shell per call (sub-millisecond startup) means no state bleeds between
    # agent episodes or parallel red-team workers; add a per-agent shell only if a scene needs cwd to persist
    result = make_shell().run(cmd)
    return {
        "exit_code": result.status,  # strands-shell 0.3.3 names it status
        "stdout": result.stdout[:4000],
        "stderr": result.stderr[:1000],
    }
