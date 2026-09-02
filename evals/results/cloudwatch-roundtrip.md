# Ida y vuelta CloudWatch (runbook §5)

Sesión observada con `scripts/run-observed.sh "¿Por qué está en alarma la instancia de pagos?"` el 2026-09-02 (prompt v2), recuperada con `python -m evals.cloudwatch_pull <session.id>` desde el log group `aws-cdarg-sentinel-logs-demo` (OTLP, ADOT) unos 20 minutos después.

```
session.id=114b6032-28c2-4de9-ab95-4ac7a6fa903d
output: {"instances": {"i-054570400bd2f64ba": {"State": "running", "Type": "m9g.medium", "Name": "aws-cdarg-sentinel-ec2-prod", "env": "prod"}, "i-02f1e51c559c9c557": {"State": "running", "Type": "m9g.medium", "Name": "aws-cdarg-sentinel-ec2-dev", "env": "dev"}}}
spans: 7
```

Nota: el endpoint OTLP de logs de CloudWatch rechaza los lotes (400) si el log stream no existe; `run-observed.sh` lo crea antes de exportar.
