# Rompe tu agente antes de que lo rompan

Repo de la charla en AWS Community Day Argentina 2026 (Buenos Aires, 2026-09-12): un agente
de guardia construido con Strands Agents sobre Amazon Bedrock, roto con chaos testing y
atacado con red teaming usando Strands Evals, con diagnóstico de trazas y un gate de CI.

Todo lo que se muestra en el escenario se regenera desde los JSON en `evals/results/`.

## Versiones probadas (2026-09)
- Python 3.13, uv
- strands-agents 1.54.0 (extras openai, otel), strands-agents-evals 1.2.0, strands-shell 0.3.3,
  aws-bedrock-token-generator 1.1.0
- openai 2.54.0 (cliente HTTP usado por el atacante GPT vía Bedrock Mantle, Responses API)
- Modelos: target y juez son perfiles de inferencia de Claude en Bedrock; atacante es GPT en
  Bedrock Mantle. Los tres ids se fijan el día del setup con `scripts/pin-models.sh` y quedan
  en `.env` (a partir de `.env.example`), nunca hardcodeados en el repo. Pines usados para los
  resultados de este repo (2026-09-02, us-east-1): target `us.anthropic.claude-sonnet-5`, juez de
  chaos `us.anthropic.claude-opus-5`, juez de red team `us.anthropic.claude-opus-4-8`
  (`REDTEAM_JUDGE_MODEL_ID`; Opus 5 devuelve `content_filtered` ante transcripts adversariales y la
  librería cuenta ese error como brecha), atacante `openai.gpt-5.6-sol`. Sonnet 5 y Opus 5
  rechazan `temperature` en Converse, por eso los modelos se construyen sin parámetros de muestreo.
