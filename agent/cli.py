"""Ask Sentinel one question from the terminal. Used by scripts/run-observed.sh."""

import sys
import uuid

from agent import config
from agent.sentinel import make_sentinel


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m agent.cli 'pregunta'", file=sys.stderr)
        return 2
    config.require_sandbox()
    session_id = str(uuid.uuid4())
    agent = make_sentinel(session_id=session_id)
    response = agent(" ".join(sys.argv[1:]))
    print(response)
    print(f"[session.id={session_id}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
