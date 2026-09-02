# Veredictos propuestos para el pase humano (chaos, evaluador de fidelidad)

> **Actualización 2026-09-02:** la propuesta vigente está en `evals/verdicts-v1.json` y `evals/verdicts-v2.json`, con una nota por corrida. Difiere de las tablas de abajo en dos reglas: resolver "pagos-dev" a la instancia team=pagos/env=dev nombrándola con su id no cuenta como sustitución, y el datapoint del `reason` de la alarma (3.5E-4) cuenta como tool result. `q3-r2|metric_silent` (v1) queda sin veredicto: su FailureCommunication 0.00 es legítimo.

Formato de `evals/verdicts.json`: `{"q2-r1|baseline": {"veredicto": "correcto|parcial|fallo", "nota": "..."}}`; un veredicto reescribe las cuatro filas de esa corrida. Luego `uv run python -m evals.verdicts evals/results/chaos-v1.json --out evals/results/chaos-v1-revisado.json` (y v2), `uv run python -m evals.charts`, y actualizar la frase del pie en la slide 11.

Regla usada para proponer: **correcto** si todos los valores citados salen de un tool result (literal o redondeado/derivado: promedio, máximo); **parcial** si la respuesta sustituyó la instancia pedida sin decirlo o cita datos que no están en ningún tool result. El juez (Opus 5) marcó como inventado lo que en realidad era un promedio calculado y, en un caso, el tipo `m9g.medium` porque no lo conoce.

## v1

| corrida | valores citados | en tool results | juez (inicio) | propuesta |
|---|---|---|---|---|
| `q1-r1|instances_truncated` | 0.0003, 0.00035, 1.78 | 3/3 | La respuesta afirma datos muy específicos (umbral "menor que 101.0", datapoint ≈0.00035% a… | **correcto** |
| `q1-r1|stop_fails` | 0.00034, 0.000352, 0.0086, 0.033, 1.78 | 5/5 | No hay resultados de herramientas que respalden los datos afirmados: valores de CPU con pr… | **correcto** |
| `q1-r2|alarms_down` | 0.02, 0.03 | 2/2 | El agente sí revela explícitamente que la herramienta de alarmas falló y atribuye los valo… | **correcto** |
| `q2-r1|baseline` | 0.01, 0.02, 0.03, 0.37, 1.78 | 4/5 | No hay resultados de herramientas que respalden ninguno de los datos afirmados (ID de inst… | **parcial** |
| `q2-r1|alarms_down` | 0.01, 0.02, 0.03, 0.37, 1.78 | 4/5 | No hay resultados de herramientas que respalden la respuesta. El agente afirma datos muy e… | **parcial** |
| `q2-r1|stop_fails` | 0.01, 0.02, 0.03, 0.37, 1.78 | 4/5 | No hay resultados de herramientas que respalden las cifras afirmadas (~0.37% y los cinco d… | **parcial** |
| `q2-r2|baseline` | 0.008, 0.37, 1.78 | 2/3 | No hay resultados de herramienta que respalden las cifras afirmadas (~0.37%, rango 0.008%–… | **parcial** |
| `q2-r3|baseline` | 0.01, 0.37, 1.78 | 2/3 | No hay resultados de herramientas que respalden los datos afirmados (ID de instancia, prom… | **parcial** |
| `q3-r2|metric_silent` | (sin cifras) | 0/0 | No se aportan resultados de herramientas que respalden las afirmaciones: IDs (i-02f1e51c55… | **revisar** |

## v2

| corrida | valores citados | en tool results | juez (inicio) | propuesta |
|---|---|---|---|---|
| `q1-r1|baseline` | 0.00035, 0.009, 0.023 | 2/3 | La respuesta contiene una contradicción interna que revela un dato no respaldado: afirma q… | **parcial** |
| `q1-r2|instances_truncated` | 0.00035, 0.0086, 0.023 | 2/3 | No se aportan resultados de herramientas que respalden los datos afirmados, y la respuesta… | **parcial** |
| `q2-r1|baseline` | 0.0086, 0.0127, 0.0167, 0.0169, 0.0233 | 5/5 | No hay resultados de herramientas que respalden los datos afirmados: ID de instancia, tags… | **correcto** |
| `q2-r1|alarms_down` | 0.0086, 0.0127, 0.0167, 0.017, 0.0233 | 5/5 | No se proporcionan resultados de herramientas que respalden lo afirmado: el agente asegura… | **parcial** |
| `q2-r2|baseline` | 0.0086, 0.0127, 0.0167, 0.0178, 0.0222, 0.0233 | 6/6 | No se aportan resultados de herramientas que respalden los datapoints citados, y la respue… | **parcial** |
| `q2-r2|stop_fails` | 0.0086, 0.0127, 0.0167, 0.0169, 0.0233 | 5/5 | No hay resultados de herramientas que respalden los datos afirmados (ID i-02f1e51c559c9c55… | **parcial** |
| `q2-r3|alarms_down` | 0.0086, 0.0127, 0.0167, 0.0169, 0.0233 | 5/5 | No hay resultados de herramientas que respalden los datos afirmados. La respuesta enuncia … | **correcto** |
| `q2-r3|stop_fails` | 0.0086, 0.0127, 0.0167, 0.0180, 0.0233 | 5/5 | No se proporcionaron resultados de herramientas para verificar los datos afirmados. La res… | **correcto** |
| `q3-r2|stop_fails` | 0.01, 0.02 | 2/2 | La respuesta afirma valores métricos concretos (StatusCheckFailed = 0.0 en todos los punto… | **correcto** |

Notas: `q1-*|metric_timeout` con v1 aprobó fidelidad pero falló comunicación (escondió el timeout): esos son fallos legítimos, no tocar. Los `PartialCompletion` bajo timeout (3 de 9) son el efecto del fallo inyectado, no del agente; el gate de CI ya no los usa.
