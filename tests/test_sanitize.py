import os
import subprocess


def test_selftest_passes():
    proc = subprocess.run(["bash", "demo/sanitize-check.sh", "--selftest"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_repo_is_clean():
    proc = subprocess.run(["bash", "demo/sanitize-check.sh"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "clean" in proc.stdout


def test_sanitizer_catches_planted_leak():
    leak = "tmp-leak.txt"
    try:
        with open(leak, "w") as f:
            f.write("123456789" + "012" + "\n")  # split so this literal never sits whole in tracked source
        proc = subprocess.run(["bash", "demo/sanitize-check.sh"], capture_output=True, text=True)
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert leak in proc.stdout
    finally:
        os.remove(leak)


def test_malformed_extra_exits_2(tmp_path):
    bad = tmp_path / "bad-extra"
    bad.write_text("a(b\n")
    env = {**os.environ, "SANITIZE_EXTRA": str(bad)}
    proc = subprocess.run(["bash", "demo/sanitize-check.sh"], capture_output=True, text=True, env=env)
    assert proc.returncode == 2, proc.stdout + proc.stderr
