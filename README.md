# Rompe tu agente antes de que lo rompan

Demo repo for the AWS Community Day Argentina 2026 talk: chaos testing and red
teaming of a Strands agent on Amazon Bedrock with Strands Evals.

## Versions tested
- Python 3.13, uv
- strands-agents 1.54.0, strands-agents-evals 1.2.0, strands-shell 0.3.3
- aws-bedrock-token-generator 1.1.0, openai 2.54.0
- aws-cdk-lib 2.267.0, constructs 10.8.1, CDK CLI 2.1139.0 (via `npx aws-cdk@2`; CLI major must match the library major). Synth needs Node.js (v22 tested) for jsii; no AWS credentials are required, the stack pins a fixed AZ instead of looking one up.

## Setup
See "Setup" below once Task 15 fills it in.
