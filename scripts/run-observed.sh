#!/usr/bin/env bash
# Runs one Sentinel question under the ADOT SDK so the session lands in CloudWatch GenAI Observability.
set -euo pipefail
: "${AWS_PROFILE:?}"; case "$AWS_PROFILE" in *sandbox*) ;; *) echo "refusing: not the sandbox" >&2; exit 1;; esac
: "${AGENT_LOG_GROUP:=aws-cdarg-sentinel-logs-demo}"
export AGENT_OBSERVABILITY_ENABLED=true
export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_LOGS_HEADERS="x-aws-log-group=${AGENT_LOG_GROUP},x-aws-log-stream=guardia,x-aws-metric-namespace=guardia"
export OTEL_RESOURCE_ATTRIBUTES="service.name=sentinel"
exec uv run --env-file .env opentelemetry-instrument python -m agent.cli "$@"
