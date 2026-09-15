# Merchant Catalogue Enrichment — API Model vs. Fine-Tuned Open-Weight Model

## Goal

Given a raw, messy menu item (name, description, price), produce a structured catalogue entry: normalized name, category, cuisine tag(s), dietary tags, and a confidence score. Then show a small fine-tuned open-weight model can match this quality at a fraction of the cost and latency of a third-party API model.

**Example:**

Input: `"chikcen tikka masala (creamy, mild spice)"` — $14.00

Output:
```json
{
  "normalized_name": "Chicken Tikka Masala",
  "category": "Curry",
  "cuisine": "Indian",
  "dietary_tags": ["contains_dairy"],
  "confidence": 0.94
}
```

The typo gets fixed, but the real payoff is the category/cuisine/dietary structure — that's what lets a downstream app answer queries like "show me Indian curries" or "hide anything with dairy," which raw text can't support on its own.

## Milestones

### 1. Dataset
Generate ~300–500 synthetic menu items via LLM, across 8–10 cuisines. This milestone is purely about collecting raw, messy input data (item name, description, price) — no labels involved yet. Deliberately engineer realistic messiness: typos, inconsistent casing, missing descriptions, ambiguous items like "Chef's Special," occasional cross-cuisine items. Store as JSON: `{restaurant, item_name, description, price}`.

### 2. Eval set
Hand-label (or LLM-label + spot-check) ~100 items with correct category, cuisine, and dietary tags. Held out from training entirely, used only for scoring — rigor here matters more than volume.

### 3. Baseline: API model pipeline
Use Claude or GPT with a structured-output prompt (JSON schema) to enrich all items. Log latency and token cost per item, then score against the eval set: per-field accuracy plus confidence calibration.

### 4. Fine-tuned open-weight model
Use the API model to generate a larger labeled training set (distillation) from the non-eval items. Fine-tune a small open-weight model (Llama 3.1 8B, Qwen2.5-7B, or similar) with LoRA — full fine-tune isn't needed. Self-host it (vLLM, Ollama, or similar) and run the same eval set through it, logging latency and estimated serving cost.

### 5. Comparison write-up
A table of accuracy, p50/p95 latency, and cost per 1,000 items across both models, plus error analysis on where each one fails. Keep the tradeoffs honest — the goal isn't to claim a small model beats a frontier one, it's "good enough at a fraction of the cost and latency."

### 6. Stretch: agentic + scoring layer
A lightweight agent that takes a raw, unstructured menu and produces the structured catalogue, flagging uncertain fields instead of guessing. A simple "merchant opportunity score" from catalogue completeness, category coverage, and pricing consistency.

### 7. Stretch: real-world data validation
Once the core pipeline works on synthetic data, stress-test it against **NYPL "What's on the Menu?"** — a public domain dataset of ~1.3M real transcribed dishes with names and prices from historical restaurant menus, available as a direct CSV download. Real, human-transcribed text (OCR quirks, archaic naming, inconsistent formatting) is messier than anything synthetic generation tends to produce, so this checks whether the pipeline holds up beyond engineered test cases. Items would be auto-labeled by the API model itself (not hand-labeled), same as the training corpus in milestone 4.

## Deliverables
- `pipeline/` — enrichment code for both API and fine-tuned paths
- `eval/` — labeled eval set + scoring script
- `results.md` — the comparison table and error analysis
- `README.md` — problem framing, how to run it, and what it demonstrates

## Out of scope
- Production infra (k8s, autoscaling, etc.) — mention as "next steps" in the write-up, don't build it
- Large-scale fine-tuning — LoRA on a small model is sufficient to prove the concept

## Timeline (rough, part-time pace)
- Week 1: dataset + eval set
- Week 2: API baseline pipeline + scoring
- Week 3: fine-tuning + self-serving
- Week 4: comparison write-up, polish README, optional stretch goal
