import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "demo" / "sanitize-check.sh"


def _run(**kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT)], cwd=REPO, capture_output=True, text=True, **kwargs)


def test_selftest_passes():
    proc = subprocess.run(["bash", str(SCRIPT), "--selftest"], cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_repo_is_clean():
    proc = _run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "clean" in proc.stdout


def test_sanitizer_catches_planted_leak():
    # Untracked but not ignored, so `git ls-files --others --exclude-standard` still sees it.
    # A per-pid directory keeps concurrent runs from deleting each other's file.
    workdir = REPO / f"tmp-sanitize-{os.getpid()}"
    leak = workdir / "leak.txt"
    try:
        workdir.mkdir()
        leak.write_text("123456789" + "012" + "\n")  # split so this literal never sits whole in tracked source
        proc = _run()
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert leak.name in proc.stdout
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def test_malformed_extra_exits_2(tmp_path):
    bad = tmp_path / "bad-extra"
    bad.write_text("a(b\n")
    proc = _run(env={**os.environ, "SANITIZE_EXTRA": str(bad)})
    assert proc.returncode == 2, proc.stdout + proc.stderr
