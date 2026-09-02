# CLAUDE.md — Rompe tu agente antes de que lo rompan (ACD Argentina 2026)

## Verify every API against current docs, every task, every agent
Strands Agents, Strands Evals and Strands Shell change weekly. Do NOT rely on
training memory for class names, parameters or CLI flags. Before writing or
changing code: Context7 (`/strands-agents/evals`, `/strands-agents/docs`) or
the official site, then read the installed source in `.venv` if docs disagree.
Pin what you verify and cite it in README. Every dispatched subagent gets this
instruction verbatim.

## AWS is the speaker's personal sandbox only
The default credentials on this machine belong to a client. Every AWS call
goes through `agent/config.py::require_sandbox()` (AWS_PROFILE must contain
"sandbox", or GITHUB_ACTIONS=true). Never apply infra, never invoke Bedrock
at scale, without the speaker saying so.

## Deliverable boundary
Spec: `docs/superpowers/specs/2026-09-01-rompe-tu-agente-design.md`.
The speaker owns the official Google Slides template; we hand over
`slides/contenido.md` and image assets only.
