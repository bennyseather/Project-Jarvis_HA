# M28 — Hybrid Research and Cost-Aware Intelligence

Status: complete

M28 makes research local-first. Project Jarvis Search supplies a private
SearXNG JSON endpoint; Jarvis retrieves a bounded number of public HTTP(S)
sources, rejects private-network page targets, extracts evidence, and retains
citations. OpenAI is used only for language routing and evidence synthesis.

The provider-neutral reasoning boundary uses GPT-5.6 Luna normally, escalates
once to Terra after a provider failure, and uses Sol only when the user
explicitly requests premium reasoning. A persistent monthly ledger stores
provider, model, token counts, timestamp, and estimated USD cost—but never
prompts or answers. The default USD 10 budget warns at 70% and 90% and blocks
further external calls at 100%.

The reasoning contract is intentionally independent of OpenAI so a local Ollama
provider can replace or precede it in a future milestone without changing
Jarvis memory, research, citations, or Home Assistant orchestration.
