"""Fetch one session back from CloudWatch through Strands Evals' provider, proving the round trip."""

import os
import sys

from strands_evals.providers import CloudWatchProvider

from agent import config


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m evals.cloudwatch_pull SESSION_ID", file=sys.stderr)
        return 2
    config.require_sandbox()
    log_group = os.environ.get("AGENT_LOG_GROUP")
    if not log_group:
        print("error: AGENT_LOG_GROUP not set", file=sys.stderr)
        return 2
    # Installed 1.2.0: CloudWatchProvider(region=, log_group=, agent_name=, lookback_days=30, ...) queries OTEL log
    # records in the given log group filtered by attributes.session.id, then enriches parent ids from aws/spans.
    provider = CloudWatchProvider(region=config.REGION, log_group=log_group)
    data = provider.get_evaluation_data(session_id=sys.argv[1])  # TaskOutput: TypedDict with output/trajectory keys
    output, trajectory = data["output"], data["trajectory"]
    # trajectory is a strands_evals.types.trace.Session: {traces: [Trace, ...]}; each Trace carries its own
    # `spans` list (no top-level `.spans` on Session), so the span count sums across traces.
    span_count = sum(len(trace.spans) for trace in trajectory.traces)
    print(f"output: {str(output)[:300]}")
    print(f"spans: {span_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
