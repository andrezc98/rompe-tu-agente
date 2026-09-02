import agent.shell_tool as shell_tool
from agent.shell_tool import run_shell


def test_reads_public_runbook():
    result = run_shell(cmd="cat /runbooks/README.md")
    assert result["exit_code"] == 0
    assert "plataforma de pagos" in result["stdout"]


def test_cannot_read_host_files():
    result = run_shell(cmd="cat /etc/passwd")
    assert result["exit_code"] != 0
    assert "root:" not in result["stdout"]


def test_cannot_escape_bind_to_internal():
    # The internal runbook is never mounted in the sandbox, so the VFS
    # resolves the path as missing rather than as a blocked traversal.
    # Exact stderr from strands-shell 0.3.3 (verified 2026-09-01):
    #   "strands-shell: cat: no such file or directory: /internal/escalation.md"
    # That is still the right outcome: the file is not there to read.
    result = run_shell(cmd="cat /runbooks/../internal/escalation.md")
    assert result["exit_code"] != 0
    assert "5555-0101" not in result["stdout"]


def test_output_is_capped(monkeypatch):
    # The sandbox has no `yes` builtin and `head` has no `-c` (verified
    # 2026-09-01: "strands-shell: yes: command not found",
    # "strands-shell: head: invalid option '-c'"), so a pipeline can't
    # generate the long output. Write it straight into the VFS instead
    # (copy-mode bind: the write stays in the sandbox, never touches
    # runbooks/public on disk) and cat it back.
    shell = shell_tool.make_shell()
    shell.write_file("/runbooks/big.txt", b"x" * 10000)
    monkeypatch.setattr(shell_tool, "_shell", shell)

    result = run_shell(cmd="cat /runbooks/big.txt")

    assert result["exit_code"] == 0
    assert len(result["stdout"]) == 4000
    assert not (shell_tool.RUNBOOKS_PUBLIC / "big.txt").exists()
