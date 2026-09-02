"""Pure test for scripts/gen-art.py: no real Bedrock call, no real image generation.

scripts/gen-art.py keeps the hyphen in its filename (it's invoked as a script, not imported
elsewhere), so it's loaded here via importlib rather than a normal `import`.
"""

import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "gen-art.py"
_spec = importlib.util.spec_from_file_location("gen_art", SCRIPT_PATH)
gen_art = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen_art)

# A minimal, self-built base64 "PNG" (real signature bytes + filler): the test only needs bytes
# that round-trip through write_bytes, never a real decodable image.
TINY_PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"fake-tiny-png-body").decode()


class _FakeBody:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._data


class _FakeRuntime:
    def __init__(self, image_b64: str):
        self.image_b64 = image_b64
        self.requests: list[dict] = []

    def invoke_model(self, *, modelId, body, contentType, accept):
        self.requests.append(json.loads(body))
        return {"body": _FakeBody({"images": [self.image_b64]})}


class _FakeSession:
    def __init__(self, runtime: _FakeRuntime, *args, **kwargs):
        self._runtime = runtime

    def client(self, service_name, **kwargs):
        assert service_name == "bedrock-runtime"
        return self._runtime


def test_main_writes_both_scene_images_under_out(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    runtime = _FakeRuntime(TINY_PNG_B64)
    monkeypatch.setattr(gen_art.boto3, "Session", lambda *a, **kw: _FakeSession(runtime, *a, **kw))
    monkeypatch.setattr(gen_art, "OUT", tmp_path)

    rc = gen_art.main()

    assert rc == 0
    assert set(gen_art.SCENES) == {"escena-timeout", "escena-crescendo"}
    for name in gen_art.SCENES:
        out_file = tmp_path / f"{name}.png"
        assert out_file.exists()
        assert out_file.read_bytes() == base64.b64decode(TINY_PNG_B64)

    assert len(runtime.requests) == len(gen_art.SCENES)
    for request in runtime.requests:
        assert request["taskType"] == "TEXT_IMAGE"
        assert request["textToImageParams"]["text"]
        cfg = request["imageGenerationConfig"]
        assert (cfg["width"], cfg["height"]) == (1280, 720)


def test_main_reports_rai_output_deflection_without_writing_a_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")

    class _BlockedRuntime:
        def invoke_model(self, **kwargs):
            return {"body": _FakeBody({"images": [], "error": "All of the generated images have been blocked by our content filters."})}

    monkeypatch.setattr(gen_art.boto3, "Session", lambda *a, **kw: SimpleNamespace(client=lambda *a2, **kw2: _BlockedRuntime()))
    monkeypatch.setattr(gen_art, "OUT", tmp_path)

    rc = gen_art.main()

    assert rc == 1
    assert list(tmp_path.iterdir()) == []
