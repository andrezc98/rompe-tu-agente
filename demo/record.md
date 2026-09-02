# Plan B — grabación de la demo

Terminal: iTerm2 o Terminal, fondo oscuro, fuente 20 pt, ventana 1600x900, `clear` entre pasos.
QuickTime → Nueva grabación de pantalla → seleccionar la ventana. 1080p. Sin audio (se narra en vivo).

## Toma 1 — chaos (v1), 60 s
```
uv run --env-file .env python -m evals.chaos --prompt v1 --repeats 1 --out /tmp/demo-chaos.json
```
(cortar la espera; dejar el resumen final y un `jq '.reasons[0:3]' /tmp/demo-chaos.json`)

## Toma 2 — el diagnóstico, 40 s
```
uv run --env-file .env python -m evals.diagnose evals/results/show/timeout-v1.json
```
`evals/results/show/timeout-v1.json` es una copia curada de una sesión de chaos real, por ejemplo
`evals/results/sessions/chaos-v1/q2-r1__metric_timeout.json` (el caso `q2-r1|metric_timeout` que
arma `ChaosCase.expand`, con el `|` reemplazado por `__` al guardar la sesión — ver `evals/telemetry.py`).

## Toma 3 — red team, 60 s
```
uv run python -c "from strands_evals.experimental.redteam import RedTeamReport; RedTeamReport.from_file('evals/results/redteam-<fecha>-pass1.json').display()"
```
(sin red: solo lee el JSON)

## Toma 4 — el transcript vs el trace, 40 s
```
cat evals/results/show/stop-prod-transcript.txt
jq '.traces[].spans[] | select(.tool_call.name == "stop_instance")
    | {tool: .tool_call.name, args: .tool_call.arguments, result: .tool_result.content, error: .tool_result.error}' \
  evals/results/show/stop-prod-session.json
```
El archivo es un `strands_evals.types.trace.Session` serializado: los spans cuelgan de cada trace
(`.traces[].spans[]`, no hay `.spans` en la raíz) y el de una tool es un `ToolExecutionSpan` con
`tool_call.name` / `tool_call.arguments` y `tool_result.content` / `tool_result.error`
(strands_evals/types/trace.py). El transcript y el trace de esta toma salen de un replay del caso de red team
`stop_prod_fake_ticket` (definido en `evals/redteam.py`, categoría `excessive_agency`):
```
uv run --env-file .env python -m evals.replay evals/results/redteam-<fecha>-pass1.json \
  --case excessive_agency_1 --strategy crescendo --out stop-prod   # la brecha real del 2026-09-02: ticket inventado sobre dev
```

## Toma 5 — CI rojo y verde (no se graba: son capturas)
`ci-rojo.png` y `ci-verde.png` salen de las corridas reales de GitHub Actions, no de la terminal
(slide 20 dice eso). Según el runbook gated, sección 6: el PR con `CURRENT=v1` deja el workflow
`evals-gate` en rojo (captura de esa corrida) y `gh workflow run evals-gate` sobre main con
`CURRENT=v2` lo deja en verde (captura de esa otra corrida). Recortar el account id de la captura.

Localmente solo se ensaya el mismo gate, para saber qué va a pasar antes de abrir el PR (esto no
se graba ni se captura):
```
echo v1 > agent/prompts/CURRENT   # rompe -> exit 1
uv run --env-file .env python -m evals.regression
echo v2 > agent/prompts/CURRENT   # pasa  -> exit 0
uv run --env-file .env python -m evals.regression
```
Es el mismo gate que corre `.github/workflows/evals.yml`; dejar `agent/prompts/CURRENT` en `v2`
al terminar.

Total objetivo: menos de 4 minutos. Exportar a slides/assets/plan-b.mp4 y copiar al pendrive.

Antes de grabar: `bash demo/sanitize-check.sh`, y revisar que ninguna salida muestre el account id.
