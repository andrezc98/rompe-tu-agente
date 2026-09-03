# Fuentes

Todo dato, versión o API que aparece en la charla, con la fecha en que se verificó. Las
diapositivas están en `slides/contenido.md`.

## SDK y librerías

- strands-agents-evals 1.2.0 (2026-08-21) en PyPI — https://pypi.org/project/strands-agents-evals/ — consultado 2026-09-01 — slides 9, 10, 15, 16 (versión fijada del SDK de evaluación)
- Releases de strands-agents/evals (chaos testing y red teaming desde 1.0.0, 2026-06-16) — https://github.com/strands-agents/evals/releases — consultado 2026-09-01 — slides 9, 14
- strands-agents 1.54.0 (2026-08-27) en PyPI — https://pypi.org/project/strands-agents/ — consultado 2026-09-01 — slide 6 (versión del framework del agente)
- Strands Shell — Quickstart — https://strandsagents.com/docs/user-guide/shell/quickstart/ — consultado 2026-09-01 — slide 7 (shell en proceso, binds copy/direct)
- Strands Shell — Modelo de seguridad ("a mediation layer, not a hardened sandbox") — https://strandsagents.com/docs/user-guide/shell/security/ — consultado 2026-09-01 — slides 7, 14 (capa 2)
- Strands Evals — Red teaming — https://strandsagents.com/docs/user-guide/evals-sdk/red-teaming/ — consultado 2026-09-02 — slides 14, 15, 16 (categorías de riesgo, umbral del juez, "una corrida limpia es evidencia, no garantía", fijar la versión si se usa en CI)
- Código instalado de strands-agents-evals 1.2.0 (`.venv`): API de chaos (`ChaosCase.expand`, `ChaosExperiment`, `ChaosPlugin`, efectos), `detectors.diagnose_session` y el CLI `strands-evals run ... --fail-on` — verificado contra el código instalado, 2026-09-02 — slides 10, 19, 20 (la doc publicada y el código instalado difieren; manda el código)
- Strands Evals — README de redteam en el repo — https://github.com/strands-agents/evals/blob/main/src/strands_evals/experimental/redteam/README.md — consultado 2026-09-01 — slide 15 (API experimental, agent_factory)
- Strands — proveedor OpenAI Responses (atacante GPT vía Bedrock Mantle) — https://strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/ — consultado 2026-09-01 — slide 15
- Anuncio de release: contexto, Strands Shell y Evals 1.0 — https://strandsagents.com/blog/reduced-cost-better-isolation-more-resilience/ — consultado 2026-09-01 — slides 6, 7

## Taxonomía de riesgos

- OWASP Top 10 for LLM Applications (GenAI Security Project) — https://genai.owasp.org/llm-top-10/ — consultado 2026-09-02 — slide 14 (taxonomía con la que la doc de Strands alinea las categorías: agencia excesiva y fuga del system prompt)

## AWS

- Amazon Bedrock — model card de OpenAI GPT-5.6 Sol (id, endpoint Mantle, Responses API) — https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-sol.html — consultado 2026-09-02 — slide 15 (el atacante no es tu modelo)
- strands-agents/evals PR #298 — "Reframe red team attacker prompts to survive aligned attacker models" (abierto, sin publicar; texto vendoreado en evals/vendor) — https://github.com/strands-agents/evals/pull/298 — consultado 2026-09-02 — slides 15 y 16
- OpenAI — Safety checks: cybersecurity (el mensaje de rechazo del atacante) — https://platform.openai.com/docs/guides/safety-checks/cybersecurity — consultado 2026-09-02 — slides 15 y 21
- Amazon Bedrock — API keys de corta duración — https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-generate.html — consultado 2026-09-01 — slide 15 (credencial del atacante, sin claves en archivos)
- aws-bedrock-token-generator para Python — https://github.com/aws/aws-bedrock-token-generator-python/blob/main/README.md — consultado 2026-09-01 — slide 15
- Amazon Bedrock Guardrails — Detectar ataques de prompt (jailbreak, inyección, fuga del system prompt; exige tags de entrada; no evalúa tool results) — https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html — consultado 2026-09-02 — slide 21 (capa 1 comprada hecha, y su límite)
- AgentCore Code Interpreter — ejecución de código en sandboxes aislados — https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html — consultado 2026-09-03 — slide 22b (capa 2 comprada hecha)
- AgentCore Gateway — conceptos: tools por MCP para agentes — https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-core-concepts.html — consultado 2026-09-03 — slide 22b (capa 4: Policy se evalúa en el Gateway)
- Logo de Strands Agents (SVG oficial del sitio de docs) — https://strandsagents.com/latest/assets/logo-github.svg — descargado 2026-09-03 — slide 22b (`slides/figuras/strands-logo.svg`, embebido en `arquitectura-solida.drawio`)
- AgentCore Policy — condiciones Cedar sobre los argumentos de la tool (`context.input`) en cada invocación vía Gateway — https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-conditions.html — consultado 2026-09-02 — slide 21 (capa 4 comprada hecha)
- AgentCore Observability para agentes fuera del runtime (ADOT, Transaction Search) — https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html — consultado 2026-09-01 — slide 18 (la sesión y el trace en CloudWatch)
- Bottlerocket ARM64 vía parámetro SSM público — https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-bottlerocket-retrieve-ami.html — consultado 2026-09-01 — slide 6 (las dos instancias del sandbox)
- Tipos de instancia EC2 de propósito general (familia M9g, Graviton5) — https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html — consultado 2026-09-01 — slide 6
- AWS CDK v2, referencia de Python (PolicyStatement con Effect.DENY y condiciones por tag) — https://docs.aws.amazon.com/cdk/api/v2/python/ — consultado 2026-09-01 — slides 7, 18 (capa 3: Deny si env=prod)
- Cloudscape Design System — bar chart, table y status indicator; modo oscuro con `applyMode` (componentes 3.0.1359, chat-components 1.0.166, global-styles 1.0.67) — https://cloudscape.design/components/bar-chart/ — consultado 2026-09-03 — slides 2, 3, 7, 11, 13, 14, 16 (las escenas, el diagrama de capas, los gráficos y la matriz: el mismo sistema de diseño que la consola de las capturas)
- Amazon Nova Canvas — estructura de request/response de generación de imágenes — https://docs.aws.amazon.com/nova/latest/userguide/image-gen-req-resp-structure.html — consultado 2026-09-02 — slides 3, 4 (las dos ilustraciones son generación propia, sin derechos de terceros)

## Evento

- Lineamiento para las sesiones v1.0 — AWS Community Day Argentina, Comité de Contenido (PDF, sin URL pública) — consultado 2026-09-01 — estructura del mazo, tiempos 2/5/18/5, QR de feedback en Q&A y cierre, código de 10 a 15 líneas

## Resultados propios

Los archivos de `evals/results/` que respaldan cada número de las slides 11, 13, 16, 17, 18, 19 y
21 se agregan acá en el Pase B, cuando las corridas existan (ver
`docs/superpowers/plans/2026-09-02-gated-runbook.md`). Cada archivo se cita con la fecha de la
corrida y la slide que alimenta.
