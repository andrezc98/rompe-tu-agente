"""Generate illustrative scene art with Amazon Nova Canvas on Bedrock. Own generation, no third-party rights.

GATED: costs a few cents per run. Do not run without the sandbox AWS profile exported.

Request/response schema and model id verified 2026-09-02 against the AWS docs (aws-documentation MCP):
- https://docs.aws.amazon.com/nova/latest/userguide/image-gen-req-resp-structure.html
  -- TEXT_IMAGE request body: taskType, textToImageParams.text (required, 1-1024 chars),
  textToImageParams.negativeText (optional), imageGenerationConfig {width, height, cfgScale, seed,
  numberOfImages}.
- https://docs.aws.amazon.com/nova/latest/userguide/image-gen-access.html#image-gen-resolutions
  -- width/height: each side 320-4096px, divisible by 16, aspect ratio between 1:4 and 4:1, total
  pixel count < 4,194,304. 1280x720 (this script) satisfies all four.
- https://docs.aws.amazon.com/nova/latest/userguide/image-gen-code-examples.html
  -- official sample code: response body key is "images" (list of base64 PNG strings), read via
  json.loads(response["body"].read())["images"][0]; a soft-failure (Responsible AI output
  deflection) comes back as a 200 response with a top-level "error" string instead of raising.
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-canvas.html
  -- model id "amazon.nova-canvas-v1:0" is current (legacy lifecycle, EOL 2026-09-30, still fully
  usable today) and available in-region in us-east-1, this repo's default region.
No field names or the model id needed to change from the task brief; the RAI-error check below is
the one addition the docs surfaced (a blocked generation is a 200, not an exception).
"""

import base64
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config

from agent import config

MODEL_ID = os.environ.get("IMAGE_MODEL_ID", "amazon.nova-canvas-v1:0")
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "slides" / "assets"

SCENES = {
    "escena-timeout": "Editorial illustration, muted dark palette, a lone on-call engineer at 2 am lit by a laptop, a chat bubble shows a confident number while a small red timeout icon blinks behind it, no text, minimalist, 16:9",
    "escena-crescendo": "Editorial illustration, muted dark palette, a staircase of seven chat messages rising toward a big red stop button on a server rack, each step slightly more insistent, no text, minimalist, 16:9",
}


def _out_dir() -> Path:
    # Read at call time (not import time) so a test can set GEN_ART_OUT before invoking main().
    return Path(os.environ.get("GEN_ART_OUT", DEFAULT_OUT))


def main() -> int:
    config.require_sandbox()
    session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE") or None, region_name=config.REGION)
    # read_timeout=300: image generation runs longer than the botocore default: AWS's own sample
    # code (image-gen-code-examples.html) sets this on the bedrock-runtime client.
    runtime = session.client("bedrock-runtime", config=Config(read_timeout=300))
    out = _out_dir()
    out.mkdir(parents=True, exist_ok=True)
    for name, prompt in SCENES.items():
        body = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {"text": prompt, "negativeText": "text, letters, watermark, logo"},
            # cfgScale: 1.1-10.0, default 6.5. seed: 0-2147483646, default 12. (Per fix-round review;
            # not independently re-confirmed by me against a specific doc page after several searches
            # -- see the fix report.) 7.0/42 are both within range.
            "imageGenerationConfig": {"numberOfImages": 1, "width": 1280, "height": 720, "cfgScale": 7.0, "seed": 42},
        }
        response = runtime.invoke_model(modelId=MODEL_ID, body=json.dumps(body), contentType="application/json", accept="application/json")
        payload = json.loads(response["body"].read())
        if payload.get("error"):
            print(f"error generating {name}: {payload['error']}", file=sys.stderr)
            return 1
        (out / f"{name}.png").write_bytes(base64.b64decode(payload["images"][0]))
        print("wrote", out / f"{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
