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


def test_output_is_capped():
    result = run_shell(cmd="yes x | head -c 100000")
    assert len(result["stdout"]) <= 4000
