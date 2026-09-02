import subprocess


def test_selftest_passes():
    proc = subprocess.run(["bash", "demo/sanitize-check.sh", "--selftest"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_repo_is_clean():
    proc = subprocess.run(["bash", "demo/sanitize-check.sh"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "clean" in proc.stdout
