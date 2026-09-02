# Rompe tu agente antes de que lo rompan

Demo repo for the AWS Community Day Argentina 2026 talk: chaos testing and red
teaming of a Strands agent on Amazon Bedrock with Strands Evals.

## Versions tested
- Python 3.13, uv
- strands-agents 1.54.0, strands-agents-evals 1.2.0, strands-shell 0.3.3
- aws-bedrock-token-generator 1.1.0, openai 2.54.0
- aws-cdk-lib 2.267.0, constructs 10.8.1, CDK CLI 2.1139.0 (via `npx aws-cdk@2`; CLI major must match the library major). Synth needs Node.js (v22 tested) for jsii. La síntesis no necesita credenciales, pero `infra/app.py` exige `AWS_PROFILE` con el perfil sandbox (o `GITHUB_ACTIONS=true`) y se niega a correr con otras credenciales; exporta el perfil ANTES de tocar `cdk`, porque la CLI resuelve la cuenta por defecto con las credenciales del entorno. Si la cuenta ya tiene un proveedor OIDC para token.actions.githubusercontent.com, el deploy falla con EntityAlreadyExists: en ese caso importarlo con OpenIdConnectProvider.from_open_id_connect_provider_arn.

## Setup
See "Setup" below once Task 15 fills it in.
