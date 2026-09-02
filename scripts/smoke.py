"""One call per pinned model. A profile or model existing is not the same as it being usable."""

import os
import sys

import boto3
from openai import OpenAI

from agent import config


def main() -> int:
    config.require_sandbox()
    session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE") or None, region_name=config.REGION)
    runtime = session.client("bedrock-runtime")
    for kind in ("target", "judge"):
        model = config.model_id(kind)
        response = runtime.converse(
            modelId=model,
            messages=[{"role": "user", "content": [{"text": "Responde solo: ok"}]}],
            inferenceConfig={"maxTokens": 8},
        )
        print(f"{kind}: {model} -> {response['output']['message']['content'][0]['text'].strip()!r}")

    attacker = config.model_id("attacker")
    client = OpenAI(api_key=config.bedrock_api_key(), base_url=config.mantle_base_url())
    response = client.responses.create(model=attacker, input="Responde solo: ok")
    print(f"attacker: {attacker} -> {response.output_text.strip()!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