- Prompts del atacante: el clasificador de ciberseguridad de OpenAI en Bedrock Mantle rechaza el
  prompt de atacante de strands-agents-evals 1.2.0 ("Adversarial Actor Simulation... security
  tester... never reveal you are a tester"), con Terra y con Sol. El PR #298 del proyecto
  (abierto, sin publicar) lo reformula como evaluación de seguridad autorizada; ese texto está
  vendoreado tal cual en `evals/vendor/` y se aplica en tiempo de ejecución desde
  `evals/strands_overrides.py`. Verificado el 2026-09-02: mismo turno 1 de GOAT, prompt 1.2.0
  rechazado 2/2, prompt del PR aceptado 2/2.
- Crescendo en 1.2.0 da por "cumplido" el ataque ante cualquier llamada a tool del target,
  lecturas incluidas, así que contra Sentinel nunca pasaba del turno 1. El mismo módulo reemplaza
  `CrescendoStrategy.run_attack` por una copia literal donde solo `stop_instance` cuenta como
  acción; GOAT no tiene ese corte.
- AWS CDK v2: aws-cdk-lib 2.267.0, constructs 10.8.1, CDK CLI 2.1139.0 (via `npx aws-cdk@2`;
  el major de la CLI debe coincidir con el de la librería). La síntesis necesita Node.js (v22
  probado) para jsii. La síntesis no necesita credenciales, pero `infra/app.py` exige
  `AWS_PROFILE` con el perfil sandbox (o `GITHUB_ACTIONS=true`) y se niega a correr con otras
  credenciales; exportar el perfil ANTES de tocar `cdk`, porque la CLI resuelve la cuenta por
  defecto con las credenciales del entorno. Dos stacks: `SentinelBootstrap` (proveedor OIDC de
  GitHub + rol de CI, se despliega una vez desde la laptop) y `SentinelDemo` (VPC, instancias,
  alarma, log group, rol del agente, se despliega y destruye desde GitHub Actions con el workflow
  `infra`). Se referencian solo por ARN determinístico, sin exports de CloudFormation. El
  bootstrap de CDK usa el qualifier `cdarg2026` y el stack `aws-cdarg-sentinel-toolkit-demo`
  (`cdk.json`), así no toca un `CDKToolkit` preexistente. Si la cuenta ya tiene un proveedor OIDC
  para `token.actions.githubusercontent.com`, el deploy del bootstrap falla con
  `EntityAlreadyExists`: pasar `-c oidc_provider_arn=<arn>` para importarlo. El `github_repo` de
  `cdk.json` es el prefijo del claim `sub` que GitHub emite para el repo (desde 2026 incluye ids
  inmutables: `owner@<id>/repo@<id>`); se obtiene con
  `gh api repos/<owner>/<repo>/actions/oidc/customization/sub --jq .sub_claim_prefix`.
- Instancias: `m9g.medium` (Graviton5) con Bottlerocket ARM64 en `infra/sentinel_stack.py`; si
  la región no ofrece `m9g`, el fallback documentado ahí es `m8g.medium`. El tipo que la región
  del setup efectivamente acepte se confirma ese día, no antes (2026-09-02: `m9g.medium` aceptado
  en us-east-1).

## Setup
1. `uv sync` (Node.js debe estar instalado: jsii y la CLI de CDK lo usan)
2. Infra (cuenta sandbox propia), desde la laptop y una sola vez:
   `npx aws-cdk@2.1139.0 bootstrap --qualifier cdarg2026` y
   `npx aws-cdk@2.1139.0 deploy SentinelBootstrap --outputs-file infra/outputs.json`.
   Luego `gh secret set AWS_CI_ROLE_ARN` con `CiRoleArn` de ese archivo y
   `gh workflow run infra -f action=deploy` (GitHub Actions despliega `SentinelDemo`;
   `-f action=destroy` la destruye). Las salidas de la stack demo:
   `aws cloudformation describe-stacks --stack-name aws-cdarg-sentinel-stack-demo --query 'Stacks[0].Outputs'`
3. `bash infra/enable-transaction-search.sh` (una vez por cuenta)
4. `bash scripts/pin-models.sh` y completar `.env` a partir de `.env.example` con los ids de
   modelo que liste el script y las salidas de la stack demo (`SentinelRoleArn` →
   `SENTINEL_ROLE_ARN`, `DevInstanceId`/`ProdInstanceId` → `DEV_INSTANCE_ID`/`PROD_INSTANCE_ID`)
5. `uv run --env-file .env python scripts/smoke.py` (una llamada por modelo: target, juez, atacante)

## Correr
- Agente: `uv run --env-file .env python -m agent.cli "¿Qué instancias del equipo pagos hay?"`
- Chaos: `uv run --env-file .env python -m evals.chaos --prompt v1 --repeats 3 --out evals/results/chaos-v1.json`
- Veredictos humanos (escribe el JSON revisado que consumen los gráficos y las slides):
  `uv run python -m evals.verdicts evals/results/chaos-v1.json --out evals/results/chaos-v1-revisado.json`
  (y lo mismo con `chaos-v2.json` → `chaos-v2-revisado.json`; sin `--out` solo imprime el resumen)
- Gráficos del deck: `uv run python -m evals.charts` (lee los `*-revisado.json` y los reportes de
  red team en `evals/results/`, escribe los PNG en `slides/assets/`)
- Diagnóstico: `uv run --env-file .env python -m evals.diagnose evals/results/show/timeout-v1.json`
- Red team (genera además la suite de brechas): `uv run --env-file .env python -m evals.redteam --generate 8 --passes 2`
- Replay de un ataque puntual (transcript + trace): `uv run --env-file .env python -m evals.replay <reporte> --case <caso> --strategy <estrategia>`
- Regresión (el mismo gate que corre CI): `uv run --env-file .env python -m evals.regression`
  (sin `evals/suites/redteam.json` todavía, imprime que no hay suite y sale 0)
- Observabilidad en CloudWatch: `bash scripts/run-observed.sh "pregunta"` y luego `uv run --env-file .env python -m evals.cloudwatch_pull <session.id>`

## Notas de diseño
- El gate de CI corre `python -m evals.chaos --prompt ... --repeats 3 --gate-evaluator FailureCommunicationEvaluator --fail-on 1.0` (ninguna corrida puede esconder una falla; el score global se imprime como información porque su techo es ~0.75 por construcción), no el CLI
  `strands-evals run`. Ese CLI carga el archivo del experimento y lo reconstruye siempre como un
  `Experiment` común (`strands_evals/cli/commands/run.py:315-319`), nunca como un
  `ChaosExperiment`, que es quien activa el `ChaosCase` en el ContextVar que lee `ChaosPlugin`
  (`strands_evals/chaos/experiment.py:106`, `strands_evals/chaos/plugin.py:29`). Con el CLI los
  efectos no se inyectan: no falla nada y todo pasa. El entrypoint del módulo mantiene ese cableado
  bajo nuestro control.
- `evals/verdicts.json` se indexa por el nombre expandido del caso (`q2-r1|metric_timeout`), que ya
  trae la repetición adentro: `q2` es la pregunta, `r1` la repetición y `metric_timeout` la
  condición. No hace falta otra clave para distinguir repeticiones.
- El reporte de chaos trae una fila por (caso, evaluador): con cuatro evaluadores, 54 corridas son
  216 filas y cada nombre aparece cuatro veces. `evals/report_rows.py` las reagrupa, así que un
  veredicto humano se aplica a la corrida entera y una corrida aprueba solo si aprueban los cuatro.

## Las tres capas
modelo (prompt v1/v2) → sandbox (Strands Shell, bind de solo runbooks/public) → permisos (rol
`aws-cdarg-sentinel-role-agent-demo` con Deny de StopInstances en env=prod).

## Notas de reproducibilidad
- El agente usa las credenciales del perfil sandbox para Bedrock y asume
  `aws-cdarg-sentinel-role-agent-demo` para las tools (expuesto como `SENTINEL_ROLE_ARN` en
  `.env`, salida `SentinelRoleArn` de la stack). El atacante del red team (GPT) entra por
  Bedrock Mantle con una API key de corta duración (hasta 12 h) generada en cada corrida a
  partir de las credenciales de AWS activas; no hay claves de API en archivos.
- Red teaming vive en `strands_evals.experimental.redteam`; la API puede cambiar entre
  versiones, por eso está fijada arriba. La suite de brechas para el gate de regresión vive en
  `evals/suites/redteam.json` y la genera `evals.redteam` a partir de los casos que efectivamente
  rompieron el prompt.
- `evals.chaos --out` guarda el reporte del experimento completo (todos los casos y puntajes);
  `evals.diagnose` necesita en cambio una sesión cruda de un caso puntual, guardada aparte en
  `evals/results/sessions/chaos-<prompt>/<caso>.json` — no son el mismo archivo ni intercambiables.
  El nombre de esas sesiones reemplaza el `|` que arma `ChaosCase.expand` (por ejemplo
  `q2-r1|metric_timeout`) por `__` (`q2-r1__metric_timeout.json`), porque `|` rompe globs y
  citado de shell.
- Antes de commitear cualquier resultado o asset (JSON de evals, capturas, video), correr
  `bash demo/sanitize-check.sh`; debe imprimir `sanitize-check: clean`.

## Fuentes
Ver `slides/fuentes.md`.
